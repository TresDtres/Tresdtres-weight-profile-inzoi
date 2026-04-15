"""
Módulo para el gestor de perfiles de modelos
"""
import bpy
from bpy.props import StringProperty, EnumProperty, IntProperty, FloatProperty, BoolProperty
from .model_profile_db import PureQ_ProfileDatabase, enum_model_profiles, enum_categories, enum_lengths, enum_model_types, enum_styles
from .core.i18n import tr


I18N = {
    "empty_model_name": {"es": "El nombre del modelo no puede estar vacio", "en": "Model name cannot be empty"},
    "added_model_profile": {"es": "Perfil de modelo agregado", "en": "Added model profile"},
    "loaded_profile_with_bones": {"es": "Perfil cargado con huesos permitidos", "en": "Loaded model profile with allowed bones"},
    "loaded_and_matched": {"es": "Perfil cargado y Bone Profile vinculado", "en": "Loaded and matched Bone Profile"},
    "loaded_and_synced": {"es": "Perfil cargado y Bone Profile sincronizado", "en": "Loaded and synced Bone Profile"},
    "loaded_manual_select": {"es": "Perfil cargado. Selecciona Bone Profile manualmente en TRANSFER", "en": "Loaded model profile. Select Bone Profile manually in TRANSFER mode."},
    "model_profile_not_found": {"es": "Perfil de modelo no encontrado", "en": "Model profile not found"},
    "no_model_profile_selected": {"es": "No hay perfil de modelo seleccionado", "en": "No model profile selected"},
    "base_profile_cannot_delete": {"es": "Es un perfil base y no puede borrarse. Crea/sobrescribe en User_Profiles para gestionarlo.", "en": "It is a base profile and cannot be deleted. Create/override it in User_Profiles to manage it."},
    "deleted_profile": {"es": "Perfil de modelo eliminado", "en": "Deleted model profile"},
    "no_model_profile_specified": {"es": "No se especifico perfil de modelo", "en": "No model profile specified"},
    "confirm_delete": {"es": "Eliminar perfil de modelo", "en": "Delete model profile"},
    "cannot_undo": {"es": "Esta accion no se puede deshacer.", "en": "This action cannot be undone."},
    "are_you_sure": {"es": "Seguro que quieres eliminar este perfil?", "en": "Are you sure you want to delete this profile?"},
    "manager_not_initialized": {"es": "Profile Manager no se inicializo completamente", "en": "Profile Manager not initialized completely"},
    "missing_prop": {"es": "Falta", "en": "Missing"},
    "restart_tip": {"es": "Tip: desactiva/activa el addon o reinicia Blender", "en": "Tip: disable/enable addon or restart Blender"},
    "create_new_profile": {"es": "Crear nuevo perfil de modelo", "en": "Create New Model Profile"},
    "name": {"es": "Nombre", "en": "Name"},
    "category": {"es": "Categoria", "en": "Category"},
    "length": {"es": "Longitud", "en": "Length"},
    "type": {"es": "Tipo", "en": "Type"},
    "style": {"es": "Estilo", "en": "Style"},
    "description": {"es": "Descripcion", "en": "Description"},
    "min_weight": {"es": "Peso minimo", "en": "Min Weight"},
    "max_influences": {"es": "Max influencias", "en": "Max Influences"},
    "select_model_profile": {"es": "Seleccionar perfil de modelo", "en": "Select Model Profile"},
    "unknown": {"es": "Desconocido", "en": "Unknown"},
    "profile_info": {"es": "Info de perfil", "en": "Profile Info"},
    "allowed_bones": {"es": "Huesos permitidos", "en": "Allowed bones"},
    "delete_profile": {"es": "Eliminar perfil", "en": "Delete Profile"},
    "suggested_bone_profile": {"es": "Bone Profile sugerido", "en": "Suggested Bone Profile"},
    "no_auto_suggestion": {"es": "Sin sugerencia automatica de Bone Profile", "en": "No automatic Bone Profile suggestion"},
    "apply_as_bone_profile": {"es": "Aplicar como Bone Profile", "en": "Apply as Bone Profile"},
    "ui_error": {"es": "Error de UI en Profile Manager", "en": "Profile Manager UI error"},
    "console_details": {"es": "Revisa la consola de Blender para detalles", "en": "Check Blender Console for details"},
    "cannot_infer_bone_profile": {"es": "No se pudo inferir Bone Profile para este Model Profile", "en": "Could not infer a Bone Profile from this Model Profile"},
    "bone_profile_not_found": {"es": "Bone Profile no encontrado en data/bone_profiles.json", "en": "Bone Profile not found in data/bone_profiles.json"},
    "bone_profile_applied": {"es": "Bone Profile aplicado", "en": "Bone Profile applied"},
}


