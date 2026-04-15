"""
Blender addon for transferring weights from avatar to clothing with contamination prevention
"""

import bpy
import bmesh
from mathutils import Vector
import os
import importlib
import textwrap
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    EnumProperty,
    PointerProperty,
    CollectionProperty
)
from bpy.types import PropertyGroup

bl_info = {
    "name": "PureQ Weight Transfer",
    "author": "TresDtres",
    "version": (1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > PureQ Weight Transfer",
    "description": "Transfer weights from avatar to clothing with contamination prevention",
    "category": "Object",
    "license": "Apache-2.0",
}

# Global variables
avatar_object = None
clothing_objects = []

# Common avatar mesh names
AVATAR_MESH_NAMES = [
    'Female', 'female', 'FEMALE',
    'Male', 'male', 'MALE',
    'Child', 'child', 'CHILD',
    'Avatar', 'avatar', 'AVATAR',
    'Body', 'body', 'BODY',
    'Character', 'character', 'CHARACTER'
]

def cleanup_object_references():
    """Clean up references to objects that no longer exist in the scene"""
    global avatar_object, clothing_objects

    # Check if avatar_object still exists
    try:
        if avatar_object and avatar_object.name not in bpy.data.objects:
            avatar_object = None
    except ReferenceError:
        avatar_object = None

    # Filter out clothing objects that no longer exist
    valid_clothing_objects = []
    for obj in clothing_objects:
        try:
            if obj.name in bpy.data.objects:
                valid_clothing_objects.append(obj)
        except ReferenceError:
            # Skip objects that no longer exist
            continue

    clothing_objects = valid_clothing_objects


def get_armature_for_mesh(mesh_obj):
    """Best-effort armature resolution for a mesh."""
    if not mesh_obj or mesh_obj.type != 'MESH':
        return None

    # 1) Armature modifier (standard case)
    for modifier in mesh_obj.modifiers:
        if modifier.type == 'ARMATURE' and modifier.object and modifier.object.type == 'ARMATURE':
            return modifier.object

    # 2) Direct parent armature
    if mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
        return mesh_obj.parent

    # 3) Parent chain armature
    parent = mesh_obj.parent
    while parent:
        if parent.type == 'ARMATURE':
            return parent
        parent = parent.parent

    # 4) Fallback by vertex-group/bone overlap
    if mesh_obj.vertex_groups:
        vg_names = {vg.name.lower() for vg in mesh_obj.vertex_groups}
        best_match = None
        best_score = 0
        for obj in bpy.data.objects:
            if obj.type != 'ARMATURE' or not obj.data:
                continue
            bone_names = {b.name.lower() for b in obj.data.bones}
            score = len(vg_names.intersection(bone_names))
            if score > best_score:
                best_score = score
                best_match = obj
        if best_match and best_score > 0:
            return best_match

    return None


def get_avatar_candidate_meshes():
    """Return meshes likely to be avatar body meshes."""
    candidates = []
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        arm = get_armature_for_mesh(obj)
        if not arm:
            continue
        score = 0
        name_l = obj.name.lower()
        for token in ("female", "male", "child", "avatar", "body", "character"):
            if token in name_l:
                score += 3
        # Prefer meshes with many vertex groups (body mesh usually has many)
        score += min(len(obj.vertex_groups), 100) // 10
        candidates.append((score, obj))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [obj for _, obj in candidates]


def _norm_profile_key(value):
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _find_matching_bone_profile_name(candidate_values, available_profiles):
    norm_map = {_norm_profile_key(name): name for name in available_profiles}
    for value in candidate_values:
        key = _norm_profile_key(value)
        if key and key in norm_map:
            return norm_map[key]
    return None


def _object_has_any_weights(obj, min_weight=0.0):
    for vertex in obj.data.vertices:
        for group in vertex.groups:
            if group.weight > min_weight:
                return True
    return False


def _apply_data_transfer_weights(target_obj, source_obj, mapping):
    mod = target_obj.modifiers.new(name="PureQ_Transfer", type='DATA_TRANSFER')
    mod.object = source_obj
    mod.use_vert_data = True
    mod.data_types_verts = {'VGROUP_WEIGHTS'}
    mod.layers_vgroup_select_src = 'ALL'
    mod.layers_vgroup_select_dst = 'NAME'
    mod.vert_mapping = mapping
    mod.mix_mode = 'REPLACE'
    mod.use_object_transform = True
    bpy.context.view_layer.objects.active = target_obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return _object_has_any_weights(target_obj, min_weight=0.0)


def _collect_weighted_vertex_indices(obj, allowed_group_names, min_weight):
    allowed_norm = {_norm_profile_key(name) for name in (allowed_group_names or [])}
    result = set()
    for vertex in obj.data.vertices:
        for group in vertex.groups:
            if group.group >= len(obj.vertex_groups):
                continue
            if group.weight <= min_weight:
                continue
            vg_name = obj.vertex_groups[group.group].name
            if not allowed_norm or _norm_profile_key(vg_name) in allowed_norm:
                result.add(vertex.index)
                break
    return result


def _clear_weights_for_groups(obj, group_names=None):
    all_indices = [v.index for v in obj.data.vertices]
    if not all_indices:
        return
    if group_names:
        names_norm = {_norm_profile_key(name) for name in group_names}
    else:
        names_norm = None
    for vg in obj.vertex_groups:
        if names_norm is None or _norm_profile_key(vg.name) in names_norm:
            vg.remove(all_indices)


def _remove_weights_from_vertices(obj, vertex_indices):
    if not vertex_indices:
        return
    for vg in obj.vertex_groups:
        vg.remove(vertex_indices)


def _normalize_transfer_profile(raw_profile):
    if not isinstance(raw_profile, dict):
        return None
    allowed = set(raw_profile.get("allowed_bones", []))
    forbidden = set(raw_profile.get("forbidden_bones", []))
    return {
        "allowed_bones": allowed,
        "forbidden_bones": forbidden,
        "min_weight": float(raw_profile.get("min_weight", 0.001)),
        "max_influences": int(raw_profile.get("max_influences", 4)),
    }


def _resolve_transfer_profile(scene, active_obj=None):
    """
    Resolve the effective transfer profile source.
    Priority: Model Profile (object/scene) -> Bone Profile dropdown.
    Returns (profile_dict, source_kind, source_name) where source_kind in {"model","bone"}.
    """
    # 1) Try model profile first (reduces confusion and aligns with Profile Manager).
    try:
        from .model_profile_db import PureQ_ProfileDatabase
        candidate_keys = []
        if active_obj:
            candidate_keys.append(active_obj.get("PureQ_model_profile"))
        selected_model = getattr(scene, "PureQ_selected_model_profile", "")
        if selected_model and selected_model != "NONE":
            candidate_keys.append(selected_model)

        for key in candidate_keys:
            if not key:
                continue
            model_data = PureQ_ProfileDatabase.get_model_profile(key)
            if not model_data:
                continue
            normalized = _normalize_transfer_profile(model_data.get("profile", {}))
            if normalized and normalized.get("allowed_bones"):
                return normalized, "model", key
    except Exception:
        pass

    # 2) Fallback to Bone Profile dropdown (explicit selection only).
    try:
        from .core.bone_profiles import get_bone_profile
        profile_name = getattr(scene, "PureQ_bone_profile", "")
        if profile_name and profile_name != "NONE":
            profile = get_bone_profile(profile_name)
            if profile:
                return profile, "bone", profile_name
    except Exception:
        pass

    # 3) One-shot manual workflow (no profile creation required).
    # Use the current manual bone mask if user has selected at least one bone.
    try:
        manual_bones = [item.name for item in getattr(scene, "PureQ_bone_list", []) if getattr(item, "enabled", False)]
        if manual_bones:
            profile = {
                "allowed_bones": set(manual_bones),
                "forbidden_bones": set(),
                "min_weight": 0.001,
                "max_influences": 4,
            }
            return profile, "manual", "MANUAL_SELECTION"
    except Exception:
        pass

    return None, None, None


def _get_ui_language():
    """Return a short UI language code ('es' or 'en')."""
    locale = ""
    try:
        locale = (bpy.app.translations.locale or "").strip()
    except Exception:
        locale = ""
    if not locale:
        try:
            locale = (bpy.context.preferences.view.language or "").strip()
        except Exception:
            locale = ""
    l = locale.lower()
    if l.startswith("es"):
        return "es"
    if l.startswith("ko"):
        return "ko"
    return "en"


def _lang_pick(messages, default_en=""):
    if isinstance(messages, str):
        return messages
    lang = _get_ui_language()
    return messages.get(lang) or messages.get("en") or default_en


UI_TEXT = {
    "manager_active": {"es": "Modo gestor activo", "en": "Manager mode is active"},
    "manager_loaded": {"es": "Propiedad de perfil cargada", "en": "Model profile property loaded"},
    "manager_missing": {"es": "Falta propiedad de perfil", "en": "Model profile property missing"},
    "manager_reload_tip": {"es": "Prueba recargar addon o reiniciar Blender", "en": "Try reloading addon or restarting Blender"},
    "avatar_section": {"es": "Avatar", "en": "Avatar"},
    "mesh_label": {"es": "Malla", "en": "Mesh"},
    "armature_label": {"es": "Armature", "en": "Armature"},
    "no_avatar": {"es": "No hay avatar asignado", "en": "No avatar set"},
    "avatar_tip": {"es": "Tip: selecciona malla avatar y pulsa Set Avatar from Selection", "en": "Tip: select avatar mesh and click Set Avatar from Selection"},
    "garment_section": {"es": "Prenda", "en": "Garment"},
    "active_label": {"es": "Activa", "en": "Active"},
    "type_label": {"es": "Tipo", "en": "Type"},
    "height_label": {"es": "Altura", "en": "Height"},
    "select_garment": {"es": "Selecciona una malla de prenda", "en": "Select a garment mesh"},
    "garment_config": {"es": "Configuracion de prenda", "en": "Garment Configuration"},
    "model_label": {"es": "Modelo", "en": "Model"},
    "weight_profile_label": {"es": "Perfil de pesos (plantilla de huesos)", "en": "Weight Profile (Bone Template)"},
    "method_label": {"es": "Metodo", "en": "Method"},
    "double_pass_label": {"es": "Limpieza anti-contaminacion en doble pasada", "en": "Double-pass contamination cleanup"},
    "seed_threshold_label": {"es": "Umbral semilla", "en": "Seed threshold"},
    "profiles_available": {"es": "Perfiles de huesos disponibles", "en": "Available bone profiles"},
    "profiles_unavailable": {"es": "Perfiles de huesos no disponibles", "en": "Bone profiles unavailable"},
    "bone_mask_section": {"es": "Mascara de huesos (filtro manual)", "en": "Bone Mask (Manual Filter)"},
    "load_mask_btn": {"es": "Cargar mascara desde perfil", "en": "Load Bone Mask from Profile"},
    "restore_mask_btn": {"es": "Restaurar desde objeto", "en": "Restore from Object"},
    "select_all": {"es": "Seleccionar todo", "en": "Select All"},
    "deselect_all": {"es": "Deseleccionar todo", "en": "Deselect All"},
    "uncheck_tip": {"es": "Desmarca huesos para excluirlos", "en": "Uncheck bones to remove them"},
    "profile_info": {"es": "Info de perfil", "en": "Profile Info"},
    "allowed_bones": {"es": "Huesos permitidos", "en": "Allowed bones"},
    "max_influences": {"es": "Maximas influencias", "en": "Max influences"},
    "min_weight": {"es": "Peso minimo", "en": "Min weight"},
    "invalid_profile": {"es": "Perfil invalido", "en": "Invalid profile"},
    "transfer_section": {"es": "Transferencia", "en": "Transfer"},
    "transfer_disabled_avatar": {"es": "Transferencia desactivada: define primero un Avatar", "en": "Transfer disabled: set an Avatar first"},
    "transfer_disabled_garment": {"es": "Transferencia desactivada: el objeto activo debe ser una prenda", "en": "Transfer disabled: active object must be a garment mesh"},
    "transfer_disabled_profile": {"es": "Transferencia desactivada: selecciona un perfil valido", "en": "Transfer disabled: select a valid Bone Profile"},
    "auto_smooth_label": {"es": "Auto suavizar y limpiar", "en": "Auto Smooth & Clean"},
    "iter_label": {"es": "Iter", "en": "Iter"},
    "lod_label": {"es": "Reglas LOD automaticas", "en": "Auto LOD Rules"},
    "weight_cleaning": {"es": "Limpieza de pesos", "en": "Weight Cleaning"},
    "auto_clean": {"es": "Limpieza automatica", "en": "Auto Clean"},
    "smooth_clean": {"es": "Suavizar y limpiar", "en": "Smooth & Clean"},
    "clear_all_weights": {"es": "Limpiar todos los pesos", "en": "Clear All Weights"},
    "threshold": {"es": "Umbral", "en": "Threshold"},
    "advanced_tools": {"es": "Herramientas avanzadas", "en": "Advanced Tools"},
    "merge_similar": {"es": "Fusionar similares", "en": "Merge Similar"},
    "select_low_weights": {"es": "Seleccionar pesos bajos", "en": "Select Low Weights"},
    "analyze_weights": {"es": "Analizar pesos", "en": "Analyze Weights"},
    "compensate_weights": {"es": "Compensar pesos", "en": "Compensate Weights"},
    "tools_section": {"es": "Herramientas", "en": "Tools"},
    "weight_paint": {"es": "Pintar pesos", "en": "Weight Paint"},
    "normalize": {"es": "Normalizar", "en": "Normalize"},
    "clean": {"es": "Limpiar", "en": "Clean"},
    "quantize": {"es": "Cuantizar", "en": "Quantize"},
    "steps": {"es": "Pasos", "en": "Steps"},
    "levels": {"es": "Niveles", "en": "Levels"},
    "low": {"es": "Bajo", "en": "Low"},
    "high": {"es": "Alto", "en": "High"},
    "diagnostic": {"es": "Diagnostico", "en": "Diagnostic"},
    "analyze_before": {"es": "Analizar antes de transferir", "en": "Analyze Before Transfer"},
    "analyze_after": {"es": "Analizar despues de transferir", "en": "Analyze After Transfer"},
    "full_scene_analysis": {"es": "Analisis completo de escena", "en": "Full Scene Analysis"},
}


UI_TEXT_KO = {
    "manager_active": "매니저 모드 활성화",
    "manager_loaded": "모델 프로필 속성이 로드됨",
    "manager_missing": "모델 프로필 속성이 누락됨",
    "manager_reload_tip": "애드온을 껐다 켜거나 Blender를 재시작하세요",
    "avatar_section": "아바타",
    "mesh_label": "메시",
    "armature_label": "아마추어",
    "no_avatar": "아바타가 설정되지 않음",
    "avatar_tip": "팁: 아바타 메시를 선택하고 Set Avatar from Selection을 누르세요",
    "garment_section": "의상",
    "active_label": "활성",
    "type_label": "유형",
    "height_label": "높이",
    "select_garment": "의상 메시를 선택하세요",
    "garment_config": "의상 설정",
    "model_label": "모델",
    "weight_profile_label": "웨이트 프로필(본 템플릿)",
    "method_label": "방법",
    "double_pass_label": "2단계 오염 정리",
    "seed_threshold_label": "시드 임계값",
    "profiles_available": "사용 가능한 본 프로필",
    "profiles_unavailable": "본 프로필을 사용할 수 없음",
    "bone_mask_section": "본 마스크(수동 필터)",
    "load_mask_btn": "프로필에서 본 마스크 불러오기",
    "restore_mask_btn": "오브젝트에서 복원",
    "select_all": "전체 선택",
    "deselect_all": "전체 해제",
    "uncheck_tip": "제외할 본은 체크 해제하세요",
    "profile_info": "프로필 정보",
    "allowed_bones": "허용 본",
    "max_influences": "최대 영향 수",
    "min_weight": "최소 가중치",
    "invalid_profile": "잘못된 프로필",
    "transfer_section": "전송",
    "transfer_disabled_avatar": "전송 비활성화: 먼저 아바타를 설정하세요",
    "transfer_disabled_garment": "전송 비활성화: 활성 오브젝트는 의상 메시여야 합니다",
    "transfer_disabled_profile": "전송 비활성화: 유효한 프로필을 선택하세요",
    "auto_smooth_label": "자동 스무딩 및 정리",
    "iter_label": "반복",
    "lod_label": "자동 LOD 규칙",
    "weight_cleaning": "가중치 정리",
    "auto_clean": "자동 정리",
    "smooth_clean": "스무딩 및 정리",
    "clear_all_weights": "모든 가중치 삭제",
    "threshold": "임계값",
    "advanced_tools": "고급 도구",
    "merge_similar": "유사 그룹 병합",
    "select_low_weights": "낮은 가중치 선택",
    "analyze_weights": "가중치 분석",
    "compensate_weights": "가중치 보정",
    "tools_section": "도구",
    "weight_paint": "웨이트 페인트",
    "normalize": "정규화",
    "clean": "정리",
    "quantize": "양자화",
    "steps": "단계",
    "levels": "레벨",
    "low": "낮음",
    "high": "높음",
    "diagnostic": "진단",
    "analyze_before": "전송 전 분석",
    "analyze_after": "전송 후 분석",
    "full_scene_analysis": "전체 씬 분석",
}


def _t(key):
    if _get_ui_language() == "ko" and key in UI_TEXT_KO:
        return UI_TEXT_KO[key]
    return _lang_pick(UI_TEXT.get(key, {"en": key}), default_en=key)


HELP_TOPICS = {
    "avatar_auto_find": {
        "es": "Busca automáticamente la malla de avatar más probable en la escena.",
        "en": "Automatically finds the most likely avatar mesh in the scene.",
    },
    "avatar_set_selected": {
        "es": "Usa la malla seleccionada como avatar de referencia para transferir pesos.",
        "en": "Uses the selected mesh as the reference avatar for weight transfer.",
    },
    "garment_import": {
        "es": "Importa una prenda (FBX) y la prepara para el flujo de transferencia.",
        "en": "Imports a garment (FBX) and prepares it for the transfer workflow.",
    },
    "garment_set_selected": {
        "es": "Usa la malla seleccionada como prenda activa para transferir pesos.",
        "en": "Uses the selected mesh as the active garment for weight transfer.",
    },
    "garment_model": {
        "es": "Clasifica la prenda por tipo visual. Ayuda a organizar y reutilizar perfiles.",
        "en": "Classifies the garment by visual type to help organize and reuse profiles.",
    },
    "weight_profile": {
        "es": "Plantilla de huesos permitidos. Define qué grupos pueden recibir peso.",
        "en": "Allowed-bones template. Defines which groups can receive weights.",
    },
    "transfer_method": {
        "es": "Método geométrico de transferencia. 'Nearest Face Interpolated' suele ser más suave; 'Nearest Vertex' más rígido y robusto.",
        "en": "Geometric transfer method. 'Nearest Face Interpolated' is usually smoother; 'Nearest Vertex' is stricter and more robust.",
    },
    "double_pass": {
        "es": "Realiza doble pasada: detecta vértices útiles, limpia y repesa para reducir contaminación.",
        "en": "Runs a double pass: detects useful vertices, cleans, and reweights to reduce contamination.",
    },
    "seed_threshold": {
        "es": "Umbral para detectar vértices semilla en la primera pasada. Más bajo = más vértices incluidos.",
        "en": "Threshold for seed vertices in pass one. Lower value = more vertices included.",
    },
    "load_bone_mask": {
        "es": "Carga la lista de huesos del perfil para activar/desactivar qué huesos intervienen.",
        "en": "Loads the profile bone list so you can enable/disable participating bones.",
    },
    "restore_bone_mask": {
        "es": "Restaura la máscara de huesos guardada en la prenda activa.",
        "en": "Restores the saved bone mask from the active garment.",
    },
    "transfer_weights": {
        "es": "Ejecuta la transferencia completa con limpieza, filtrado por perfil y normalización.",
        "en": "Runs full transfer with cleanup, profile filtering, and normalization.",
    },
    "auto_smooth": {
        "es": "Suaviza y limpia pesos automáticamente después de transferir.",
        "en": "Automatically smooths and cleans weights after transfer.",
    },
    "lod_rules": {
        "es": "Aplica reglas automáticas de LOD en mallas LOD0/LOD1/LOD2 detectadas.",
        "en": "Applies automatic LOD rules to detected LOD0/LOD1/LOD2 meshes.",
    },
}

HELP_TOPICS_KO = {
    "avatar_auto_find": "씬에서 가장 가능성이 높은 아바타 메시를 자동으로 찾습니다.",
    "avatar_set_selected": "선택한 메시를 가중치 전송용 기준 아바타로 사용합니다.",
    "garment_import": "의상(FBX)을 가져와 전송 워크플로우에 맞게 준비합니다.",
    "garment_set_selected": "선택한 메시를 활성 의상으로 설정합니다.",
    "garment_model": "의상 유형을 분류하여 프로필 관리/재사용을 돕습니다.",
    "weight_profile": "허용 본 템플릿으로, 어떤 그룹이 가중치를 받을지 정의합니다.",
    "transfer_method": "전송 방법입니다. 보통 Face Interpolated가 부드럽고, Nearest Vertex가 엄격합니다.",
    "double_pass": "2단계 전송으로 유효 정점 탐지 후 재전송하여 오염을 줄입니다.",
    "seed_threshold": "1차 패스에서 시드 정점을 판별하는 임계값입니다.",
    "load_bone_mask": "프로필의 본 목록을 불러와 참여 본을 켜고 끕니다.",
    "restore_bone_mask": "활성 의상에 저장된 본 마스크를 복원합니다.",
    "transfer_weights": "정리, 필터링, 정규화를 포함한 전체 전송을 실행합니다.",
    "auto_smooth": "전송 후 자동으로 스무딩 및 정리를 수행합니다.",
    "lod_rules": "감지된 LOD0/1/2 메시에 자동 LOD 규칙을 적용합니다.",
}

# PureQ Avatar bone names for reference
from .PureQ_bones import PureQ_AVATAR_BONES

class PureQ_OT_load_avatar(bpy.types.Operator):
    """Load avatar object with weighted bones only"""
    bl_idname = "pureq.load_avatar"
    bl_label = "Load Avatar"
    bl_description = "Load avatar FBX and keep only weighted bones"

    filepath: StringProperty(subtype="FILE_PATH")
    use_PureQ_bone_validation: BoolProperty(
        name="Use PureQ Bone Validation",
        description="Filter bones based on PureQ avatar bone names",
        default=False
    )

    def execute(self, context):
        global avatar_object

        # Import FBX file
        if self.filepath and self.filepath.endswith('.fbx'):
            bpy.ops.import_scene.fbx(filepath=self.filepath)

            # Find the imported armature/mesh pair
            found_pair = False
            for obj in bpy.context.selected_objects:
                if obj.type == 'ARMATURE':
                    avatar_armature = obj
                    avatar_mesh = None

                    # Find the mesh parented to the armature
                    for child in avatar_armature.children:
                        if child.type == 'MESH':
                            avatar_mesh = child
                            break

                    if avatar_mesh:
                        # Clean up the armature to keep only bones with vertex groups
                        # DISABLED: Do not modify avatar armature structure, it breaks the rig hierarchy
                        # self.cleanup_armature(avatar_armature, avatar_mesh)

                        # Optionally validate against PureQ bone names
                        scene = context.scene
                        if scene.PureQ_use_PureQ_validation:
                            bone_count = self.validate_avatar_bones(avatar_armature)
                            self.report({'INFO'}, f"Avatar bones filtered to PureQ standard: {bone_count} bones kept")

                        avatar_object = avatar_mesh
                        self.report({'INFO'}, f"Avatar loaded: {avatar_mesh.name}")
                        found_pair = True
                        break

            # Fallback: choose any selected mesh with detectable armature association.
            if not found_pair:
                for obj in bpy.context.selected_objects:
                    if obj.type != 'MESH':
                        continue
                    avatar_armature = get_armature_for_mesh(obj)
                    if avatar_armature:
                        scene = context.scene
                        if scene.PureQ_use_PureQ_validation:
                            bone_count = self.validate_avatar_bones(avatar_armature)
                            self.report({'INFO'}, f"Avatar bones filtered to PureQ standard: {bone_count} bones kept")
                        avatar_object = obj
                        self.report({'INFO'}, f"Avatar loaded: {obj.name}")
                        found_pair = True
                        break

            if not found_pair:
                self.report({'ERROR'}, "No valid avatar mesh found in imported FBX")
                return {'CANCELLED'}
        else:
            # Use selected object as avatar if no file is specified
            if context.active_object and context.active_object.type == 'MESH':
                avatar_mesh = context.active_object
                avatar_armature = get_armature_for_mesh(avatar_mesh)

                if avatar_armature:
                    # Clean up the armature to keep only bones with vertex groups
                    # DISABLED: Do not modify avatar armature structure
                    # self.cleanup_armature(avatar_armature, avatar_mesh)

                    # Optionally validate against PureQ bone names
                    scene = context.scene
                    if scene.PureQ_use_PureQ_validation:
                        bone_count = self.validate_avatar_bones(avatar_armature)
                        self.report({'INFO'}, f"Avatar bones filtered to PureQ standard: {bone_count} bones kept")

                    avatar_object = avatar_mesh
                    self.report({'INFO'}, f"Avatar set from selection: {avatar_mesh.name}")
                else:
                    self.report({'ERROR'}, "Selected object has no armature association (modifier/parent)")
                    return {'CANCELLED'}

        return {'FINISHED'}

class PureQ_OT_find_avatar_by_name(bpy.types.Operator):
    """Find and set avatar object by common names"""
    bl_idname = "pureq.find_avatar_by_name"
    bl_label = "Find Avatar by Name"
    bl_description = "Automatically find avatar by common names (Female, Male, Child, etc.)"

    def cleanup_armature(self, armature, mesh):
        """Remove bones that don't have corresponding vertex groups in the mesh"""
        # Store original state
        original_mode = bpy.context.object.mode
        original_active = bpy.context.view_layer.objects.active
        original_selected = bpy.context.selected_objects[:]

        try:
            # Switch to edit mode to modify bones
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.select_all(action='DESELECT')
            armature.select_set(True)
            bpy.context.view_layer.objects.active = armature

            # Only try to enter edit mode if we're in object mode
            if original_mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            else:
                # If already in edit mode, ensure the right object is in edit mode
                if bpy.context.mode != 'EDIT_ARMATURE':
                    bpy.ops.object.mode_set(mode='EDIT')

            # Get all vertex group names
            vertex_group_names = {vg.name for vg in mesh.vertex_groups}

            # Remove unused bones (only if they don't have any vertex assignments)
            edit_bones = armature.data.edit_bones
            bones_to_remove = []

            for bone in edit_bones:
                # Check if this bone name exists in vertex groups
                if bone.name not in vertex_group_names:
                    bones_to_remove.append(bone.name)

            # Only remove bones that have no vertex group (to avoid removing bones that might be needed for hierarchy)
            for bone_name in bones_to_remove:
                if bone_name in edit_bones:  # Check if bone still exists before removing
                    # Additional check: see if this bone has any influence on any vertices
                    has_influence = False
                    for vertex in mesh.data.vertices:
                        for group in vertex.groups:
                            if group.group < len(mesh.vertex_groups):
                                vg_name = mesh.vertex_groups[group.group].name
                                if vg_name == bone_name:
                                    has_influence = True
                                    break
                        if has_influence:
                            break

                    if not has_influence:
                        edit_bones.remove(edit_bones[bone_name])

            # Also remove unused vertex groups from the mesh to match
            vertex_groups_to_remove = []
            for vg in mesh.vertex_groups:
                if vg.name not in [eb.name for eb in armature.data.bones]:
                    vertex_groups_to_remove.append(vg)

            for vg in vertex_groups_to_remove:
                mesh.vertex_groups.remove(vg)

        except Exception as e:
            print(f"Error in cleanup_armature: {e}")
        finally:
            # Restore original state safely
            try:
                # Only try to exit edit mode if we're currently in it
                if bpy.context.mode == 'EDIT_ARMATURE':
                    bpy.ops.object.mode_set(mode='OBJECT')
                elif original_mode == 'EDIT_MESH' and bpy.context.mode == 'EDIT':
                    bpy.ops.object.mode_set(mode='OBJECT')

                # Restore original active object and selection
                bpy.context.view_layer.objects.active = original_active
                bpy.ops.object.select_all(action='DESELECT')
                for obj in original_selected:
                    if obj.name in bpy.data.objects:
                        obj.select_set(True)
            except:
                # If restoration fails, at least try to exit edit mode
                try:
                    if bpy.context.mode.startswith('EDIT'):
                        bpy.ops.object.mode_set(mode='OBJECT')
                except:
                    pass

    def validate_avatar_bones(self, armature):
        """Validate and filter bones based on PureQ avatar bone names"""
        # Get all bones in the armature
        bones_to_keep = []

        # Check which bones match the PureQ avatar bone names
        for bone in armature.data.bones:
            if bone.name in PureQ_AVATAR_BONES:
                bones_to_keep.append(bone.name)

        # Store original state
        original_mode = bpy.context.object.mode
        original_active = bpy.context.view_layer.objects.active
        original_selected = bpy.context.selected_objects[:]

        try:
            # Switch to edit mode to modify bones
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.select_all(action='DESELECT')
            armature.select_set(True)
            bpy.context.view_layer.objects.active = armature

            # Only try to enter edit mode if we're in object mode
            if original_mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            else:
                # If already in edit mode, ensure the right object is in edit mode
                if bpy.context.mode != 'EDIT_ARMATURE':
                    bpy.ops.object.mode_set(mode='EDIT')

            # Remove bones that are not in the PureQ list
            edit_bones = armature.data.edit_bones
            bones_to_remove = []

            for bone in edit_bones:
                if bone.name not in bones_to_keep:
                    bones_to_remove.append(bone.name)

            for bone_name in bones_to_remove:
                if bone_name in edit_bones:  # Check if bone still exists before removing
                    edit_bones.remove(edit_bones[bone_name])

        except Exception as e:
            print(f"Error in validate_avatar_bones: {e}")
        finally:
            # Restore original state safely
            try:
                # Only try to exit edit mode if we're currently in it
                if bpy.context.mode == 'EDIT_ARMATURE':
                    bpy.ops.object.mode_set(mode='OBJECT')
                elif original_mode == 'EDIT_MESH' and bpy.context.mode == 'EDIT':
                    bpy.ops.object.mode_set(mode='OBJECT')

                # Restore original active object and selection
                bpy.context.view_layer.objects.active = original_active
                bpy.ops.object.select_all(action='DESELECT')
                for obj in original_selected:
                    if obj.name in bpy.data.objects:
                        obj.select_set(True)
            except:
                # If restoration fails, at least try to exit edit mode
                try:
                    if bpy.context.mode.startswith('EDIT'):
                        bpy.ops.object.mode_set(mode='OBJECT')
                except:
                    pass

        return len(bones_to_keep)

    def execute(self, context):
        global avatar_object

        # 1) Prefer active mesh if it is already a valid avatar candidate.
        found_avatar = None
        active_obj = context.active_object
        if active_obj and active_obj.type == 'MESH' and get_armature_for_mesh(active_obj):
            found_avatar = active_obj

        # 2) Fallback: search best candidate in scene.
        if not found_avatar:
            candidates = get_avatar_candidate_meshes()
            if candidates:
                found_avatar = candidates[0]

        if found_avatar:
            avatar_mesh = found_avatar
            avatar_armature = get_armature_for_mesh(avatar_mesh)

            if avatar_armature:
                # Optionally validate against PureQ bone names
                scene = context.scene
                if scene.PureQ_use_PureQ_validation:
                    bone_count = self.validate_avatar_bones(avatar_armature)
                    self.report({'INFO'}, f"Avatar bones filtered to PureQ standard: {bone_count} bones kept")

                avatar_object = avatar_mesh
                self.report({'INFO'}, f"Avatar automatically found and set: {avatar_mesh.name}")
            else:
                self.report({'ERROR'}, f"Found object '{avatar_mesh.name}' but no armature association was found")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, "No valid avatar mesh found (needs armature modifier or armature parenting)")
            return {'CANCELLED'}

        return {'FINISHED'}

