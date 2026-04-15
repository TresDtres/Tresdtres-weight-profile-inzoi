"""
Módulo para el editor avanzado de perfiles
"""
import bpy
from bpy.props import StringProperty, BoolProperty, CollectionProperty, IntProperty
from .model_profile_db import PureQ_ProfileDatabase
from .core.i18n import tr


I18N = {
    "no_model_selected": {"es": "No hay perfil de modelo seleccionado", "en": "No model profile selected"},
    "model_not_found": {"es": "Perfil de modelo no encontrado", "en": "Model profile not found"},
    "loaded_bones": {"es": "Cargados huesos permitidos/prohibidos", "en": "Loaded allowed and forbidden bones"},
    "saved_changes": {"es": "Cambios guardados en perfil", "en": "Saved changes to profile"},
    "empty_bone_name": {"es": "El nombre del hueso no puede estar vacio", "en": "Bone name cannot be empty"},
    "bone_exists": {"es": "El hueso ya existe en esta categoria", "en": "Bone already exists in this category"},
    "added_bone": {"es": "Hueso agregado", "en": "Added bone"},
    "allowed": {"es": "permitido", "en": "allowed"},
    "forbidden": {"es": "prohibido", "en": "forbidden"},
    "removed_bones": {"es": "Huesos eliminados del perfil", "en": "Removed bones from profile"},
    "select_profile_hint": {"es": "Selecciona un perfil de modelo para editar huesos", "en": "Select a model profile to edit bones"},
    "add_bones": {"es": "Agregar huesos", "en": "Add Bones"},
    "add_allowed": {"es": "Agregar permitido", "en": "Add Allowed"},
    "add_forbidden": {"es": "Agregar prohibido", "en": "Add Forbidden"},
    "profile_bones": {"es": "Huesos del perfil", "en": "Profile Bones"},
    "select_all": {"es": "Seleccionar todo", "en": "Select All"},
    "deselect_all": {"es": "Deseleccionar todo", "en": "Deselect All"},
    "allowed_btn": {"es": "Permitidos", "en": "Allowed"},
    "forbidden_btn": {"es": "Prohibidos", "en": "Forbidden"},
    "remove_selected": {"es": "Eliminar seleccionados", "en": "Remove Selected"},
    "save_changes": {"es": "Guardar cambios en perfil", "en": "Save Changes to Profile"},
    "bone_name": {"es": "Nombre del hueso", "en": "Bone Name"},
}


def _t(key, default_en=""):
    return tr(key, I18N, default_en=default_en)


class PureQ_BoneItem(bpy.types.PropertyGroup):
    """Item para la lista de huesos"""
    name: StringProperty(name="Bone Name")
    enabled: BoolProperty(name="Enabled", default=True)
    is_allowed: BoolProperty(name="Is Allowed Bone", default=True)  # True for allowed, False for forbidden


class PureQ_OT_RefreshProfileBones(bpy.types.Operator):
    """Carga los huesos del perfil seleccionado en la lista de edición"""
    bl_idname = "pureq.pm_refresh_profile_bones"
    bl_label = "Refresh Profile Bones"
    bl_description = "Load bones from the selected profile into the editor"
    
    def execute(self, context):
        scene = context.scene
        model_key = scene.PureQ_selected_model_profile
        
        if not model_key or model_key == "NONE":
            self.report({'WARNING'}, "No model profile selected")
            return {'CANCELLED'}
        
        # Limpiar lista existente
        scene.PureQ_profile_bones.clear()
        
        # Cargar el perfil
        model_data = PureQ_ProfileDatabase.get_model_profile(model_key)
        if not model_data:
            self.report({'ERROR'}, f"Model profile '{model_key}' not found")
            return {'CANCELLED'}
        
        profile = model_data.get("profile", {})
        allowed_bones = profile.get("allowed_bones", [])
        forbidden_bones = profile.get("forbidden_bones", [])
        
        # Añadir huesos permitidos
        for bone_name in sorted(allowed_bones):
            item = scene.PureQ_profile_bones.add()
            item.name = bone_name
            item.enabled = True
            item.is_allowed = True
        
        # Añadir huesos prohibidos
        for bone_name in sorted(forbidden_bones):
            item = scene.PureQ_profile_bones.add()
            item.name = bone_name
            item.enabled = True
            item.is_allowed = False
        
        self.report({'INFO'}, f"Loaded {len(allowed_bones)} allowed and {len(forbidden_bones)} forbidden bones")
        return {'FINISHED'}