def _t(key, default_en=""):
    return tr(key, I18N, default_en=default_en)

def _norm_key(value):
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())

def _find_matching_bone_profile(candidate_values, available_profiles):
    """Return first exact normalized name match."""
    norm_map = {_norm_key(name): name for name in available_profiles}
    for value in candidate_values:
        key = _norm_key(value)
        if key and key in norm_map:
            return norm_map[key]
    return None


def _infer_bone_profile_from_model_data(model_data):
    """Infer best matching transfer bone profile from a model profile."""
    if not model_data:
        return None

    model_type = (model_data.get("model_type") or "").lower()
    length = (model_data.get("length") or "").lower()

    if model_type == "skirt":
        if length in {"short", "mini"}:
            return "SHORT_SKIRT"
        if length in {"long", "maxi"}:
            return "LONG_SKIRT"
        return "MEDIUM_SKIRT"

    if model_type in {"pants", "shorts", "trousers", "jeans", "legging", "leggings"}:
        return "TROUSERS"

    if model_type in {"shirt", "top", "blouse", "tee", "sweater", "hoodie", "vest"}:
        return "SHIRT"

    if model_type in {"jacket", "coat", "blazer"}:
        return "JACKET"

    return None


class PureQ_OT_AddModelProfile(bpy.types.Operator):
    """Añade un nuevo perfil de modelo a la base de datos"""
    bl_idname = "pureq.add_model_profile"
    bl_label = "Add Model Profile"
    bl_description = "Add a new model profile to the database"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Propiedades para la creación del modelo
    model_name: StringProperty(
        name="Model Name",
        description="Name of the model/clothing item",
        default="New Model"
    )
    
    category: EnumProperty(
        name="Category",
        description="Category of the model",
        items=enum_categories
    )
    
    length: EnumProperty(
        name="Length",
        description="Length of the garment",
        items=enum_lengths
    )
    
    model_type: EnumProperty(
        name="Model Type",
        description="Type of model",
        items=enum_model_types
    )

    style: EnumProperty(
        name="Style",
        description="Visual style of the model",
        items=enum_styles
    )
    
    description: StringProperty(
        name="Description",
        description="Description of the model",
        default="Model description"
    )
    
    # Propiedades del perfil
    min_weight: FloatProperty(
        name="Min Weight",
        description="Minimum weight threshold for filtering",
        default=0.001,
        min=0.0,
        max=1.0
    )
    
    max_influences: IntProperty(
        name="Max Influences",
        description="Maximum number of bone influences per vertex",
        default=4,
        min=1,
        max=8
    )
    
    def execute(self, context):
        scene = context.scene

        # Use scene fields from the manager panel to avoid desync/confusion.
        model_name = (scene.PureQ_new_model_name or self.model_name).strip()
        category = scene.PureQ_new_model_category or self.category
        length = scene.PureQ_new_model_length or self.length
        model_type = scene.PureQ_new_model_type or self.model_type
        style = scene.PureQ_new_model_style or self.style
        description = scene.PureQ_new_model_description or self.description
        min_weight = scene.PureQ_new_min_weight
        max_influences = scene.PureQ_new_max_influences

        if not model_name:
            self.report({'ERROR'}, _t("empty_model_name", "Model name cannot be empty"))
            return {'CANCELLED'}

        # Crear el perfil base basado en las selecciones
        profile_data = {
            "allowed_bones": self._get_default_bones_for_type(model_type, length),
            "forbidden_bones": self._get_default_forbidden_bones(),
            "min_weight": min_weight,
            "max_influences": max_influences
        }
        
        # Añadir el perfil a la base de datos
        model_key = PureQ_ProfileDatabase.add_model_profile(
            model_name,
            category,
            length,
            model_type,
            description,
            profile_data,
            style=style
        )
        scene.PureQ_selected_model_profile = model_key
        
        self.report({'INFO'}, f"{_t('added_model_profile')}: {model_key}")
        return {'FINISHED'}
    
    def _get_default_bones_for_type(self, model_type, length):
        """Obtiene huesos por defecto basados en el tipo y longitud"""
        lower_body_short = ["pelvis", "thigh_l", "thigh_r", "thigh_twist_01_l", "thigh_twist_01_r"]
        lower_body_mid = lower_body_short + ["calf_l", "calf_r"]
        lower_body_long = lower_body_mid + ["thigh_twist_02_l", "thigh_twist_02_r", "calf_twist_01_l", "calf_twist_01_r"]
        upper_core = ["spine_01", "spine_02", "spine_03", "clavicle_l", "clavicle_r", "upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r"]
        upper_extended = upper_core + ["spine_04", "spine_05"]

        bone_sets = {
            "skirt": {
                "micro": lower_body_short,
                "mini": lower_body_short,
                "short": lower_body_short,
                "mid": lower_body_mid,
                "medium": lower_body_mid,
                "midi": lower_body_mid,
                "long": lower_body_long,
                "maxi": lower_body_long,
                "floor": lower_body_long,
            },
            "shorts": {
                "micro": lower_body_short,
                "short": lower_body_short,
                "medium": lower_body_mid,
            },
            "pants": {
                "short": lower_body_mid,
                "medium": lower_body_mid,
                "long": lower_body_long,
                "maxi": lower_body_long,
            },
            "jeans": {"long": lower_body_long},
            "leggings": {"long": lower_body_long},
            "dress": {
                "mini": list(dict.fromkeys(lower_body_short + upper_core)),
                "short": list(dict.fromkeys(lower_body_short + upper_core)),
                "medium": list(dict.fromkeys(lower_body_mid + upper_core)),
                "long": list(dict.fromkeys(lower_body_long + upper_core)),
                "maxi": list(dict.fromkeys(lower_body_long + upper_core)),
            },
            "top": {"cropped": upper_core, "short": upper_core, "medium": upper_core},
            "shirt": {"short": upper_core, "medium": upper_core},
            "blouse": {"short": upper_core, "medium": upper_core},
            "sweater": {"short": upper_extended, "medium": upper_extended},
            "hoodie": {"short": upper_extended, "medium": upper_extended},
            "vest": {"short": upper_core, "medium": upper_core},
            "jacket": {"short": upper_extended, "medium": upper_extended},
            "coat": {"long": list(dict.fromkeys(lower_body_mid + upper_extended))},
            "blazer": {"short": upper_extended, "medium": upper_extended},
        }
        
        # Obtener huesos por defecto o usar un conjunto genérico
        default_bones = bone_sets.get(model_type, {}).get(length, ["pelvis", "thigh_l", "thigh_r"])
        if not default_bones:
            default_bones = ["pelvis", "thigh_l", "thigh_r"]
        return default_bones
    
    def _get_default_forbidden_bones(self):
        """Obtiene huesos prohibidos por defecto"""
        return ["foot_l", "foot_r", "ball_l", "ball_r", "bigtoe_01_l", "bigtoe_01_r"]