class PureQ_OT_set_avatar_from_selection(bpy.types.Operator):
    """Set the selected object as avatar"""
    bl_idname = "pureq.set_avatar_from_selection"
    bl_label = "Set Avatar from Selection"
    bl_description = "Use the currently selected object as avatar"

    def execute(self, context):
        global avatar_object

        if context.active_object and context.active_object.type == 'MESH':
            avatar_mesh = context.active_object
            avatar_armature = get_armature_for_mesh(avatar_mesh)

            if avatar_armature:
                # Store current mode to restore later
                original_mode = context.mode

                # Only validate against PureQ bone names, don't clean up the avatar armature here
                # The cleanup_armature should only be used for garments during weight transfer
                scene = context.scene
                if scene.PureQ_use_PureQ_validation:
                    bone_count = self.validate_avatar_bones(avatar_armature)
                    self.report({'INFO'}, f"Avatar bones filtered to PureQ standard: {bone_count} bones kept")

                avatar_object = avatar_mesh
                self.report({'INFO'}, f"Avatar set from selection: {avatar_mesh.name}")

                # Restore original mode if needed
                # bpy.ops.object.mode_set(mode=original_mode)  # Only if different from OBJECT
            else:
                self.report({'ERROR'}, "Selected object has no armature association (modifier/parent)")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, "Please select a mesh object")
            return {'CANCELLED'}

        return {'FINISHED'}

    def cleanup_armature(self, armature, mesh):
        """Remove bones that don't have corresponding vertex groups in the mesh"""
        # Store original state
        original_mode = bpy.context.object.mode
        original_active = bpy.context.view_layer.objects.active
        original_selected = bpy.context.selected_objects[:]

        try:
            # Switch to edit mode to modify bones
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.select_all(action='DESELECT')
            armature.select_set(True)
            bpy.context.view_layer.objects.active = armature

            # Only try to enter edit mode if we're in object mode
            if original_mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            else:
                # If already in edit mode, ensure the right object is in edit mode
                if bpy.context.mode != 'EDIT_ARMATURE':
                    bpy.ops.object.mode_set(mode='EDIT')

            # Get all vertex group names
            vertex_group_names = {vg.name for vg in mesh.vertex_groups}

            # Remove unused bones (only if they don't have any vertex assignments)
            edit_bones = armature.data.edit_bones
            bones_to_remove = []

            for bone in edit_bones:
                # Check if this bone name exists in vertex groups
                if bone.name not in vertex_group_names:
                    bones_to_remove.append(bone.name)

            # Only remove bones that have no vertex group (to avoid removing bones that might be needed for hierarchy)
            for bone_name in bones_to_remove:
                if bone_name in edit_bones:  # Check if bone still exists before removing
                    # Additional check: see if this bone has any influence on any vertices
                    has_influence = False
                    for vertex in mesh.data.vertices:
                        for group in vertex.groups:
                            if group.group < len(mesh.vertex_groups):
                                vg_name = mesh.vertex_groups[group.group].name
                                if vg_name == bone_name:
                                    has_influence = True
                                    break
                        if has_influence:
                            break

                    if not has_influence:
                        edit_bones.remove(edit_bones[bone_name])

            # Also remove unused vertex groups from the mesh to match
            vertex_groups_to_remove = []
            for vg in mesh.vertex_groups:
                if vg.name not in [eb.name for eb in armature.data.bones]:
                    vertex_groups_to_remove.append(vg)

            for vg in vertex_groups_to_remove:
                mesh.vertex_groups.remove(vg)

        except Exception as e:
            print(f"Error in cleanup_armature: {e}")
        finally:
            # Restore original state safely
            try:
                # Only try to exit edit mode if we're currently in it
                if bpy.context.mode == 'EDIT_ARMATURE':
                    bpy.ops.object.mode_set(mode='OBJECT')
                elif original_mode == 'EDIT_MESH' and bpy.context.mode == 'EDIT':
                    bpy.ops.object.mode_set(mode='OBJECT')

                # Restore original active object and selection
                bpy.context.view_layer.objects.active = original_active
                bpy.ops.object.select_all(action='DESELECT')
                for obj in original_selected:
                    if obj.name in bpy.data.objects:
                        obj.select_set(True)
            except:
                # If restoration fails, at least try to exit edit mode
                try:
                    if bpy.context.mode.startswith('EDIT'):
                        bpy.ops.object.mode_set(mode='OBJECT')
                except:
                    pass

    def validate_avatar_bones(self, armature):
        """Validate and filter bones based on PureQ avatar bone names"""
        # Get all bones in the armature
        bones_to_keep = []

        # Check which bones match the PureQ avatar bone names
        for bone in armature.data.bones:
            if bone.name in PureQ_AVATAR_BONES:
                bones_to_keep.append(bone.name)

        # Store original state
        original_mode = bpy.context.object.mode
        original_active = bpy.context.view_layer.objects.active
        original_selected = bpy.context.selected_objects[:]

        try:
            # Switch to edit mode to modify bones
            bpy.context.view_layer.objects.active = armature
            bpy.ops.object.select_all(action='DESELECT')
            armature.select_set(True)
            bpy.context.view_layer.objects.active = armature

            # Only try to enter edit mode if we're in object mode
            if original_mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            else:
                # If already in edit mode, ensure the right object is in edit mode
                if bpy.context.mode != 'EDIT_ARMATURE':
                    bpy.ops.object.mode_set(mode='EDIT')

            # Remove bones that are not in the PureQ list
            edit_bones = armature.data.edit_bones
            bones_to_remove = []

            for bone in edit_bones:
                if bone.name not in bones_to_keep:
                    bones_to_remove.append(bone.name)

            for bone_name in bones_to_remove:
                if bone_name in edit_bones:  # Check if bone still exists before removing
                    edit_bones.remove(edit_bones[bone_name])

        except Exception as e:
            print(f"Error in validate_avatar_bones: {e}")
        finally:
            # Restore original state safely
            try:
                # Only try to exit edit mode if we're currently in it
                if bpy.context.mode == 'EDIT_ARMATURE':
                    bpy.ops.object.mode_set(mode='OBJECT')
                elif original_mode == 'EDIT_MESH' and bpy.context.mode == 'EDIT':
                    bpy.ops.object.mode_set(mode='OBJECT')

                # Restore original active object and selection
                bpy.context.view_layer.objects.active = original_active
                bpy.ops.object.select_all(action='DESELECT')
                for obj in original_selected:
                    if obj.name in bpy.data.objects:
                        obj.select_set(True)
            except:
                # If restoration fails, at least try to exit edit mode
                try:
                    if bpy.context.mode.startswith('EDIT'):
                        bpy.ops.object.mode_set(mode='OBJECT')
                except:
                    pass

        return len(bones_to_keep)