class PureQ_OT_SaveProfileBones(bpy.types.Operator):
    """Guarda los cambios en los huesos del perfil"""
    bl_idname = "pureq.save_profile_bones"
    bl_label = "Save Profile Changes"
    bl_description = "Save the bone changes to the selected profile"
    
    def execute(self, context):
        scene = context.scene
        model_key = scene.PureQ_selected_model_profile
        
        if not model_key or model_key == "NONE":
            self.report({'ERROR'}, "No model profile selected")
            return {'CANCELLED'}
        
        # Cargar el perfil existente (puede venir de base o de usuario)
        model_data = PureQ_ProfileDatabase.get_model_profile(model_key)
        if not model_data:
            self.report({'ERROR'}, f"Model profile '{model_key}' not found")
            return {'CANCELLED'}
        
        # Separar huesos permitidos y prohibidos
        allowed_bones = set()
        forbidden_bones = set()
        
        for item in scene.PureQ_profile_bones:
            if item.enabled:
                if item.is_allowed:
                    allowed_bones.add(item.name)
                else:
                    forbidden_bones.add(item.name)
        
        # Actualizar el perfil con los nuevos huesos
        profile_data = dict(model_data.get("profile", {}))
        profile_data["allowed_bones"] = list(allowed_bones)
        profile_data["forbidden_bones"] = list(forbidden_bones)
        model_data = dict(model_data)
        model_data["profile"] = profile_data
        
        # Guardar siempre en usuario (override limpio sobre base si aplica)
        PureQ_ProfileDatabase.upsert_user_profile(model_key, model_data)
        
        self.report({'INFO'}, f"Saved changes to profile '{model_key}' with {len(allowed_bones)} allowed and {len(forbidden_bones)} forbidden bones")
        return {'FINISHED'}


class PureQ_OT_AddBoneToProfile(bpy.types.Operator):
    """Añade un hueso al perfil"""
    bl_idname = "pureq.add_bone_to_profile"
    bl_label = "Add Bone"
    bl_description = "Add a bone to the profile"
    
    bone_name: StringProperty(name="Bone Name", description="Name of the bone to add")
    is_allowed: BoolProperty(name="Add as Allowed", description="Add as allowed (True) or forbidden (False)", default=True)
    
    def execute(self, context):
        if not self.bone_name:
            self.report({'ERROR'}, "Bone name cannot be empty")
            return {'CANCELLED'}
        
        scene = context.scene
        
        # Verificar que no exista ya
        for item in scene.PureQ_profile_bones:
            if item.name == self.bone_name and item.is_allowed == self.is_allowed:
                self.report({'WARNING'}, f"Bone '{self.bone_name}' already exists in this category")
                return {'CANCELLED'}
        
        # Añadir el hueso
        item = scene.PureQ_profile_bones.add()
        item.name = self.bone_name
        item.enabled = True
        item.is_allowed = self.is_allowed
        
        action = "allowed" if self.is_allowed else "forbidden"
        self.report({'INFO'}, f"Added '{self.bone_name}' to {action} bones")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)
    
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "bone_name", text="Bone Name")
        
        row = col.row()
        row.prop(self, "is_allowed", expand=True)


class PureQ_OT_RemoveSelectedBones(bpy.types.Operator):
    """Elimina los huesos seleccionados del perfil"""
    bl_idname = "pureq.remove_selected_bones"
    bl_label = "Remove Selected"
    bl_description = "Remove selected bones from the profile"
    
    def execute(self, context):
        scene = context.scene
        
        # Recoger índices a eliminar en orden inverso para no afectar los índices
        to_remove = []
        for i, item in enumerate(scene.PureQ_profile_bones):
            if item.enabled:
                to_remove.insert(0, i)  # Insertar al principio para mantener orden
        
        removed_count = 0
        for i in to_remove:
            scene.PureQ_profile_bones.remove(i)
            removed_count += 1
        
        self.report({'INFO'}, f"Removed {removed_count} bones from profile")
        return {'FINISHED'}


class PureQ_OT_BoneListActions(bpy.types.Operator):
    """Acciones para la lista de huesos"""
    bl_idname = "pureq.pm_bone_list_actions"
    bl_label = "Bone List Actions"
    bl_description = "Select or deselect all bones in the list"
    
    action: bpy.props.EnumProperty(
        items=(
            ('SELECT_ALL', "Select All", ""),
            ('DESELECT_ALL', "Deselect All", ""),
            ('SELECT_ALLOWED', "Select Allowed", ""),
            ('SELECT_FORBIDDEN', "Select Forbidden", ""),
        )
    )
    
    def execute(self, context):
        scene = context.scene
        
        if self.action == 'SELECT_ALL':
            for item in scene.PureQ_profile_bones:
                item.enabled = True
        elif self.action == 'DESELECT_ALL':
            for item in scene.PureQ_profile_bones:
                item.enabled = False
        elif self.action == 'SELECT_ALLOWED':
            for item in scene.PureQ_profile_bones:
                if item.is_allowed:
                    item.enabled = True
                else:
                    item.enabled = False
        elif self.action == 'SELECT_FORBIDDEN':
            for item in scene.PureQ_profile_bones:
                if not item.is_allowed:
                    item.enabled = True
                else:
                    item.enabled = False
        
        return {'FINISHED'}