class PureQ_OT_LoadSelectedModelProfile(bpy.types.Operator):
    """Carga el perfil de modelo seleccionado"""
    bl_idname = "pureq.load_selected_model_profile"
    bl_label = "Load Selected Model Profile"
    bl_description = "Load the selected model profile for use"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        model_key = scene.PureQ_selected_model_profile
        
        if model_key and model_key != "NONE":
            model_data = PureQ_ProfileDatabase.get_model_profile(model_key)
            if model_data:
                profile = model_data.get("profile", {})
                
                # Aquí iría la lógica para aplicar el perfil al objeto seleccionado
                # Por ahora solo mostramos información
                allowed_bones = profile.get("allowed_bones", [])
                self.report({'INFO'}, f"{_t('loaded_profile_with_bones')}: '{model_key}' ({len(allowed_bones)})")
                
                # Opcional: guardar el perfil en las propiedades de la escena para su uso posterior
                scene.PureQ_current_profile_data = str(profile)

                # Try to sync transfer profile automatically when possible.
                try:
                    from .core.bone_profiles import get_bone_profile_names
                    available = list(get_bone_profile_names())
                    matched = _find_matching_bone_profile(
                        [model_key, model_data.get("name"), model_data.get("model_type"), model_data.get("category")],
                        available
                    )
                    inferred = _infer_bone_profile_from_model_data(model_data)

                    if matched:
                        scene.PureQ_bone_profile = matched
                        self.report({'INFO'}, f"{_t('loaded_and_matched')}: {matched}")
                    elif inferred and inferred in set(available):
                        scene.PureQ_bone_profile = inferred
                        self.report({'INFO'}, f"{_t('loaded_and_synced')}: {inferred}")
                    else:
                        self.report({'INFO'}, _t("loaded_manual_select"))
                except Exception:
                    pass

                # Optional object-level bridge for fast re-use in transfer mode.
                if context.active_object and context.active_object.type == 'MESH':
                    context.active_object["PureQ_model_profile"] = model_key
                
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"{_t('model_profile_not_found')}: '{model_key}'")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, _t("no_model_profile_selected"))
            return {'CANCELLED'}