# Define clothing types enum
CLOTHING_TYPES = [
    ('SHORT_SKIRT', 'Short Skirt', 'A short skirt'),
    ('MEDIUM_SKIRT', 'Medium Skirt', 'A medium length skirt'),
    ('LONG_SKIRT', 'Long Skirt', 'A long skirt'),
    ('TROUSERS', 'Trousers', 'Trousers/pants'),
    ('SHIRT', 'Shirt', 'Shirt/top'),
    ('JACKET', 'Jacket', 'Jacket/coat'),
    ('CUSTOM', 'Custom', 'Custom clothing item'),
]

class PureQ_OT_load_clothing(bpy.types.Operator):
    """Load clothing object"""
    bl_idname = "pureq.load_clothing"
    bl_label = "Load Clothing"
    bl_description = "Load clothing FBX file"

    filepath: StringProperty(subtype="FILE_PATH")
    clothing_type: EnumProperty(
        name="Clothing Type",
        description="Select the type of clothing being loaded",
        items=CLOTHING_TYPES,
        default='CUSTOM'
    )

    filter_glob: StringProperty(
        default="*.fbx",
        options={'HIDDEN'},
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        global clothing_objects

        # Import FBX file
        if self.filepath and self.filepath.endswith('.fbx'):
            # Auto-detect type from filename if currently CUSTOM
            detected_type = self.clothing_type
            if self.clothing_type == 'CUSTOM':
                fname = os.path.basename(self.filepath).lower()
                if 'mini' in fname or 'short' in fname: detected_type = 'SHORT_SKIRT'
                elif 'maxi' in fname or 'long' in fname: detected_type = 'LONG_SKIRT'
                elif 'skirt' in fname or 'midi' in fname: detected_type = 'MEDIUM_SKIRT'
                elif any(k in fname for k in ['pant', 'trouser', 'jean', 'legging']): detected_type = 'TROUSERS'
                elif any(k in fname for k in ['jacket', 'coat', 'blazer', 'hoodie']): detected_type = 'JACKET'
                elif any(k in fname for k in ['shirt', 'top', 'blouse', 'tee']): detected_type = 'SHIRT'

            bpy.ops.import_scene.fbx(filepath=self.filepath)

            imported_clothing_obj = None
            # Find the imported clothing mesh
            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH' and obj != avatar_object:
                    # Store clothing type as custom property
                    obj['PureQ_clothing_type'] = detected_type
                    clothing_objects.append(obj)
                    imported_clothing_obj = obj
                    
                    type_label = detected_type.replace('_', ' ').title()
                    if detected_type != self.clothing_type:
                        self.report({'INFO'}, f"Auto-detected {type_label} from file: {obj.name}")
                    else:
                        self.report({'INFO'}, f"{type_label} loaded: {obj.name}")
                    break

            # Make imported garment active so transfer workflow is ready.
            if imported_clothing_obj and imported_clothing_obj.name in bpy.data.objects:
                bpy.ops.object.select_all(action='DESELECT')
                imported_clothing_obj.select_set(True)
                context.view_layer.objects.active = imported_clothing_obj
        else:
            # Use selected object as clothing if no file is specified
            if context.active_object and context.active_object.type == 'MESH' and context.active_object != avatar_object:
                clothing_obj = context.active_object
                # Store clothing type as custom property
                clothing_obj['PureQ_clothing_type'] = self.clothing_type
                clothing_objects.append(clothing_obj)
                self.report({'INFO'}, f"{self.clothing_type.replace('_', ' ').title()} set from selection: {clothing_obj.name}")
            else:
                self.report({'ERROR'}, "Please select a mesh object that is not the avatar")
                return {'CANCELLED'}

        return {'FINISHED'}

class PureQ_OT_set_clothing_from_selection(bpy.types.Operator):
    """Set the selected object as clothing"""
    bl_idname = "pureq.set_clothing_from_selection"
    bl_description = "Use the currently selected object as clothing"
    bl_label = "Set Clothing from Selection"

    clothing_type: EnumProperty(
        name="Clothing Type",
        description="Select the type of clothing being loaded",
        items=CLOTHING_TYPES,
        default='CUSTOM'
    )

    def execute(self, context):
        global clothing_objects

        if context.active_object and context.active_object.type == 'MESH' and context.active_object != avatar_object:
            clothing_obj = context.active_object
            
            # Auto-detect from object name if CUSTOM
            detected_type = self.clothing_type
            if self.clothing_type == 'CUSTOM':
                name = clothing_obj.name.lower()
                if 'mini' in name or 'short' in name: detected_type = 'SHORT_SKIRT'
                elif 'maxi' in name or 'long' in name: detected_type = 'LONG_SKIRT'
                elif 'skirt' in name or 'midi' in name: detected_type = 'MEDIUM_SKIRT'
                elif any(k in name for k in ['pant', 'trouser', 'jean', 'legging']): detected_type = 'TROUSERS'
                elif any(k in name for k in ['jacket', 'coat', 'blazer', 'hoodie']): detected_type = 'JACKET'
                elif any(k in name for k in ['shirt', 'top', 'blouse', 'tee']): detected_type = 'SHIRT'

            # Store clothing type as custom property
            clothing_obj['PureQ_clothing_type'] = detected_type
            clothing_objects.append(clothing_obj)
            
            type_label = detected_type.replace('_', ' ').title()
            self.report({'INFO'}, f"{type_label} set from selection: {clothing_obj.name}")
        else:
            self.report({'ERROR'}, "Please select a mesh object that is not the avatar")
            return {'CANCELLED'}

        return {'FINISHED'}

class PureQBoneItem(PropertyGroup):
    """Item for the bone list UI"""
    name: StringProperty(name="Bone Name")
    enabled: BoolProperty(name="Enabled", default=True)

class PUREQ_UL_bone_list(bpy.types.UIList):
    """UI List for displaying and filtering bones"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "enabled", text="")
            layout.label(text=item.name, icon='BONE_DATA')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='BONE_DATA')

class PureQ_OT_bone_list_actions(bpy.types.Operator):
    """Select or Deselect all bones in the list"""
    bl_idname = "pureq.bone_list_actions"
    bl_label = "Bone List Actions"

    action: EnumProperty(
        items=[
            ('SELECT_ALL', "Select All", "Select all bones"),
            ('DESELECT_ALL', "Deselect All", "Deselect all bones"),
        ]
    )

    def execute(self, context):
        scene = context.scene
        for item in scene.PureQ_bone_list:
            if self.action == 'SELECT_ALL':
                item.enabled = True
            elif self.action == 'DESELECT_ALL':
                item.enabled = False
        return {'FINISHED'}

class PureQ_OT_load_bones_from_object(bpy.types.Operator):
    """Load the saved bone list from the active object"""
    bl_idname = "pureq.load_bones_from_object"
    bl_label = "Load Saved Bones"
    bl_description = "Restore the bone list used previously on this object"

    @classmethod
    def poll(cls, context):
        return context.active_object and "PureQ_saved_bones" in context.active_object

    def execute(self, context):
        obj = context.active_object
        scene = context.scene

        # Get saved list
        saved_bones = obj["PureQ_saved_bones"]
        # Handle Blender IDPropertyArray if necessary
        if hasattr(saved_bones, "to_list"):
            saved_bones = saved_bones.to_list()
        saved_set = set(saved_bones)

        # Clear and populate UI list
        scene.PureQ_bone_list.clear()

        # Load all bones from current profile to show context, but enable only saved ones
        # This allows the user to re-enable bones they previously disabled
        bpy.ops.pureq.refresh_profile_bones()

        for item in scene.PureQ_bone_list:
            item.enabled = (item.name in saved_set)

        self.report({'INFO'}, f"Restored configuration from {obj.name}")
        return {'FINISHED'}

class PureQ_OT_refresh_profile_bones(bpy.types.Operator):
    """Load bones from the selected profile into the UI list"""
    bl_idname = "pureq.refresh_profile_bones"
    bl_label = "Load Profile Bones"
    bl_description = "Populate the list below with bones from the selected profile"

    def execute(self, context):
        scene = context.scene
        profile_name = scene.PureQ_bone_profile

        # Clear existing list
        scene.PureQ_bone_list.clear()

        if not profile_name or profile_name == "NONE":
            self.report({'WARNING'}, "Select a Bone Profile first (or use Model Profile workflow).")
            return {'CANCELLED'}

        from .core.bone_profiles import get_bone_profile
        profile = get_bone_profile(profile_name)

        if not profile:
            self.report({'WARNING'}, f"Profile {profile_name} not found or empty")
            return {'CANCELLED'}

        allowed = profile.get("allowed_bones", set())

        # Add bones to list
        # Sort alphabetically for better UX
        for bone_name in sorted(list(allowed)):
            item = scene.PureQ_bone_list.add()
            item.name = bone_name
            item.enabled = True

        self.report({'INFO'}, f"Loaded {len(allowed)} bones from profile {profile_name}")
        return {'FINISHED'}

class PureQ_OT_transfer_weights(bpy.types.Operator):
    """Transfer weights from avatar to clothing"""
    bl_idname = "pureq.transfer_weights"
    bl_label = "Transfer Weights"
    bl_description = "Transfer weights from avatar to selected clothing"

    def execute(self, context):
        global avatar_object
        print("\n=== DIAGNOSTIC: STARTING WEIGHT TRANSFER ===")

        # Run diagnostic before transfer
        bpy.ops.pureq.diagnostic_analyzer(action="before_transfer")

        # Clean up any invalid object references
        cleanup_object_references()

        # Check if avatar object still exists
        if not avatar_object or avatar_object.name not in bpy.data.objects:
            # Attempt auto-recovery to reduce workflow friction.
            candidates = get_avatar_candidate_meshes()
            if candidates:
                avatar_object = candidates[0]
            else:
                self.report({'ERROR'}, "Avatar object no longer exists in the scene")
                return {'CANCELLED'}

        # Check if avatar has vertex groups to transfer
        if not avatar_object.vertex_groups:
            self.report({'ERROR'}, f"Avatar '{avatar_object.name}' has no vertex groups! Cannot transfer weights.")
            return {'CANCELLED'}

        # Get selected clothing object
        active_obj = context.active_object
        if not active_obj or active_obj.type != 'MESH' or active_obj == avatar_object or active_obj.name == avatar_object.name:
            self.report({'ERROR'}, "Please select a clothing object")
            return {'CANCELLED'}

        scene = context.scene

        # Resolve effective profile with clear priority:
        # 1) Model Profile data (Profile Manager)
        # 2) Bone Profile dropdown
        profile, profile_source, profile_name = _resolve_transfer_profile(scene, active_obj=active_obj)

        if not profile:
            self.report({'ERROR'}, "No valid transfer source found. Choose Model Profile, Bone Profile, or select bones in Bone Mask.")
            return {'CANCELLED'}

        if profile_source == "model":
            self.report({'INFO'}, f"Using Model Profile for transfer: {profile_name}")
        elif profile_source == "manual":
            self.report({'INFO'}, "Using one-shot manual bone mask (no saved profile).")
        else:
            self.report({'INFO'}, f"Using Bone Profile for transfer: {profile_name}")

        # DEBUG: Print vertex groups in avatar and allowed bones in profile
        print("Vertex groups in avatar:", sorted([vg.name for vg in avatar_object.vertex_groups]))
        print("Allowed bones in profile:", sorted(profile.get("allowed_bones", set())))

        # Get the avatar's armature
        avatar_armature = get_armature_for_mesh(avatar_object)

        if not avatar_armature:
            self.report({'ERROR'}, "Avatar object has no armature association (modifier/parent)")
            return {'CANCELLED'}

        # Ensure the clothing object is parented to the armature
        if active_obj.parent != avatar_armature:
            # Keep transform when parenting to avoid "disappearing" mesh due to scale inheritance
            mat = active_obj.matrix_world.copy()
            active_obj.parent = avatar_armature
            active_obj.matrix_world = mat

        # Ensure avatar is visible for data transfer (prevents empty transfer issues)
        original_hide_viewport = avatar_object.hide_viewport
        avatar_object.hide_viewport = False

        # Store configuration in the clothing object for reproducibility
        active_obj["PureQ_profile"] = profile_name
        active_obj["PureQ_profile_source"] = profile_source or "bone"
        if profile_source == "model":
            active_obj["PureQ_model_profile"] = profile_name
        active_obj["PureQ_model"] = scene.PureQ_garment_model

        # Temporarily disable any existing armature modifiers during transfer to avoid mesh deformation
        for mod in active_obj.modifiers:
            if mod.type == 'ARMATURE':
                mod.show_viewport = False
                mod.show_render = False

        # --- FINAL STRATEGY: Replicate the robust manual operator workflow ---

        # 1. Clear existing groups
        active_obj.vertex_groups.clear()

        # 2. Create Empty Groups (Mimic "Parent with Empty Groups")
        # This ensures target groups exist and match by name.
        # Only create groups for bones that are allowed in the profile
        allowed_bones = set()

        # Check if UI list has items
        if len(scene.PureQ_bone_list) > 0:
            for item in scene.PureQ_bone_list:
                if item.enabled:
                    allowed_bones.add(item.name)
        else:
            # Fallback to JSON profile directly if user didn't load the list
            allowed_bones = profile.get("allowed_bones", set())

        # Create vertex groups for allowed bones
        for bone_name in allowed_bones:
            if bone_name not in active_obj.vertex_groups:
                active_obj.vertex_groups.new(name=bone_name)

        # If no allowed bones are defined, create all avatar groups as fallback
        if not allowed_bones:
            for vg in avatar_object.vertex_groups:
                if vg.name not in active_obj.vertex_groups:
                    active_obj.vertex_groups.new(name=vg.name)

        # 3. Use Data Transfer Modifier with explicit 'NAME' mapping
        # This is the most robust method for scripts, avoiding context issues of operators.

        # Ensure Object Mode
        if active_obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Debug: Check positions of objects before transfer
        print(f"Avatar location: {avatar_object.location}")
        print(f"Clothing location: {active_obj.location}")
        print(f"Avatar scale: {avatar_object.scale}")
        print(f"Clothing scale: {active_obj.scale}")

        # Check if there's a significant scale difference that might affect transfer
        avatar_scale_avg = sum(avatar_object.scale) / 3
        clothing_scale_avg = sum(active_obj.scale) / 3
        scale_ratio = clothing_scale_avg / avatar_scale_avg

        if scale_ratio < 0.1 or scale_ratio > 10:
            self.report({'WARNING'}, f"Scale difference detected ({scale_ratio:.2f}). Proceeding anyway.")
            print(f"WARNING: Scale ratio is {scale_ratio:.3f}")

        # Proceed with normal transfer regardless of scale
        has_weights = _apply_data_transfer_weights(active_obj, avatar_object, scene.PureQ_transfer_method)

        print(f"Has weights after first transfer: {has_weights}")

        # Fallback if no weights and using Poly Interp
        if not has_weights:
            self.report({'WARNING'}, "Standard transfer produced no weights. Retrying with Nearest Vertex...")

            has_weights = _apply_data_transfer_weights(active_obj, avatar_object, 'NEAREST')

            print(f"Has weights after fallback transfer: {has_weights}")

        # Restore avatar visibility
        avatar_object.hide_viewport = original_hide_viewport

        # 4. STRICT FILTERING (The "Mask") - This part remains the same
        # Get allowed bones from the UI List (user checked items)
        # If list is empty, fallback to the profile's default allowed list

        allowed_bones = set()

        # Check if UI list has items
        if len(scene.PureQ_bone_list) > 0:
            for item in scene.PureQ_bone_list:
                if item.enabled:
                    allowed_bones.add(item.name)

            if not allowed_bones:
                self.report({'WARNING'}, "No bones selected in list! All weights will be removed.")
            self.report({'INFO'}, f"Using {len(allowed_bones)} bones from Manual Selection")
        else:
            # Fallback to JSON profile directly if user didn't load the list
            allowed_bones = profile.get("allowed_bones", set())
            self.report({'INFO'}, f"Using {len(allowed_bones)} bones from JSON Profile")

        # Save allowed_bones to object for future reference (Persistence)
        # Convert to list for storage
        active_obj["PureQ_saved_bones"] = list(allowed_bones)

        # Debug: Print all vertex groups before filtering
        all_groups_before = [vg.name for vg in active_obj.vertex_groups]
        print(f"All vertex groups before filtering: {all_groups_before}")
        print(f"Avatar vertex groups: {[vg.name for vg in avatar_object.vertex_groups]}")
        print(f"Profile allowed bones: {allowed_bones}")
        print(f"Profile allowed bones (lowercase): {{b.lower() for b in allowed_bones}}")

        # 4. Remove any vertex group NOT in the allowed list
        groups_to_remove = []
        groups_to_keep = []

        # Fix: Case-insensitive matching to handle Avatar vs Profile naming differences
        allowed_bones_lower = {b.lower() for b in allowed_bones}

        for vg in active_obj.vertex_groups:
            if vg.name not in allowed_bones and vg.name.lower() not in allowed_bones_lower:
                groups_to_remove.append(vg)
                print(f"Marking for removal: {vg.name}")
            else:
                groups_to_keep.append(vg)
                print(f"Marking for keeping: {vg.name}")

        print(f"Groups to remove: {[vg.name for vg in groups_to_remove]}")
        print(f"Groups to keep: {[vg.name for vg in groups_to_keep]}")
        print(f"Allowed bones: {allowed_bones}")

        for vg in groups_to_remove:
            active_obj.vertex_groups.remove(vg)

        # Debug: Print remaining vertex groups after filtering
        remaining_groups = [vg.name for vg in active_obj.vertex_groups]
        print(f"Remaining vertex groups after filtering: {remaining_groups}")

        # Optional ultra-clean two-pass workflow:
        # 1) detect vertices that truly belong to the garment
        # 2) clear all current weights in kept groups
        # 3) transfer again
        # 4) keep weights only on detected garment vertices
        profile_min_weight = profile.get("min_weight", 0.001) if profile else 0.001
        use_double_pass = bool(getattr(scene, "PureQ_enable_double_pass_clean", True))
        seed_threshold = float(getattr(scene, "PureQ_seed_weight_threshold", max(profile_min_weight, 0.001)))
        if use_double_pass and active_obj.vertex_groups:
            kept_group_names = [vg.name for vg in active_obj.vertex_groups]
            seed_vertices = _collect_weighted_vertex_indices(
                active_obj,
                kept_group_names,
                seed_threshold
            )

            if seed_vertices:
                print(f"Double-pass seed vertices: {len(seed_vertices)} (threshold={seed_threshold})")
                _clear_weights_for_groups(active_obj, kept_group_names)

                has_weights = _apply_data_transfer_weights(active_obj, avatar_object, scene.PureQ_transfer_method)
                if not has_weights:
                    self.report({'WARNING'}, "Double-pass transfer produced no weights. Retrying with Nearest Vertex...")
                    has_weights = _apply_data_transfer_weights(active_obj, avatar_object, 'NEAREST')

                outside_seed = [v.index for v in active_obj.data.vertices if v.index not in seed_vertices]
                _remove_weights_from_vertices(active_obj, outside_seed)
                self.report(
                    {'INFO'},
                    f"Double-pass cleanup: protected {len(seed_vertices)} garment vertices, removed contamination from {len(outside_seed)} vertices."
                )
            else:
                self.report(
                    {'WARNING'},
                    "Double-pass cleanup skipped: no seed vertices detected in first pass. Try lowering seed threshold."
                )

        # Debug: Print weights for each remaining group to see their values
        vertices_with_weights = 0
        for vg in active_obj.vertex_groups:
            total_weight = 0
            vertices_in_group = 0
            for v in active_obj.data.vertices:
                for g in v.groups:
                    if g.group == vg.index and g.weight > 0.001:  # Only count meaningful weights
                        total_weight += g.weight
                        vertices_with_weights += 1
                        vertices_in_group += 1
            print(f"  {vg.name}: total weight = {total_weight}, vertices with weights = {vertices_in_group}")

        print(f"Total vertices with meaningful weights: {vertices_with_weights} out of {len(active_obj.data.vertices)}")

        # Check if filtering removed everything
        if not active_obj.vertex_groups:
            self.report({'WARNING'}, "All weights were filtered out! Check your Bone Profile or Bone List.")
            # Instead of failing completely, let's create the allowed bones as empty vertex groups
            # This preserves the object structure even if the transfer didn't work as expected
            if allowed_bones:
                for bone_name in allowed_bones:
                    try:
                        active_obj.vertex_groups.new(name=bone_name)
                        print(f"Created empty vertex group: {bone_name}")
                    except:
                        print(f"Could not create vertex group: {bone_name}")
                self.report({'INFO'}, f"Created {len(allowed_bones)} empty vertex groups as fallback")
            else:
                self.report({'ERROR'}, "No allowed bones defined in profile or selection.")
                return {'CANCELLED'}

        # Additional check: if very few vertices have weights, warn the user
        vertex_count = len(active_obj.data.vertices)
        if vertices_with_weights < vertex_count * 0.1:  # Less than 10% of vertices have weights
            self.report({'WARNING'}, f"Only {vertices_with_weights}/{vertex_count} vertices have weights. This may cause mesh collapse. Consider checking your transfer settings.")
            print(f"WARNING: Only {vertices_with_weights}/{vertex_count} vertices have meaningful weights")

        # 5. Clean small weights (Noise reduction)
        # Use a very low threshold for cleaning to avoid removing entire vertex groups
        # The profile min_weight filtering will be applied properly later
        clean_threshold = 0.0001  # Very low threshold to avoid removing entire groups
        print(f"Cleaning weights with threshold: {clean_threshold}")
        if active_obj.vertex_groups:
            bpy.ops.object.vertex_group_clean(group_select_mode='ALL', limit=clean_threshold)

        # Debug: Print vertex groups after cleaning
        groups_after_clean = [vg.name for vg in active_obj.vertex_groups]
        print(f"Remaining vertex groups after cleaning: {groups_after_clean}")
        for vg in active_obj.vertex_groups:
            total_weight = 0
            for v in active_obj.data.vertices:
                for g in v.groups:
                    if g.group == vg.index:
                        total_weight += g.weight
            print(f"  {vg.name}: total weight = {total_weight}")

        # 6. Normalize weights (ensure they sum to 1.0)
        if active_obj.vertex_groups:
            bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
        else:
            self.report({'WARNING'}, "No vertex groups remained after filtering. Check overlap or profile.")

        # Debug: Print vertex groups and their weights after normalization
        print("Vertex groups and weights after normalization:")
        for vg in active_obj.vertex_groups:
            total_weight = 0
            for v in active_obj.data.vertices:
                for g in v.groups:
                    if g.group == vg.index:
                        total_weight += g.weight
            print(f"  {vg.name}: total weight = {total_weight}")

        # 7. Apply profile's min_weight filtering properly using a more robust method
        # This removes vertex groups that have very low total weights across all vertices
        print(f"Applying profile min_weight filtering: {profile_min_weight}")

        # Instead of using total weight per group, use the approach from the reference addon
        # Find all vertex groups that are actually in use (have vertices with significant weights)
        used_groups = set()
        for vertex in active_obj.data.vertices:
            for group in vertex.groups:
                # Consider a group as "used" only if the weight is significant
                if group.weight > profile_min_weight and group.group < len(active_obj.vertex_groups):
                    vg_name = active_obj.vertex_groups[group.group].name
                    used_groups.add(vg_name)

        # Identify groups that exist but are not in the "used" list
        groups_to_remove = [vg for vg in active_obj.vertex_groups if vg.name not in used_groups]

        # Remove those unused groups
        for group in reversed(groups_to_remove):  # Iterate in reverse to not affect indices
            print(f"Removing unused group: {group.name}")
            active_obj.vertex_groups.remove(group)

        print(f"Removed {len(groups_to_remove)} unused vertex groups")

        # 8. Apply smarter smoothing to improve weight distribution (based on reference addon)
        # Only apply smoothing if there are vertex groups and the scene has smoothing properties
        try:
            smooth_factor = scene.PureQ_smooth_factor if hasattr(scene, 'PureQ_smooth_factor') else 0.5
            smooth_iterations = 1

            if getattr(scene, 'PureQ_auto_smooth', False) and active_obj.vertex_groups:
                print("Applying Auto Smooth & Clean...")
                try:
                    bpy.ops.pureq.smooth_clean_weights(
                        iterations=scene.PureQ_smooth_iterations,
                        smooth_factor=scene.PureQ_smooth_factor,
                        clean_threshold=scene.PureQ_clean_threshold
                    )
                except Exception as e:
                    print(f"Auto smooth failed: {e}")

                    if active_obj.vertex_groups and smooth_factor > 0:
                        original_mode = bpy.context.mode
                        original_active = bpy.context.view_layer.objects.active
                        original_selected = bpy.context.selected_objects[:]

                        try:
                            bpy.context.view_layer.objects.active = active_obj
                            active_obj.select_set(True)

                            if original_mode != 'PAINT_WEIGHT':
                                bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

                            for vg in active_obj.vertex_groups:
                                total_weight = 0
                                for v in active_obj.data.vertices:
                                    for g in v.groups:
                                        if g.group == vg.index:
                                            total_weight += g.weight

                                if total_weight > 0.0001:
                                    bpy.ops.object.vertex_group_set_active(group=vg.name)
                                    bpy.ops.object.vertex_group_smooth(factor=smooth_factor, repeat=smooth_iterations)

                        except RuntimeError as e:
                            print(f"Could not apply weight smoothing: {e}")
                        finally:
                            try:
                                if original_mode != 'PAINT_WEIGHT':
                                    bpy.ops.object.mode_set(mode=original_mode)
                                else:
                                    bpy.ops.object.mode_set(mode='OBJECT')

                                bpy.context.view_layer.objects.active = original_active
                                bpy.ops.object.select_all(action='DESELECT')
                                for obj_sel in original_selected:
                                    if obj_sel.name in bpy.data.objects:
                                        obj_sel.select_set(True)
                            except Exception:
                                try:
                                    bpy.ops.object.mode_set(mode='OBJECT')
                                except Exception:
                                    pass
            else:
                print("Smoothing properties not available in scene")
        except AttributeError:
            print("Smoothing not configured in scene properties")

        # 9. Apply LOD rules if enabled
        if scene.PureQ_apply_lods:
            self.apply_lod_rules_from_base(active_obj, profile)

        # 10. Ensure armature modifier is properly configured after transfer
        # Check if there's a significant scale difference that might cause issues
        avatar_scale_avg = sum(avatar_object.scale) / 3
        clothing_scale_avg = sum(active_obj.scale) / 3
        scale_ratio = clothing_scale_avg / avatar_scale_avg

        # Check if we have enough weighted vertices to safely apply armature modifier
        vertex_count = len(active_obj.data.vertices)
        weighted_vertex_count = 0
        for v in active_obj.data.vertices:
            for g in v.groups:
                if g.weight > 0.001:  # Meaningful weight
                    weighted_vertex_count += 1
                    break  # Only count each vertex once

        print(f"Vertex count: {vertex_count}, Weighted vertices: {weighted_vertex_count}")

        if weighted_vertex_count < vertex_count * 0.1:  # Less than 10% vertices have weights
            self.report({'WARNING'}, f"Not enough weighted vertices ({weighted_vertex_count}/{vertex_count}). Skipping armature modifier to prevent mesh collapse.")
            print(f"WARNING: Only {weighted_vertex_count}/{vertex_count} vertices have weights, skipping armature modifier")
        else:
            # If scales are reasonable and we have sufficient weighted vertices, proceed with armature modifier setup
            # Remove any existing armature modifiers first to avoid conflicts
            mods_to_remove = []
            for mod in active_obj.modifiers:
                if mod.type == 'ARMATURE':
                    mods_to_remove.append(mod)

            for mod in mods_to_remove:
                active_obj.modifiers.remove(mod)

            # Create new armature modifier
            arm_mod = active_obj.modifiers.new(name="Armature", type='ARMATURE')

            # Set the armature object and ensure vertex groups are used
            arm_mod.object = avatar_armature
            arm_mod.use_vertex_groups = True

        # After transfer, ensure all vertices have at least some weight assigned
        # For high-resolution meshes like PureQ LOD0, we need to ensure vertex groups have meaningful weights

        # Count vertices without weights to identify potential problems
        vertices_without_weights = 0
        for v in active_obj.data.vertices:
            has_weight = False
            for g in v.groups:
                if g.weight > 0.001:  # Meaningful weight threshold
                    has_weight = True
                    break
            if not has_weight:
                vertices_without_weights += 1

        vertex_count = len(active_obj.data.vertices)
        unweighted_ratio = vertices_without_weights / vertex_count if vertex_count > 0 else 0

        if unweighted_ratio > 0.5:  # More than 50% of vertices have no weights
            self.report({'WARNING'}, f"High percentage of unweighted vertices: {vertices_without_weights}/{vertex_count} ({unweighted_ratio*100:.1f}%). Applying fallback weights.")
            print(f"WARNING: {vertices_without_weights}/{vertex_count} vertices have no weights, applying fallback")

            # Apply fallback: assign unweighted vertices to the most appropriate bone based on position
            if active_obj.vertex_groups:
                # Find the most commonly used bone in the profile as fallback
                # This is typically 'pelvis' for skirts
                preferred_fallback = None
                for bone_name in ['pelvis', 'spine_01', 'spine_02', 'spine_03']:
                    if bone_name in active_obj.vertex_groups:
                        preferred_fallback = active_obj.vertex_groups[bone_name]
                        break

                # If no preferred bone found, use the first available
                if not preferred_fallback:
                    preferred_fallback = active_obj.vertex_groups[0]

                # Assign unweighted vertices to the appropriate group
                for v in active_obj.data.vertices:
                    # Only assign to fallback group if vertex has no other groups
                    vertex_has_group = False
                    for g in v.groups:
                        if g.weight > 0.001:
                            vertex_has_group = True
                            break

                    if not vertex_has_group:
                        preferred_fallback.add([v.index], 1.0, 'REPLACE')  # Full weight to fallback group
                        print(f"Assigned vertex {v.index} to fallback group {preferred_fallback.name}")

        # Also ensure the clothing object is still parented to the armature after transfer
        if active_obj.parent != avatar_armature:
            # Keep transform
            mat = active_obj.matrix_world.copy()
            active_obj.parent = avatar_armature
            active_obj.matrix_world = mat

        # Run diagnostic after transfer
        bpy.ops.pureq.diagnostic_analyzer(action="after_transfer")

        print("=== DIAGNOSTIC: WEIGHT TRANSFER COMPLETE ===\n")

        # Switch to Weight Paint mode for immediate inspection (Best Practice from intoZOI)
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            # Set helpful brush defaults
            bpy.context.tool_settings.weight_paint.brush.weight = 0.05
            bpy.context.tool_settings.weight_paint.brush.blend = 'ADD'

        self.report({'INFO'}, f"Transfer Complete. Kept {len(active_obj.vertex_groups)} active vertex groups. {vertices_without_weights} vertices initially had no weights.")
        return {'FINISHED'}

    def get_avatar_height(self, avatar_obj):
        """Calculate the approximate height of the avatar"""
        avatar_mesh = avatar_obj.data
        min_z = float('inf')
        max_z = float('-inf')

        for vert in avatar_mesh.vertices:
            world_pos = avatar_obj.matrix_world @ vert.co
            if world_pos.z < min_z:
                min_z = world_pos.z
            if world_pos.z > max_z:
                max_z = world_pos.z

        return max_z - min_z

    def should_process_vertex(self, clothing_type, vertex_pos, avatar_pos, avatar_height):
        """Determine if a vertex should be processed based on clothing type and position"""
        if clothing_type is None:
            return True  # If no clothing type specified, process all vertices

        # Calculate relative position to avatar
        relative_z = vertex_pos.z - avatar_pos.z

        # Define processing rules based on clothing type
        if clothing_type == 'SHORT_SKIRT':
            # Short skirts: only process vertices from mid-thigh down to knee level
            thigh_level = avatar_height * 0.4  # Approximate mid-thigh
            knee_level = avatar_height * 0.2   # Approximate knee level
            return knee_level <= relative_z <= thigh_level

        elif clothing_type == 'MEDIUM_SKIRT':
            # Medium skirts: only process vertices from waist down to below knee
            waist_level = avatar_height * 0.5  # Approximate waist
            below_knee_level = avatar_height * 0.1  # Slightly below knee
            return below_knee_level <= relative_z <= waist_level

        elif clothing_type == 'LONG_SKIRT':
            # Long skirts: only process vertices from waist down to ankle level
            waist_level = avatar_height * 0.5   # Approximate waist
            ankle_level = avatar_height * 0.05  # Approximate ankle level
            return ankle_level <= relative_z <= waist_level

        elif clothing_type == 'TROUSERS':
            # Trousers: only process vertices from waist down to ankle level
            waist_level = avatar_height * 0.5   # Approximate waist
            ankle_level = avatar_height * 0.05  # Approximate ankle level
            return ankle_level <= relative_z <= waist_level

        elif clothing_type == 'SHIRT':
            # Shirts: only process vertices from chest up to shoulders
            chest_level = avatar_height * 0.6   # Approximate chest
            head_level = avatar_height * 0.85   # Approximate head/chin
            return chest_level <= relative_z <= head_level

        elif clothing_type == 'JACKET':
            # Jackets: only process vertices from chest up to shoulders
            chest_level = avatar_height * 0.6   # Approximate chest
            head_level = avatar_height * 0.85   # Approximate head/chin
            return chest_level <= relative_z <= head_level

        else:
            # For CUSTOM or other types, process all vertices
            return True

    def apply_weight_smoothing(self, obj):
        """Apply weight smoothing to the object"""
        scene = bpy.context.scene
        smooth_factor = scene.PureQ_smooth_factor

        # Store original context
        original_mode = bpy.context.mode
        original_active = bpy.context.view_layer.objects.active
        original_selected = bpy.context.selected_objects[:]

        try:
            # Set object as active and ensure we're in the right mode
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)

            # Enter weight paint mode temporarily if needed for smoothing
            if original_mode != 'PAINT_WEIGHT':
                bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

            # Use Blender's built-in smooth operator
            for vg in obj.vertex_groups:
                # Select this vertex group
                bpy.ops.object.vertex_group_set_active(group=vg.name)
                bpy.ops.object.vertex_group_smooth(factor=smooth_factor, repeat=1)

        except RuntimeError as e:
            print(f"Could not apply weight smoothing: {e}")
        finally:
            # Restore original mode and selection
            try:
                if original_mode != 'PAINT_WEIGHT':
                    bpy.ops.object.mode_set(mode=original_mode)
                else:
                    bpy.ops.object.mode_set(mode='OBJECT')

                # Restore original selection
                bpy.context.view_layer.objects.active = original_active
                bpy.ops.object.select_all(action='DESELECT')
                for obj_sel in original_selected:
                    if obj_sel.name in bpy.data.objects:
                        obj_sel.select_set(True)
            except:
                # If restoration fails, at least ensure we're in object mode
                try:
                    bpy.ops.object.mode_set(mode='OBJECT')
                except:
                    pass

    def prefilter_avatar_armature(self, avatar_obj, profile):
        """Pre-filter avatar armature to keep only allowed bones based on profile"""
        # Find the armature modifier
        avatar_armature = None
        for modifier in avatar_obj.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object:
                avatar_armature = modifier.object
                break

        if not avatar_armature or not profile:
            return

        # Store original state
        original_mode = bpy.context.mode
        original_active = bpy.context.view_layer.objects.active
        original_selected = bpy.context.selected_objects[:]

        try:
            # Switch to edit mode to modify bones
            bpy.context.view_layer.objects.active = avatar_armature
            bpy.ops.object.select_all(action='DESELECT')
            avatar_armature.select_set(True)
            bpy.context.view_layer.objects.active = avatar_armature

            # Only try to enter edit mode if we're in object mode
            if original_mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            else:
                # If already in edit mode, ensure the right object is in edit mode
                if bpy.context.mode != 'EDIT_ARMATURE':
                    bpy.ops.object.mode_set(mode='EDIT')

            allowed_bones = profile.get("allowed_bones", set())
            forbidden_bones = profile.get("forbidden_bones", set())

            # Get all bones in the armature
            edit_bones = avatar_armature.data.edit_bones
            bones_to_remove = []

            # Identify bones that should be kept based on profile
            bones_to_keep = set()

            # Add directly allowed bones
            for bone_name in allowed_bones:
                if bone_name in edit_bones:
                    bones_to_keep.add(bone_name)

            # Add forbidden bones to remove list immediately
            for bone_name in forbidden_bones:
                if bone_name in edit_bones:
                    bones_to_remove.append(bone_name)

            # For remaining bones, only remove if they are not parents/ancestors of allowed bones
            # and not in the allowed list
            for bone in edit_bones:
                if (bone.name not in bones_to_keep and
                    bone.name not in forbidden_bones):
                    # Only remove if allowed_bones is specified (not empty)
                    if allowed_bones:
                        # Check if this bone is an ancestor of any allowed bone
                        is_ancestor = False
                        for allowed_bone_name in allowed_bones:
                            if allowed_bone_name in edit_bones:
                                current_bone = edit_bones[allowed_bone_name]
                                # Walk up the parent chain to see if current bone is an ancestor
                                parent = current_bone.parent
                                while parent:
                                    if parent.name == bone.name:
                                        is_ancestor = True
                                        break
                                    parent = parent.parent
                                if is_ancestor:
                                    break

                        # Only remove if it's not an ancestor of an allowed bone
                        if not is_ancestor:
                            bones_to_remove.append(bone.name)

            # Remove the bones (in reverse order to handle dependencies correctly)
            bones_to_remove.reverse()
            for bone_name in bones_to_remove:
                if bone_name in edit_bones:
                    edit_bones.remove(edit_bones[bone_name])

        except Exception as e:
            print(f"Error in prefilter_avatar_armature: {e}")
        finally:
            # Restore original state safely
            try:
                # Only try to exit edit mode if we're currently in it
                if bpy.context.mode == 'EDIT_ARMATURE':
                    bpy.ops.object.mode_set(mode='OBJECT')
                elif original_mode == 'EDIT_MESH' and bpy.context.mode == 'EDIT':
                    bpy.ops.object.mode_set(mode='OBJECT')

                # Restore original active object and selection
                bpy.context.view_layer.objects.active = original_active
                bpy.ops.object.select_all(action='DESELECT')
                for obj in original_selected:
                    if obj.name in bpy.data.objects:
                        obj.select_set(True)
            except:
                # If restoration fails, at least try to exit edit mode
                try:
                    if bpy.context.mode.startswith('EDIT'):
                        bpy.ops.object.mode_set(mode='OBJECT')
                except:
                    pass

    def disable_armature_modifier(self, obj):
        """Disable armature modifier during weight transfer to prevent contamination"""
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE':
                # Store original state as custom properties on the object
                obj['_armature_mod_show_viewport'] = mod.show_viewport
                obj['_armature_mod_show_render'] = mod.show_render

                # Disable the modifier
                mod.show_viewport = False
                mod.show_render = False
                return mod
        return None

    def enable_armature_modifier(self, mod):
        """Re-enable armature modifier after weight transfer"""
        if mod:
            # Restore original state from custom properties on the object
            obj = mod.id_data  # Get the object the modifier belongs to
            if '_armature_mod_show_viewport' in obj:
                mod.show_viewport = obj['_armature_mod_show_viewport']
                mod.show_render = obj['_armature_mod_show_render']
                # Clean up the custom properties
                del obj['_armature_mod_show_viewport']
                del obj['_armature_mod_show_render']
            else:
                # If original state not stored, just enable
                mod.show_viewport = True
                mod.show_render = True

    def ensure_clothing_armature_modifier(self, clothing_obj, avatar_armature):
        """Ensure clothing object has armature modifier pointing to avatar's armature"""
        # Check if clothing already has an armature modifier
        existing_arm_mod = None
        for mod in clothing_obj.modifiers:
            if mod.type == 'ARMATURE':
                existing_arm_mod = mod
                break

        if existing_arm_mod:
            # Check if it points to the correct armature
            if existing_arm_mod.object != avatar_armature:
                # Update to point to avatar's armature
                existing_arm_mod.object = avatar_armature
            # Ensure vertex groups are used
            existing_arm_mod.use_vertex_groups = True
            arm_mod = existing_arm_mod
            self.report({'INFO'}, f"Updated clothing armature modifier to use avatar's armature")
        else:
            # Add new armature modifier
            arm_mod = clothing_obj.modifiers.new(name="Armature", type='ARMATURE')
            arm_mod.object = avatar_armature
            arm_mod.use_vertex_groups = True
            self.report({'INFO'}, f"Added armature modifier to clothing object")

        # Ensure it's at the end of the modifier stack for proper evaluation
        # Move it to the last position
        bpy.context.view_layer.objects.active = clothing_obj
        bpy.ops.object.modifier_move_to_index(modifier=arm_mod.name, index=len(clothing_obj.modifiers) - 1)

    def cleanup_unused_vertex_groups(self, obj, profile):
        """Remove vertex groups that don't have any assigned weights"""
        if not profile:
            return

        allowed_bones = profile.get("allowed_bones", set())
        forbidden_bones = profile.get("forbidden_bones", set())

        # First, remove vertex groups that are explicitly forbidden
        groups_to_remove = []
        for vg in obj.vertex_groups:
            if vg.name in forbidden_bones:
                groups_to_remove.append(vg)

        # Remove forbidden groups
        for vg in groups_to_remove:
            obj.vertex_groups.remove(vg)

        # Second, remove vertex groups that are not in allowed list (if allowed list is specified)
        if allowed_bones:  # Only if there are specific allowed bones
            groups_to_remove = []
            for vg in obj.vertex_groups:
                if vg.name not in allowed_bones:
                    # Check if this vertex group has any assigned vertices
                    has_vertices = False
                    for v in obj.data.vertices:
                        for g in v.groups:
                            if g.group == vg.index and g.weight > 0.001:  # Small threshold
                                has_vertices = True
                                break
                        if has_vertices:
                            break

                    if not has_vertices:
                        groups_to_remove.append(vg)

            # Remove unused groups
            for vg in groups_to_remove:
                obj.vertex_groups.remove(vg)

        # Finally, verify that only allowed bone names remain
        groups_to_remove = []
        for vg in obj.vertex_groups:
            if vg.name not in allowed_bones:
                groups_to_remove.append(vg)

        for vg in groups_to_remove:
            obj.vertex_groups.remove(vg)

    def prefilter_avatar_armature(self, avatar_obj, profile):
        """Pre-filter avatar armature to keep only allowed bones based on profile"""
        # Find the armature modifier
        avatar_armature = None
        for modifier in avatar_obj.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object:
                avatar_armature = modifier.object
                break

        if not avatar_armature or not profile:
            return

        # Store original state
        original_mode = bpy.context.mode
        original_active = bpy.context.view_layer.objects.active
        original_selected = bpy.context.selected_objects[:]

        try:
            # Switch to edit mode to modify bones
            bpy.context.view_layer.objects.active = avatar_armature
            bpy.ops.object.select_all(action='DESELECT')
            avatar_armature.select_set(True)
            bpy.context.view_layer.objects.active = avatar_armature

            # Only try to enter edit mode if we're in object mode
            if original_mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            else:
                # If already in edit mode, ensure the right object is in edit mode
                if bpy.context.mode != 'EDIT_ARMATURE':
                    bpy.ops.object.mode_set(mode='EDIT')

            allowed_bones = profile.get("allowed_bones", set())
            forbidden_bones = profile.get("forbidden_bones", set())

            # Get all bones in the armature
            edit_bones = avatar_armature.data.edit_bones
            bones_to_remove = []

            # Identify bones that should be kept based on profile
            bones_to_keep = set()

            # Add directly allowed bones
            for bone_name in allowed_bones:
                if bone_name in edit_bones:
                    bones_to_keep.add(bone_name)

            # Add forbidden bones to remove list immediately
            for bone_name in forbidden_bones:
                if bone_name in edit_bones:
                    bones_to_remove.append(bone_name)

            # For remaining bones, only remove if they are not parents/ancestors of allowed bones
            # and not in the allowed list
            for bone in edit_bones:
                if (bone.name not in bones_to_keep and
                    bone.name not in forbidden_bones):
                    # Only remove if allowed_bones is specified (not empty)
                    if allowed_bones:
                        # Check if this bone is an ancestor of any allowed bone
                        is_ancestor = False
                        for allowed_bone_name in allowed_bones:
                            if allowed_bone_name in edit_bones:
                                current_bone = edit_bones[allowed_bone_name]
                                # Walk up the parent chain to see if current bone is an ancestor
                                parent = current_bone.parent
                                while parent:
                                    if parent.name == bone.name:
                                        is_ancestor = True
                                        break
                                    parent = parent.parent
                                if is_ancestor:
                                    break

                        # Only remove if it's not an ancestor of an allowed bone
                        if not is_ancestor:
                            bones_to_remove.append(bone.name)

            # Remove the bones (in reverse order to handle dependencies correctly)
            bones_to_remove.reverse()
            for bone_name in bones_to_remove:
                if bone_name in edit_bones:
                    edit_bones.remove(edit_bones[bone_name])

        except Exception as e:
            print(f"Error in prefilter_avatar_armature: {e}")
        finally:
            # Restore original state safely
            try:
                # Only try to exit edit mode if we're currently in it
                if bpy.context.mode == 'EDIT_ARMATURE':
                    bpy.ops.object.mode_set(mode='OBJECT')
                elif original_mode == 'EDIT_MESH' and bpy.context.mode == 'EDIT':
                    bpy.ops.object.mode_set(mode='OBJECT')

                # Restore original active object and selection
                bpy.context.view_layer.objects.active = original_active
                bpy.ops.object.select_all(action='DESELECT')
                for obj in original_selected:
                    if obj.name in bpy.data.objects:
                        obj.select_set(True)
            except:
                # If restoration fails, at least try to exit edit mode
                try:
                    if bpy.context.mode.startswith('EDIT'):
                        bpy.ops.object.mode_set(mode='OBJECT')
                except:
                    pass

    def apply_lod_rules_from_base(self, base_obj, base_profile):
        """Apply LOD rules to LOD0/LOD1/LOD2 objects based on the base object"""
        from .core.lod_apply import find_lods, apply_lod_rules
        from .core.bone_profiles import get_lod_rules

        lod_objects = find_lods(base_obj)
        lod_rules = get_lod_rules()

        for lod_level, lod_obj in lod_objects.items():
            if lod_obj and lod_level in lod_rules:
                rule = lod_rules[lod_level]
                apply_lod_rules(lod_obj, base_profile, rule)

                # Store metadata
                lod_obj["PureQ_lod"] = lod_level
                lod_obj["PureQ_source"] = base_obj.name

class PureQ_OT_clear_weights(bpy.types.Operator):
    """Remove all vertex groups and armature modifiers"""
    bl_idname = "pureq.clear_weights"
    bl_label = "Clear Weights"
    bl_description = "Remove all vertex groups and armature modifiers from the selected object"
    
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh object")
            return {'CANCELLED'}
            
        obj.vertex_groups.clear()
        for mod in [m for m in obj.modifiers if m.type == 'ARMATURE']:
            obj.modifiers.remove(mod)
            
        self.report({'INFO'}, f"Cleared weights and modifiers from {obj.name}")
        return {'FINISHED'}


class PureQ_OT_show_help_tip(bpy.types.Operator):
    """Show contextual help for UI options"""
    bl_idname = "pureq.show_help_tip"
    bl_label = "Show Help"
    bl_description = "Show a short explanation for this option"

    topic: EnumProperty(
        name="Help Topic",
        items=[(k, k.replace("_", " ").title(), "") for k in HELP_TOPICS.keys()],
        default="weight_profile"
    )

    def execute(self, context):
        fallback = {
            "es": "No hay ayuda disponible para esta opción.",
            "ko": "이 옵션에 대한 도움말이 없습니다.",
            "en": "No help available for this option.",
        }
        if _get_ui_language() == "ko" and self.topic in HELP_TOPICS_KO:
            message = HELP_TOPICS_KO[self.topic]
        else:
            message = _lang_pick(HELP_TOPICS.get(self.topic, fallback), default_en=fallback["en"])
        lines = textwrap.wrap(message, width=72) or [message]

        def draw_help(self_popup, _context):
            for line in lines:
                self_popup.layout.label(text=line, icon='INFO')

        context.window_manager.popup_menu(
            draw_help,
            title=_lang_pick({"es": "Ayuda", "ko": "도움말", "en": "Help"}, default_en="Help"),
            icon='QUESTION'
        )
        return {'FINISHED'}

class PUREQ_PT_mode_selector(bpy.types.Panel):
    """Panel to select the addon mode"""
    bl_label = "Mode"
    bl_idname = "PUREQ_PT_mode_selector"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PureQ Weight Transfer'
    bl_order = -100  # Keep this as the first panel in the tab

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(
            text=_lang_pick({"es": "Elige flujo de trabajo", "ko": "작업 흐름 선택", "en": "Choose workflow"}, default_en="Choose workflow"),
            icon='PREFERENCES'
        )
        layout.prop(scene, "PureQ_addon_mode", expand=True)

class PUREQ_PT_manager_hint(bpy.types.Panel):
    """Fallback panel in MANAGER mode to avoid empty UI on partial failures"""
    bl_label = "Profile Manager Status"
    bl_idname = "PUREQ_PT_manager_hint"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PureQ Weight Transfer'
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return getattr(context.scene, "PureQ_addon_mode", "TRANSFER") == 'MANAGER'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()
        box.label(text=_t("manager_active"), icon='CHECKMARK')
        if hasattr(scene, "PureQ_selected_model_profile"):
            box.label(text=_t("manager_loaded"), icon='INFO')
        else:
            box.label(text=_t("manager_missing"), icon='ERROR')
            box.label(text=_t("manager_reload_tip"), icon='INFO')

class PUREQ_PT_main_panel(bpy.types.Panel):
    """Main panel for PureQ Weight Transfer"""
    bl_label = "PureQ Weight Transfer"
    bl_idname = "PUREQ_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PureQ Weight Transfer'
    bl_order = 1

    @classmethod
    def poll(cls, context):
        # Only show if in TRANSFER mode
        return getattr(context.scene, "PureQ_addon_mode", "TRANSFER") == 'TRANSFER'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Clean up any invalid object references before displaying
        cleanup_object_references()

        # Section 1: Avatar
        box = layout.box()
        box.label(text=_t("avatar_section"), icon='ARMATURE_DATA')

        if avatar_object and avatar_object.name in bpy.data.objects:
            box.label(text=f"{_t('mesh_label')}: {avatar_object.name}", icon='MESH_DATA')

            # Find armature associated with avatar
            avatar_armature = get_armature_for_mesh(avatar_object)

            if avatar_armature:
                box.label(text=f"{_t('armature_label')}: {avatar_armature.name}", icon='BONE_DATA')
        else:
            box.label(text=_t("no_avatar"), icon='ERROR')
            if context.active_object and context.active_object.type == 'MESH':
                box.label(text=_t("avatar_tip"), icon='INFO')

        row = box.row(align=True)
        row.operator("pureq.find_avatar_by_name", icon='VIEWZOOM')
        row.operator("pureq.set_avatar_from_selection", icon='RESTRICT_SELECT_OFF')
        op = row.operator("pureq.show_help_tip", text="", icon='QUESTION')
        op.topic = "avatar_auto_find"

        # Section 2: Garment
        box = layout.box()
        box.label(text=_t("garment_section"), icon='OUTLINER_DATA_MESH')

        row = box.row(align=True)
        row.operator("pureq.load_clothing", icon='IMPORT')
        row.operator("pureq.set_clothing_from_selection", icon='RESTRICT_SELECT_OFF')
        op = row.operator("pureq.show_help_tip", text="", icon='QUESTION')
        op.topic = "garment_import"

        # Only consider active object as garment if it's not the avatar
        active_obj = context.active_object
        if active_obj and active_obj.type == 'MESH' and active_obj != avatar_object:
            box.label(text=f"{_t('active_label')}: {active_obj.name}", icon='CHECKMARK')

            # Show detected type if available
            if "PureQ_clothing_type" in active_obj:
                c_type = active_obj["PureQ_clothing_type"]
                box.label(text=f"{_t('type_label')}: {c_type.replace('_', ' ').title()}", icon='SHADING_BBOX')

            # Show basic bounding info
            if active_obj and active_obj.type == 'MESH':
                bbox = [active_obj.matrix_world @ Vector(co) for co in active_obj.bound_box]
                min_co = min(bbox, key=lambda v: v.z)
                max_co = max(bbox, key=lambda v: v.z)
                height = (max_co - min_co).z
                box.label(text=f"{_t('height_label')}: {height:.2f}m", icon='ARROW_LEFTRIGHT')
        else:
            box.label(text=_t("select_garment"), icon='ERROR')

        # Section 3: Garment Configuration (Model + Profile)
        box = layout.box()
        box.label(text=_t("garment_config"), icon='MOD_CLOTH')

        row = box.row(align=True)
        row.prop(scene, "PureQ_garment_model", text=_t("model_label"))
        op = row.operator("pureq.show_help_tip", text="", icon='QUESTION')
        op.topic = "garment_model"

        # Optional link to Profile Manager data (used as transfer source when available).
        if hasattr(scene, "PureQ_selected_model_profile"):
            row = box.row(align=True)
            row.prop(scene, "PureQ_selected_model_profile", text="Model Profile")

        row = box.row(align=True)
        row.prop(scene, "PureQ_bone_profile", text=_t("weight_profile_label"))
        op = row.operator("pureq.show_help_tip", text="", icon='QUESTION')
        op.topic = "weight_profile"

        row = box.row(align=True)
        row.prop(scene, "PureQ_transfer_method", text=_t("method_label"))
        op = row.operator("pureq.show_help_tip", text="", icon='QUESTION')
        op.topic = "transfer_method"

        row = box.row(align=True)
        row.prop(scene, "PureQ_enable_double_pass_clean", text=_t("double_pass_label"))
        op = row.operator("pureq.show_help_tip", text="", icon='QUESTION')
        op.topic = "double_pass"
        if scene.PureQ_enable_double_pass_clean:
            row = box.row(align=True)
            row.prop(scene, "PureQ_seed_weight_threshold", text=_t("seed_threshold_label"))
            op = row.operator("pureq.show_help_tip", text="", icon='QUESTION')
            op.topic = "seed_threshold"
        try:
            from .core.bone_profiles import get_bone_profile_names
            count = len(get_bone_profile_names())
            box.label(text=f"{_t('profiles_available')}: {count}", icon='INFO')
        except Exception:
            box.label(text=_t("profiles_unavailable"), icon='ERROR')

        # --- NEW UI: BONE LIST ---
        box = layout.box()
        box.label(text=_t("bone_mask_section"), icon='FILTER')

        row = box.row(align=True)
        row.operator("pureq.refresh_profile_bones", text=_t("load_mask_btn"), icon='FILE_REFRESH')
        op = row.operator("pureq.show_help_tip", text="", icon='QUESTION')
        op.topic = "load_bone_mask"

        # Show Restore button if object has saved data
        if context.active_object and "PureQ_saved_bones" in context.active_object:
            restore_row = box.row(align=True)
            restore_row.operator("pureq.load_bones_from_object", text=_t("restore_mask_btn"), icon='RECOVER_LAST')
            op = restore_row.operator("pureq.show_help_tip", text="", icon='QUESTION')
            op.topic = "restore_bone_mask"

        if len(scene.PureQ_bone_list) > 0:
            row = box.row(align=True)
            op = row.operator("pureq.bone_list_actions", text=_t("select_all"), icon='CHECKBOX_HLT')
            if op:
                op.action = 'SELECT_ALL'
            op = row.operator("pureq.bone_list_actions", text=_t("deselect_all"), icon='CHECKBOX_DEHLT')
            if op:
                op.action = 'DESELECT_ALL'

            row = box.row()
            row.template_list("PUREQ_UL_bone_list", "", scene, "PureQ_bone_list", scene, "PureQ_bone_list_index", rows=5)

            box.label(text=_t("uncheck_tip"), icon='INFO')

        # Section 4: Profile Info (professional level)
        profile, profile_source, profile_name = _resolve_transfer_profile(scene, active_obj=context.active_object)

        info_box = box.box()
        info_box.label(text=_t("profile_info"), icon='INFO')

        if profile:
            if profile_source == "model":
                info_box.label(text=f"Source: Model Profile ({profile_name})", icon='CHECKMARK')
            elif profile_source == "manual":
                info_box.label(text="Source: Manual Bone Mask (one-shot)", icon='CHECKMARK')
            else:
                info_box.label(text=f"Source: Bone Profile ({profile_name})", icon='CHECKMARK')
            info_box.label(text=f"{_t('allowed_bones')}: {len(profile['allowed_bones'])}")
            info_box.label(text=f"{_t('max_influences')}: {profile['max_influences']}")
            info_box.label(text=f"{_t('min_weight')}: {profile['min_weight']:.2f}")
        else:
            info_box.label(text=_t("invalid_profile"), icon='ERROR')

        # Section 5: Transfer Action
        box = layout.box()
        box.label(text=_t("transfer_section"), icon='MOD_VERTEX_WEIGHT')

        # Use active_obj instead of obj
        active_obj = context.active_object
        has_avatar = bool(avatar_object and getattr(avatar_object, "name", None) in bpy.data.objects)
        has_garment = bool(active_obj and active_obj.type == 'MESH' and active_obj != avatar_object)
        has_profile = bool(profile)

        row = box.row()
        row.enabled = bool(has_avatar and has_garment and has_profile)
        row.operator("pureq.transfer_weights", icon='PLAY')
        op = row.operator("pureq.show_help_tip", text="", icon='QUESTION')
        op.topic = "transfer_weights"

        if not has_avatar:
            box.label(text=_t("transfer_disabled_avatar"), icon='ERROR')
        if not has_garment:
            box.label(text=_t("transfer_disabled_garment"), icon='ERROR')
        if not has_profile:
            box.label(text=_t("transfer_disabled_profile"), icon='ERROR')

        # LOD Rules option
        row = box.row()
        row.prop(scene, "PureQ_auto_smooth", text=_t("auto_smooth_label"))
        op = row.operator("pureq.show_help_tip", text="", icon='QUESTION')
        op.topic = "auto_smooth"
        if scene.PureQ_auto_smooth:
            row.prop(scene, "PureQ_smooth_iterations", text=_t("iter_label"))
        lod_row = box.row(align=True)
        lod_row.prop(scene, "PureQ_apply_lods", text=_t("lod_label"))
        op = lod_row.operator("pureq.show_help_tip", text="", icon='QUESTION')
        op.topic = "lod_rules"

        # Section 6: Weight Cleaning Tools
        box = layout.box()
        box.label(text=_t("weight_cleaning"), icon='BRUSH_DATA')

        # Auto clean tools
        clean_box = box.box()
        clean_box.label(text=_t("auto_clean"), icon='TRASH')
        row = clean_box.row(align=True)
        row.operator("pureq.smooth_clean_weights", text=_t("smooth_clean"), icon='SMOOTHCURVE')
        row.operator("pureq.clear_weights", text=_t("clear_all_weights"), icon='X')
        row.operator("pureq.auto_clean_vertex_groups", text=_t("auto_clean"), icon='MODIFIER_DATA')
        row.prop(scene, "PureQ_clean_threshold", text=_t("threshold"))

        # Advanced cleaning tools
        advanced_box = box.box()
        advanced_box.label(text=_t("advanced_tools"), icon='TOOL_SETTINGS')
        row = advanced_box.row(align=True)
        row.operator("pureq.merge_similar_vertex_groups", text=_t("merge_similar"), icon='AUTOMERGE_ON')
        row = advanced_box.row(align=True)
        row.operator("pureq.select_low_weight_vertices", text=_t("select_low_weights"), icon='VERTEXSEL')
        row = advanced_box.row(align=True)
        row.operator("pureq.identify_unused_bones", text=_t("analyze_weights"), icon='INFO')
        row = advanced_box.row(align=True)
        row.operator("pureq.compensate_weights", text=_t("compensate_weights"), icon='MOD_VERTEX_WEIGHT')

        # Legacy tools (moved to bottom for cleaner workflow)
        box = layout.box()
        box.label(text=_t("tools_section"), icon='TOOL_SETTINGS')

        row = box.row(align=True)
        row.operator("paint.weight_paint", text=_t("weight_paint"), icon='BRUSH_DATA')

        row = box.row(align=True)
        row.operator("object.vertex_group_normalize_all", text=_t("normalize"), icon='ARROW_LEFTRIGHT')

        row = box.row(align=True)
        row.operator("object.vertex_group_clean", text=_t("clean"), icon='X')
        row.prop(scene, "PureQ_clean_threshold", text=_t("threshold"))

        row = box.row(align=True)
        row.operator("object.vertex_group_quantize", text=_t("quantize"), icon='MESH_GRID')
        row.prop(scene, "PureQ_quantize_steps", text=_t("steps"))

        row = box.row(align=True)
        row.operator("object.vertex_group_levels", text=_t("levels"), icon='IMAGE_ALPHA')
        row.prop(scene, "PureQ_levels_low", text=_t("low"))
        row.prop(scene, "PureQ_levels_high", text=_t("high"))

        # Diagnostic tools
        diag_box = layout.box()
        diag_box.label(text=_t("diagnostic"), icon='INFO')
        row = diag_box.row(align=True)
        op = row.operator("pureq.diagnostic_analyzer", text=_t("analyze_before"))
        if op:
            op.action = "before_transfer"
        row = diag_box.row(align=True)
        op = row.operator("pureq.diagnostic_analyzer", text=_t("analyze_after"))
        if op:
            op.action = "after_transfer"
        row = diag_box.row(align=True)
        op = row.operator("pureq.diagnostic_analyzer", text=_t("full_scene_analysis"))
        if op:
            op.action = "full_analysis"

def enum_bone_profiles(self, context):
    from .core.bone_profiles import load_bone_profiles, get_bone_profile_names

    try:
        load_bone_profiles()
        profiles = get_bone_profile_names()
        items = [("NONE", "Select Bone Profile", "Choose manually before transfer")]
        items.extend([(p, p.replace("_", " ").title(), "") for p in profiles])
        return items
    except Exception:
        return [("NONE", "No Profiles Found", "")]

_classes = [
    PureQBoneItem,
    PUREQ_UL_bone_list,
    PureQ_OT_bone_list_actions,
    PureQ_OT_load_bones_from_object,
    PureQ_OT_refresh_profile_bones,
    PureQ_OT_load_avatar,
    PureQ_OT_load_clothing,
    PureQ_OT_transfer_weights,
    PureQ_OT_clear_weights,
    PureQ_OT_show_help_tip,
    PUREQ_PT_mode_selector,
    PUREQ_PT_manager_hint,
    PUREQ_PT_main_panel,
    PureQ_OT_set_avatar_from_selection,
    PureQ_OT_set_clothing_from_selection,
    PureQ_OT_find_avatar_by_name,
]

def register():
    global _registered_modules
    _registered_modules = []

    for cls in _classes:
        try:
            bpy.utils.register_class(cls)
        except (ValueError, RuntimeError):
            pass

    # Register mode early so UI can always switch to MANAGER.
    _set_scene_property("PureQ_addon_mode", EnumProperty(
        name=_lang_pick({"es": "Modo", "en": "Mode"}, default_en="Mode"),
        description=_lang_pick({"es": "Selecciona el modo de operacion", "ko": "작업 모드를 선택하세요", "en": "Select the operation mode"}, default_en="Select the operation mode"),
        items=[
            (
                'TRANSFER',
                _lang_pick({"es": "Transferir pesos", "ko": "가중치 전송", "en": "Transfer Weights"}, default_en="Transfer Weights"),
                _lang_pick({"es": "Modo para transferir pesos de avatar a ropa", "ko": "아바타에서 의상으로 가중치를 전송하는 모드", "en": "Mode for transferring weights from avatar to clothing"}, default_en="Mode for transferring weights from avatar to clothing")
            ),
            (
                'MANAGER',
                _lang_pick({"es": "Gestor de perfiles", "ko": "프로필 관리자", "en": "Profile Manager"}, default_en="Profile Manager"),
                _lang_pick({"es": "Modo para crear y gestionar perfiles de huesos", "ko": "본 프로필을 생성/관리하는 모드", "en": "Mode for creating and managing bone profiles"}, default_en="Mode for creating and managing bone profiles")
            ),
        ],
        default='TRANSFER'
    ))

    _set_scene_property("PureQ_bone_list", CollectionProperty(type=PureQBoneItem))
    _set_scene_property("PureQ_bone_list_index", IntProperty(name="Index for bone list", default=0))

    for module_name, register_fn, unregister_fn, force_reload in _SUBMODULE_REGISTRY:
        _safe_register_module(module_name, register_fn, unregister_fn, force_reload=force_reload)

    _set_scene_property("PureQ_smooth_factor", FloatProperty(
        name="Smooth Factor",
        description="Amount of weight smoothing to apply",
        default=0.5,
        min=0.0,
        max=1.0
    ))
    
    _set_scene_property("PureQ_auto_smooth", BoolProperty(
        name="Auto Smooth",
        description="Automatically smooth and clean weights after transfer",
        default=True
    ))
    
    _set_scene_property("PureQ_smooth_iterations", IntProperty(
        name="Smooth Iterations",
        description="Number of smoothing iterations",
        default=2,
        min=1,
        max=20
    ))

    _set_scene_property("PureQ_clothing_type", EnumProperty(
        name="Clothing Type",
        description="Select the type of clothing to load",
        items=CLOTHING_TYPES,
        default='CUSTOM'
    ))

    _set_scene_property("PureQ_clean_threshold", FloatProperty(
        name="Clean Threshold",
        description="Threshold value for cleaning vertex groups",
        default=0.001,
        min=0.0,
        max=1.0
    ))

    _set_scene_property("PureQ_quantize_steps", IntProperty(
        name="Quantize Steps",
        description="Number of steps for quantizing weights",
        default=4,
        min=2,
        max=32
    ))

    _set_scene_property("PureQ_levels_low", FloatProperty(
        name="Levels Low",
        description="Low level value for adjusting weights",
        default=0.0,
        min=0.0,
        max=1.0
    ))

    _set_scene_property("PureQ_levels_high", FloatProperty(
        name="Levels High",
        description="High level value for adjusting weights",
        default=1.0,
        min=0.0,
        max=1.0
    ))

    _set_scene_property("PureQ_use_PureQ_validation", BoolProperty(
        name="Use PureQ Bone Validation",
        description="Filter avatar bones based on PureQ avatar bone names",
        default=False
    ))

    _set_scene_property("PureQ_bone_profile", EnumProperty(
        name="Weight Profile",
        description="Bone template that defines which bones are allowed during weight transfer",
        items=enum_bone_profiles
    ))

    GARMENT_MODELS = [
        ('A_LINE', 'A-Line Skirt', ''),
        ('PENCIL', 'Pencil Skirt', ''),
        ('PLEATED', 'Pleated Skirt', ''),
        ('CIRCLE', 'Circle Skirt', ''),
        ('MINI', 'Mini Skirt', ''),
        ('MAXI', 'Maxi Skirt', ''),
        ('SHORTS', 'Shorts', ''),
        ('PANTS', 'Pants', ''),
        ('JEANS', 'Jeans', ''),
        ('TOP', 'Top', ''),
        ('SHIRT', 'Shirt', ''),
        ('JACKET', 'Jacket', ''),
        ('DRESS', 'Dress', ''),
        ('CUSTOM', 'Custom', ''),
    ]

    _set_scene_property("PureQ_garment_model", EnumProperty(
        name="Garment Model",
        description="Visual/structural garment model",
        items=GARMENT_MODELS,
        default='A_LINE'
    ))

    _set_scene_property("PureQ_apply_lods", BoolProperty(
        name="Auto LOD Rules",
        description="Apply automatic LOD rules to LOD0/LOD1/LOD2 objects",
        default=True
    ))

    _set_scene_property("PureQ_transfer_method", EnumProperty(
        name="Transfer Method",
        description="Method used to transfer weights",
        items=[
            ('POLYINTERP_NEAREST', "Nearest Face Interpolated", "Best for most clothing (Smooth)"),
            ('NEAREST', "Nearest Vertex", "Best for tight fitting or mismatched topology"),
        ],
        default='POLYINTERP_NEAREST'
    ))

    _set_scene_property("PureQ_enable_double_pass_clean", BoolProperty(
        name="Double-pass Cleanup",
        description="Run transfer twice and keep weights only on garment-detected vertices to minimize contamination",
        default=True
    ))

    _set_scene_property("PureQ_seed_weight_threshold", FloatProperty(
        name="Seed Threshold",
        description="Minimum weight in pass 1 to mark a vertex as garment-owned for pass 2",
        default=0.002,
        min=0.0,
        max=1.0
    ))

    from .model_profile_db import enum_categories, enum_lengths, enum_model_types, enum_model_profiles, enum_styles
    _set_scene_property("PureQ_new_model_name", StringProperty(
        name="New Model Name",
        description="Name for the new model profile",
        default="MyModel"
    ))

    _set_scene_property("PureQ_new_model_category", EnumProperty(
        name="Category",
        description="Category for the new model",
        items=enum_categories
    ))

    _set_scene_property("PureQ_new_model_length", EnumProperty(
        name="Length",
        description="Length for the new model",
        items=enum_lengths
    ))

    _set_scene_property("PureQ_new_model_type", EnumProperty(
        name="Type",
        description="Type for the new model",
        items=enum_model_types
    ))

    _set_scene_property("PureQ_new_model_style", EnumProperty(
        name="Style",
        description="Style for the new model",
        items=enum_styles
    ))

    _set_scene_property("PureQ_new_model_description", StringProperty(
        name="Description",
        description="Description for the new model",
        default="Model description"
    ))

    _set_scene_property("PureQ_new_min_weight", FloatProperty(
        name="Min Weight",
        description="Minimum weight threshold",
        default=0.001,
        min=0.0,
        max=1.0
    ))

    _set_scene_property("PureQ_new_max_influences", IntProperty(
        name="Max Influences",
        description="Maximum number of bone influences",
        default=4,
        min=1,
        max=8
    ))

    _set_scene_property("PureQ_selected_model_profile", EnumProperty(
        name="Model Profile",
        description="Select a model profile to use",
        items=enum_model_profiles
    ))

    _ensure_runtime_defaults()

def unregister():
    global _registered_modules

    for module_info in reversed(_registered_modules):
        _safe_unregister_module(module_info)
    _registered_modules = []

    for prop_name in _SCENE_PROPERTIES:
        _delete_scene_property(prop_name)

    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except (RuntimeError, ValueError):
            pass


_registered_modules = []
_SUBMODULE_REGISTRY = [
    ("operators", "register", "unregister", False),
    ("diagnostic", "register", "unregister", False),
    ("PureQ_profile_extension", "register", "unregister", False),
    ("model_profile_manager", "register", "unregister", False),
    ("profile_editor", "register", "unregister", False),
    ("profile_import_export", "register", "unregister", False),
    ("profile_search", "register", "unregister", False),
    ("profile_favorites", "register", "unregister", False),
    ("rig_detector", "register", "unregister", False),
    ("profile_validator", "register", "unregister", False),
    ("avatar_profile_organizer", "register", "unregister", False),
]
_SCENE_PROPERTIES = [
    "PureQ_bone_list",
    "PureQ_bone_list_index",
    "PureQ_addon_mode",
    "PureQ_smooth_factor",
    "PureQ_auto_smooth",
    "PureQ_smooth_iterations",
    "PureQ_clothing_type",
    "PureQ_clean_threshold",
    "PureQ_quantize_steps",
    "PureQ_levels_low",
    "PureQ_levels_high",
    "PureQ_use_PureQ_validation",
    "PureQ_bone_profile",
    "PureQ_garment_model",
    "PureQ_apply_lods",
    "PureQ_transfer_method",
    "PureQ_enable_double_pass_clean",
    "PureQ_seed_weight_threshold",
    "PureQ_new_model_name",
    "PureQ_new_model_category",
    "PureQ_new_model_length",
    "PureQ_new_model_type",
    "PureQ_new_model_style",
    "PureQ_new_model_description",
    "PureQ_new_min_weight",
    "PureQ_new_max_influences",
    "PureQ_selected_model_profile",
]


def _set_scene_property(name, value):
    # Re-register property to avoid stale definitions after failed reloads.
    if hasattr(bpy.types.Scene, name):
        try:
            delattr(bpy.types.Scene, name)
        except Exception:
            pass
    setattr(bpy.types.Scene, name, value)


def _delete_scene_property(name):
    if hasattr(bpy.types.Scene, name):
        delattr(bpy.types.Scene, name)


def _safe_import_module(module_name, force_reload=False):
    try:
        if __package__:
            module = importlib.import_module(f".{module_name}", __package__)
        else:
            module = importlib.import_module(module_name)
        if force_reload:
            module = importlib.reload(module)
        return module
    except Exception as e:
        print(f"Warning: Failed to import module '{module_name}': {e}")
        return None


def _safe_register_module(module_name, register_fn, unregister_fn, force_reload=False):
    module = _safe_import_module(module_name, force_reload=force_reload)
    if not module:
        return

    fn = getattr(module, register_fn, None)
    if not callable(fn):
        print(f"Warning: Module '{module_name}' has no callable '{register_fn}'")
        return

    try:
        fn()
        _registered_modules.append((module_name, unregister_fn))
    except Exception as e:
        print(f"Warning: Failed to register module '{module_name}': {e}")


def _safe_unregister_module(module_info):
    module_name, unregister_fn = module_info
    module = _safe_import_module(module_name, force_reload=False)
    if not module:
        return

    fn = getattr(module, unregister_fn, None)
    if not callable(fn):
        return

    try:
        fn()
    except Exception as e:
        print(f"Warning: Failed to unregister module '{module_name}': {e}")


def _ensure_runtime_defaults():
    """Ensure dynamic enum properties have a usable default in current scene."""
    # Ensure user storage shipped with addon exists on first run.
    try:
        from .core.bone_profiles import ensure_user_bone_profile_storage
        from .model_profile_db import PureQ_ProfileDatabase
        ensure_user_bone_profile_storage()
        PureQ_ProfileDatabase.ensure_user_profile_storage()
    except Exception:
        pass

    try:
        scene = bpy.context.scene
    except Exception:
        return

    if not scene:
        return

    # Do not auto-select transfer profiles.
    # User must explicitly choose Bone Profile or Model Profile to avoid accidental mismatch.

if __name__ == "__main__":
    register()