class PUREQ_UL_ProfileBones(bpy.types.UIList):
    """UI List para mostrar los huesos del perfil"""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Mostrar checkbox y nombre del hueso
            layout.prop(item, "enabled", text="")
            layout.label(text=item.name, icon='BONE_DATA' if item.is_allowed else 'X')
            
            # Mostrar si es permitido o prohibido
            if item.is_allowed:
                layout.label(text="", icon='CHECKMARK')
            else:
                layout.label(text="", icon='X')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='BONE_DATA')


class PUREQ_PT_ProfileEditor(bpy.types.Panel):
    """Panel para el editor avanzado de perfiles"""
    bl_label = "Profile Bone Editor"
    bl_idname = "PUREQ_PT_profile_editor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PureQ Weight Transfer'
    bl_parent_id = 'PUREQ_PT_model_profile_manager'  # Este panel será hijo del panel principal
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        model_key = scene.PureQ_selected_model_profile
        
        if not model_key or model_key == "NONE":
            box = layout.box()
            box.label(text="Select a model profile to edit bones", icon='INFO')
            return
        
        # Botón para refrescar huesos del perfil
        row = layout.row()
        row.operator("pureq.pm_refresh_profile_bones", icon='FILE_REFRESH')
        
        # Controles para añadir huesos
        box = layout.box()
        box.label(text="Add Bones", icon='ADD')
        
        row = box.row(align=True)
        row.operator("pureq.add_bone_to_profile", text="Add Allowed", icon='CHECKMARK').is_allowed = True
        row.operator("pureq.add_bone_to_profile", text="Add Forbidden", icon='X').is_allowed = False
        
        # Lista de huesos
        if len(scene.PureQ_profile_bones) > 0:
            bones_box = layout.box()
            bones_box.label(text="Profile Bones", icon='BONE_DATA')
            
            # Controles de selección
            row = bones_box.row(align=True)
            row.operator("pureq.pm_bone_list_actions", text="Select All").action = 'SELECT_ALL'
            row.operator("pureq.pm_bone_list_actions", text="Deselect All").action = 'DESELECT_ALL'
            row = bones_box.row(align=True)
            row.operator("pureq.pm_bone_list_actions", text="Allowed").action = 'SELECT_ALLOWED'
            row.operator("pureq.pm_bone_list_actions", text="Forbidden").action = 'SELECT_FORBIDDEN'
            
            # Lista de huesos
            rows = 2 if len(scene.PureQ_profile_bones) < 15 else 8
            bones_box.template_list("PUREQ_UL_ProfileBones", "", scene, "PureQ_profile_bones", scene, "PureQ_profile_bones_index", rows=rows)
            
            # Controles de eliminación
            row = bones_box.row()
            row.operator("pureq.remove_selected_bones", icon='REMOVE', text="Remove Selected")
        
        # Botón para guardar cambios
        if len(scene.PureQ_profile_bones) > 0:
            layout.separator()
            row = layout.row()
            row.operator("pureq.save_profile_bones", icon='SAVE_PREFS', text="Save Changes to Profile")


def register():
    # Registrar clases
    bpy.utils.register_class(PureQ_BoneItem)
    bpy.utils.register_class(PureQ_OT_RefreshProfileBones)
    bpy.utils.register_class(PureQ_OT_SaveProfileBones)
    bpy.utils.register_class(PureQ_OT_AddBoneToProfile)
    bpy.utils.register_class(PureQ_OT_RemoveSelectedBones)
    bpy.utils.register_class(PureQ_OT_BoneListActions)
    bpy.utils.register_class(PUREQ_UL_ProfileBones)
    bpy.utils.register_class(PUREQ_PT_ProfileEditor)
    
    # Registrar propiedades
    bpy.types.Scene.PureQ_profile_bones = CollectionProperty(type=PureQ_BoneItem)
    bpy.types.Scene.PureQ_profile_bones_index = IntProperty(name="Index for profile bones", default=0)


def unregister():
    # Desregistrar clases
    for cls in (
        PureQ_BoneItem,
        PureQ_OT_RefreshProfileBones,
        PureQ_OT_SaveProfileBones,
        PureQ_OT_AddBoneToProfile,
        PureQ_OT_RemoveSelectedBones,
        PureQ_OT_BoneListActions,
        PUREQ_UL_ProfileBones,
        PUREQ_PT_ProfileEditor,
    ):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    
    # Eliminar propiedades
    if hasattr(bpy.types.Scene, 'PureQ_profile_bones'):
        del bpy.types.Scene.PureQ_profile_bones
    if hasattr(bpy.types.Scene, 'PureQ_profile_bones_index'):
        del bpy.types.Scene.PureQ_profile_bones_index