class PureQ_OT_DeleteModelProfile(bpy.types.Operator):
    """Elimina un perfil de modelo de la base de datos"""
    bl_idname = "pureq.delete_model_profile"
    bl_label = "Delete Model Profile"
    bl_description = "Delete the selected model profile from the database"
    bl_options = {'REGISTER', 'UNDO'}
    
    model_key: StringProperty(
        name="Model Key",
        description="Key of the model profile to delete"
    )
    
    @classmethod
    def poll(cls, context):
        return context.scene.PureQ_selected_model_profile and context.scene.PureQ_selected_model_profile != "NONE"
    
    def execute(self, context):
        if self.model_key:
            merged = PureQ_ProfileDatabase.load_model_profiles()
            if self.model_key in merged:
                deleted = PureQ_ProfileDatabase.delete_user_profile(self.model_key)
                if not deleted:
                    self.report(
                        {'WARNING'},
                        f"'{self.model_key}': {_t('base_profile_cannot_delete')}"
                    )
                    return {'CANCELLED'}
                self.report({'INFO'}, f"{_t('deleted_profile')}: {self.model_key}")
                
                # Limpiar la selección actual
                context.scene.PureQ_selected_model_profile = "NONE"
                
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"{_t('model_profile_not_found')}: '{self.model_key}'")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, _t("no_model_profile_specified"))
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        # Usar el modelo seleccionado actualmente
        self.model_key = context.scene.PureQ_selected_model_profile
        return context.window_manager.invoke_props_dialog(self, width=400)
    
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text=f"{_t('confirm_delete')}: {self.model_key}?", icon='ERROR')
        col.label(text=_t("cannot_undo"), icon='BLANK1')
        col.label(text=_t("are_you_sure"))


class PUREQ_PT_ModelProfileManager(bpy.types.Panel):
    """Panel para el gestor de perfiles de modelos"""
    bl_label = "Model Profile Manager"
    bl_idname = "PUREQ_PT_model_profile_manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PureQ Weight Transfer'
    
    @classmethod
    def poll(cls, context):
        # Only show if in MANAGER mode
        return getattr(context.scene, "PureQ_addon_mode", "TRANSFER") == 'MANAGER'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        try:
            required_props = [
                "PureQ_new_model_name",
                "PureQ_new_model_category",
                "PureQ_new_model_length",
                "PureQ_new_model_type",
                "PureQ_new_model_description",
                "PureQ_new_min_weight",
                "PureQ_new_max_influences",
                "PureQ_selected_model_profile",
            ]
            missing = [p for p in required_props if not hasattr(scene, p)]
            if missing:
                warn_box = layout.box()
                warn_box.label(text=_t("manager_not_initialized"), icon='ERROR')
                for p in missing[:4]:
                    warn_box.label(text=f"{_t('missing_prop')}: {p}", icon='DOT')
                warn_box.label(text=_t("restart_tip"), icon='INFO')
                return

            # Crear nuevo perfil
            box = layout.box()
            box.label(text=_t("create_new_profile"), icon='ADD')

            col = box.column(align=True)
            col.prop(scene, "PureQ_new_model_name", text=_t("name"))
            col.prop(scene, "PureQ_new_model_category", text=_t("category"))
            col.prop(scene, "PureQ_new_model_length", text=_t("length"))
            col.prop(scene, "PureQ_new_model_type", text=_t("type"))
            col.prop(scene, "PureQ_new_model_style", text=_t("style"))
            col.prop(scene, "PureQ_new_model_description", text=_t("description"))

            col.separator()

            profile_col = box.column(align=True)
            profile_col.prop(scene, "PureQ_new_min_weight", text=_t("min_weight"))
            profile_col.prop(scene, "PureQ_new_max_influences", text=_t("max_influences"))

            box.operator("pureq.add_model_profile", icon='FILE_TICK')

            # Separador
            layout.separator()

            # Seleccionar perfil existente
            box = layout.box()
            box.label(text=_t("select_model_profile"), icon='GROUP_BONE')

            row = box.row()
            row.prop(scene, "PureQ_selected_model_profile", text="")
            row.operator("pureq.load_selected_model_profile", icon='IMPORT', text="")

            # Mostrar información del perfil seleccionado si hay uno seleccionado
            if scene.PureQ_selected_model_profile and scene.PureQ_selected_model_profile != "NONE":
                model_data = PureQ_ProfileDatabase.get_model_profile(scene.PureQ_selected_model_profile)
                if model_data:
                    info_box = box.box()
                    info_col = info_box.column(align=True)
                    info_col.label(text=f"{_t('name')}: {model_data.get('name', _t('unknown'))}", icon='INFO')
                    info_col.label(text=f"{_t('category')}: {model_data.get('category', _t('unknown'))}")
                    info_col.label(text=f"{_t('length')}: {model_data.get('length', _t('unknown'))}")
                    info_col.label(text=f"{_t('type')}: {model_data.get('model_type', _t('unknown'))}")
                    info_col.label(text=f"{_t('style')}: {model_data.get('style', 'custom')}")

                    profile = model_data.get("profile", {})
                    info_col.separator()
                    info_col.label(text=f"{_t('profile_info')}:", icon='SETTINGS')
                    info_col.label(text=f"{_t('allowed_bones')}: {len(profile.get('allowed_bones', []))}")
                    info_col.label(text=f"{_t('min_weight')}: {profile.get('min_weight', 0.0):.3f}")
                    info_col.label(text=f"{_t('max_influences')}: {profile.get('max_influences', 4)}")

                    # Botón para eliminar perfil
                    del_row = info_box.row()
                    del_row.operator("pureq.delete_model_profile", text=_t("delete_profile"), icon='TRASH').model_key = scene.PureQ_selected_model_profile

                    # Sync helper for transfer profile
                    inferred = _infer_bone_profile_from_model_data(model_data)
                    helper_box = box.box()
                    if inferred:
                        helper_box.label(text=f"{_t('suggested_bone_profile')}: {inferred}", icon='INFO')
                    else:
                        helper_box.label(text=_t("no_auto_suggestion"), icon='ERROR')
                    helper_box.operator("pureq.apply_model_profile_as_bone_profile", text=_t("apply_as_bone_profile"), icon='FILE_TICK')
        except Exception as e:
            error_box = layout.box()
            error_box.label(text=_t("ui_error"), icon='ERROR')
            error_box.label(text=str(e), icon='DOT')
            error_box.label(text=_t("console_details"), icon='INFO')


class PureQ_OT_ApplyModelProfileAsBoneProfile(bpy.types.Operator):
    """Apply inferred bone profile from selected model profile"""
    bl_idname = "pureq.apply_model_profile_as_bone_profile"
    bl_label = "Apply as Bone Profile"
    bl_description = "Apply a suggested transfer Bone Profile from selected Model Profile"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        model_key = scene.PureQ_selected_model_profile
        if not model_key or model_key == "NONE":
            self.report({'ERROR'}, _t("no_model_profile_selected"))
            return {'CANCELLED'}

        model_data = PureQ_ProfileDatabase.get_model_profile(model_key)
        if not model_data:
            self.report({'ERROR'}, f"{_t('model_profile_not_found')}: '{model_key}'")
            return {'CANCELLED'}

        inferred = _infer_bone_profile_from_model_data(model_data)
        if not inferred:
            self.report({'ERROR'}, _t("cannot_infer_bone_profile"))
            return {'CANCELLED'}

        from .core.bone_profiles import get_bone_profile_names
        if inferred not in set(get_bone_profile_names()):
            self.report({'ERROR'}, f"{_t('bone_profile_not_found')}: '{inferred}'")
            return {'CANCELLED'}

        scene.PureQ_bone_profile = inferred
        self.report({'INFO'}, f"{_t('bone_profile_applied')}: {inferred}")
        return {'FINISHED'}


def register():
    # Registrar operadores
    bpy.utils.register_class(PureQ_OT_AddModelProfile)
    bpy.utils.register_class(PureQ_OT_LoadSelectedModelProfile)
    bpy.utils.register_class(PureQ_OT_DeleteModelProfile)
    bpy.utils.register_class(PureQ_OT_ApplyModelProfileAsBoneProfile)
    bpy.utils.register_class(PUREQ_PT_ModelProfileManager)

    # Note: Properties are registered in the main __init__.py file to avoid duplicate registration errors


def unregister():
    # Desregistrar operadores
    bpy.utils.unregister_class(PureQ_OT_AddModelProfile)
    bpy.utils.unregister_class(PureQ_OT_LoadSelectedModelProfile)
    bpy.utils.unregister_class(PureQ_OT_DeleteModelProfile)
    bpy.utils.unregister_class(PureQ_OT_ApplyModelProfileAsBoneProfile)
    bpy.utils.unregister_class(PUREQ_PT_ModelProfileManager)

    # Note: Properties are unregistered in the main __init__.py file


