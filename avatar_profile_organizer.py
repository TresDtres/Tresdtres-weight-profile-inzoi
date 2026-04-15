"""
Módulo para la organización de perfiles por avatar/modelo con carpetas y vistas previas
"""
import bpy
import json
import os
from bpy.props import StringProperty, EnumProperty, BoolProperty, IntProperty, FloatProperty, CollectionProperty
from .model_profile_db import PureQ_ProfileDatabase


class PureQ_AvatarProfileManager:
    """Clase para gestionar perfiles organizados por avatar/modelo"""
    
    @staticmethod
    def get_avatar_profiles_path(avatar_name, system_name="CUSTOM"):
        """Obtiene la ruta para los perfiles de un avatar específico"""
        base_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "avatar_profiles",
            system_name
        )

        # Limpiar el nombre del avatar para usarlo como nombre de carpeta
        safe_avatar_name = "".join(c for c in avatar_name if c.isalnum() or c in "._- ").rstrip()
        avatar_path = os.path.join(base_path, safe_avatar_name)

        return avatar_path

    @classmethod
    def create_avatar_folder(cls, avatar_name, system_name="CUSTOM"):
        """Crea la carpeta para un avatar específico"""
        avatar_path = cls.get_avatar_profiles_path(avatar_name, system_name)
        os.makedirs(avatar_path, exist_ok=True)
        return avatar_path

    @classmethod
    def save_avatar_profile(cls, avatar_name, profile_name, profile_data, system_name="CUSTOM"):
        """Guarda un perfil específico para un avatar"""
        avatar_path = cls.get_avatar_profiles_path(avatar_name, system_name)
        os.makedirs(avatar_path, exist_ok=True)

        profile_file = os.path.join(avatar_path, f"{profile_name}.json")

        data = {
            "version": "1.0",
            "system": system_name,
            "avatar_name": avatar_name,
            "profile_name": profile_name,
            "profile_data": profile_data,
            "created_date": str(bpy.context.scene.frame_current)  # Fecha aproximada
        }

        with open(profile_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return profile_file

    @classmethod
    def load_avatar_profiles(cls, avatar_name, system_name="CUSTOM"):
        """Carga todos los perfiles para un avatar específico"""
        avatar_path = cls.get_avatar_profiles_path(avatar_name, system_name)
        if not os.path.exists(avatar_path):
            return {}

        profiles = {}
        for file_name in os.listdir(avatar_path):
            if file_name.endswith('.json'):
                file_path = os.path.join(avatar_path, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    profile_name = data.get('profile_name', file_name.replace('.json', ''))
                    profiles[profile_name] = data.get('profile_data', {})
                except Exception as e:
                    print(f"Error loading profile {file_name}: {e}")

        return profiles

    @classmethod
    def get_all_avatar_folders(cls, system_name="CUSTOM"):
        """Obtiene todas las carpetas de avatares en un sistema"""
        base_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "avatar_profiles",
            system_name
        )

        if not os.path.exists(base_path):
            return []

        folders = []
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path):
                folders.append(item)

        return folders


class PureQ_OT_CreateAvatarFolder(bpy.types.Operator):
    """Crea una carpeta para un avatar específico"""
    bl_idname = "pureq.create_avatar_folder"
    bl_label = "Create Avatar Folder"
    bl_description = "Create a folder for the specified avatar to organize profiles"
    
    avatar_name: StringProperty(
        name="Avatar Name",
        description="Name of the avatar to create a folder for",
        default="New_Avatar"
    )
    
    def execute(self, context):
        if not self.avatar_name.strip():
            self.report({'ERROR'}, "Avatar name cannot be empty")
            return {'CANCELLED'}

        try:
            system = context.scene.PureQ_avatar_system
            folder_path = PureQ_AvatarProfileManager.create_avatar_folder(self.avatar_name, system)
            context.scene.PureQ_custom_avatar_name = self.avatar_name # Update current selection
            self.report({'INFO'}, f"Created folder for avatar: {self.avatar_name}")
            print(f"Avatar folder created at: {folder_path}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create avatar folder: {str(e)}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        # Si hay un objeto seleccionado, usar su nombre como nombre de avatar
        obj = context.active_object
        if obj and obj.type == 'MESH':
            self.avatar_name = obj.name
        elif obj and obj.type == 'ARMATURE':
            self.avatar_name = obj.name
        else:
            self.avatar_name = context.scene.PureQ_custom_avatar_name

        return context.window_manager.invoke_props_dialog(self, width=400)
    
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "avatar_name", text="Avatar Name")


class PureQ_OT_SaveProfileToAvatar(bpy.types.Operator):
    """Guarda el perfil actual en la carpeta del avatar"""
    bl_idname = "pureq.save_profile_to_avatar"
    bl_label = "Save Profile to Avatar Folder"
    bl_description = "Save the selected profile to the avatar's folder"
    
    profile_key: StringProperty(name="Profile Key")
    avatar_name: StringProperty(name="Avatar Name")
    new_profile_name: StringProperty(
        name="New Profile Name",
        description="Name for the profile in the avatar's folder",
        default="Avatar_Profile"
    )
    
    def execute(self, context):
        if not self.profile_key or self.profile_key == "NONE":
            self.report({'ERROR'}, "No profile selected")
            return {'CANCELLED'}

        if not self.avatar_name.strip():
            self.report({'ERROR'}, "Avatar name cannot be empty")
            return {'CANCELLED'}

        if not self.new_profile_name.strip():
            self.report({'ERROR'}, "Profile name cannot be empty")
            return {'CANCELLED'}

        # Obtener el perfil original
        model_data = PureQ_ProfileDatabase.get_model_profile(self.profile_key)
        if not model_data:
            self.report({'ERROR'}, f"Profile '{self.profile_key}' not found")
            return {'CANCELLED'}

        profile_data = model_data.get("profile", {})

        # Guardar en la carpeta del avatar
        try:
            system = context.scene.PureQ_avatar_system
            file_path = PureQ_AvatarProfileManager.save_avatar_profile(
                self.avatar_name,
                self.new_profile_name,
                profile_data,
                system
            )
            self.report({'INFO'}, f"Saved profile '{self.new_profile_name}' for avatar '{self.avatar_name}'")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save profile: {str(e)}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        # Usar el avatar seleccionado si existe
        obj = context.active_object
        if obj and obj.type == 'MESH':
            self.avatar_name = obj.name
        elif obj and obj.type == 'ARMATURE':
            self.avatar_name = obj.name
        else:
            self.avatar_name = context.scene.PureQ_custom_avatar_name

        # Usar el perfil seleccionado actualmente
        if hasattr(context.scene, 'PureQ_selected_model_profile'):
            self.profile_key = context.scene.PureQ_selected_model_profile
            self.new_profile_name = f"{self.profile_key}_for_{self.avatar_name}"

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "avatar_name", text="Avatar Name")
        col.prop(self, "new_profile_name", text="Profile Name")
        col.label(text=f"Will save profile to avatar-specific folder", icon='FILE_FOLDER')


class PureQ_OT_CreateJSONFromSelection(bpy.types.Operator):
    """Crea un archivo JSON de perfil basado en los grupos de vértices del objeto seleccionado"""
    bl_idname = "pureq.create_json_from_selection"
    bl_label = "Create JSON Profile from Selection"
    bl_description = "Create a new profile JSON using the active object's vertex groups"

    profile_name: StringProperty(name="Profile Name", default="New_Profile")
    min_weight: FloatProperty(name="Min Weight", default=0.001, min=0.0, precision=4)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a Mesh object")
            return {'CANCELLED'}

        system = context.scene.PureQ_avatar_system
        avatar_name = context.scene.PureQ_custom_avatar_name

        # Recopilar grupos de vértices
        vgroups = [vg.name for vg in obj.vertex_groups]
        if not vgroups:
            self.report({'WARNING'}, "Object has no vertex groups")

        # Crear estructura de datos del perfil
        profile_data = {
            "allowed_bones": vgroups,
            "min_weight": self.min_weight,
            "exclude_bones": [],
            "description": f"Auto-generated from {obj.name}"
        }

        try:
            PureQ_AvatarProfileManager.save_avatar_profile(
                avatar_name,
                self.profile_name,
                profile_data,
                system
            )
            self.report({'INFO'}, f"Created profile '{self.profile_name}' in {system}/{avatar_name}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create profile: {str(e)}")
            return {'CANCELLED'}

    def invoke(self, context, event):
        if context.active_object:
            self.profile_name = f"{context.active_object.name}_Profile"
        return context.window_manager.invoke_props_dialog(self)


class PureQ_OT_LoadAvatarProfiles(bpy.types.Operator):
    """Carga los perfiles de un avatar específico"""
    bl_idname = "pureq.load_avatar_profiles"
    bl_label = "Load Avatar Profiles"
    bl_description = "Load profiles from the selected avatar's folder"
    
    avatar_name: StringProperty(name="Avatar Name")
    
    def execute(self, context):
        if not self.avatar_name.strip():
            self.report({'ERROR'}, "Avatar name cannot be empty")
            return {'CANCELLED'}

        try:
            system = context.scene.PureQ_avatar_system
            profiles = PureQ_AvatarProfileManager.load_avatar_profiles(self.avatar_name, system)

            # Aquí podríamos hacer varias cosas con los perfiles cargados
            # Por ahora, simplemente mostramos cuántos encontramos
            self.report({'INFO'}, f"Loaded {len(profiles)} profiles for avatar '{self.avatar_name}'")

            # Guardar temporalmente en la escena para mostrarlos
            context.scene.PureQ_loaded_avatar_profiles.clear()
            for profile_name, profile_data in profiles.items():
                item = context.scene.PureQ_loaded_avatar_profiles.add()
                item.name = profile_name
                item.avatar_name = self.avatar_name
                item.profile_data = str(profile_data)  # Guardar como string para simplificar

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load profiles: {str(e)}")
            return {'CANCELLED'}


class PureQ_AvatarProfileItem(bpy.types.PropertyGroup):
    """Item para perfiles de avatar"""
    name: StringProperty(name="Profile Name")
    avatar_name: StringProperty(name="Avatar Name")
    profile_data: StringProperty(name="Profile Data (JSON string)")


class PUREQ_UL_AvatarProfiles(bpy.types.UIList):
    """UI List para mostrar perfiles de avatar"""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name, icon='FILE_BLEND')
            layout.label(text=item.avatar_name)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE_BLEND')


class PUREQ_PT_AvatarProfileOrganizer(bpy.types.Panel):
    """Panel para organizar perfiles por avatar"""
    bl_label = "Avatar Profile Organizer"
    bl_idname = "PUREQ_PT_avatar_profile_organizer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PureQ Weight Transfer'
    bl_parent_id = 'PUREQ_PT_model_profile_manager'
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Selección de Sistema
        layout.prop(scene, "PureQ_avatar_system", text="System")

        avatar_box = layout.box()

        # Selección de Nombre de Avatar
        row = avatar_box.row()
        row.prop(scene, "PureQ_custom_avatar_name", text="Avatar Name")

        # Botón para usar nombre del objeto seleccionado
        obj = context.active_object
        if obj:
            row.operator("pureq.create_avatar_folder", text="", icon='EYEDROPPER').avatar_name = obj.name

        # Crear carpeta para avatar
        folder_row = avatar_box.row()
        folder_row.operator("pureq.create_avatar_folder", icon='NEWFOLDER', text="Create Folder for Avatar")

        # Crear JSON desde selección
        if obj and obj.type == 'MESH':
            json_box = layout.box()
            json_box.label(text="Create Profile JSON", icon='FILE_TEXT')
            json_box.operator("pureq.create_json_from_selection", text="Create from Active Mesh", icon='ADD')

        # Separador
        layout.separator()

        # Guardar perfil en carpeta de avatar
        save_box = layout.box()
        save_box.label(text="Save Profile to Avatar", icon='SAVE_PREFS')

        if scene.PureQ_selected_model_profile and scene.PureQ_selected_model_profile != "NONE":
            save_row = save_box.row()
            save_row.operator("pureq.save_profile_to_avatar", icon='EXPORT', text=f"Save '{scene.PureQ_selected_model_profile}' to Avatar Folder")
        else:
            save_box.label(text="Select a profile to save", icon='ERROR')

        # Separador
        layout.separator()

        # Cargar perfiles de avatar
        load_box = layout.box()
        load_box.label(text="Load Avatar Profiles", icon='IMPORT')

        # Lista de avatares disponibles
        system = scene.PureQ_avatar_system
        all_avatars = PureQ_AvatarProfileManager.get_all_avatar_folders(system)
        if all_avatars:
            col = load_box.column(align=True)
            for avatar_name in all_avatars:
                row = col.row(align=True)
                row.label(text=avatar_name, icon='USER')
                row.operator("pureq.load_avatar_profiles", text="Load", icon='IMPORT').avatar_name = avatar_name
        else:
            load_box.label(text="No avatar folders found", icon='ERROR')

        # Mostrar perfiles cargados si hay
        if len(scene.PureQ_loaded_avatar_profiles) > 0:
            loaded_box = layout.box()
            loaded_box.label(text=f"Loaded Profiles ({len(scene.PureQ_loaded_avatar_profiles)})", icon='INFO')

            rows = min(6, max(2, len(scene.PureQ_loaded_avatar_profiles)))
            loaded_box.template_list("PUREQ_UL_AvatarProfiles", "", scene, "PureQ_loaded_avatar_profiles", scene, "PureQ_loaded_avatar_profiles_index", rows=rows)


def register():
    bpy.utils.register_class(PureQ_AvatarProfileItem)
    bpy.utils.register_class(PureQ_OT_CreateAvatarFolder)
    bpy.utils.register_class(PureQ_OT_SaveProfileToAvatar)
    bpy.utils.register_class(PureQ_OT_CreateJSONFromSelection)
    bpy.utils.register_class(PureQ_OT_LoadAvatarProfiles)
    bpy.utils.register_class(PUREQ_UL_AvatarProfiles)
    bpy.utils.register_class(PUREQ_PT_AvatarProfileOrganizer)

    # Registrar propiedades
    bpy.types.Scene.PureQ_loaded_avatar_profiles = CollectionProperty(type=PureQ_AvatarProfileItem)
    bpy.types.Scene.PureQ_loaded_avatar_profiles_index = IntProperty(name="Index for loaded avatar profiles", default=0)

    bpy.types.Scene.PureQ_avatar_system = EnumProperty(
        name="Avatar System",
        description="Select the avatar system/model type",
        items=[
            ('MIXAMO', "Mixamo", "Mixamo Avatar System"),
            ('PureQ', "PureQ", "PureQ Avatar System"),
            ('METAHUMAN', "MetaHuman", "Unreal MetaHuman"),
            ('CC', "Character Creator", "Reallusion Character Creator"),
            ('CUSTOM', "Custom", "Custom Avatar System"),
        ],
        default='CUSTOM'
    )
    bpy.types.Scene.PureQ_custom_avatar_name = StringProperty(
        name="Avatar Name",
        description="Name of the specific avatar",
        default="MyAvatar"
    )


def unregister():
    bpy.utils.unregister_class(PureQ_AvatarProfileItem)
    bpy.utils.unregister_class(PureQ_OT_CreateAvatarFolder)
    bpy.utils.unregister_class(PureQ_OT_SaveProfileToAvatar)
    bpy.utils.unregister_class(PureQ_OT_CreateJSONFromSelection)
    bpy.utils.unregister_class(PureQ_OT_LoadAvatarProfiles)
    bpy.utils.unregister_class(PUREQ_UL_AvatarProfiles)
    bpy.utils.unregister_class(PUREQ_PT_AvatarProfileOrganizer)

    # Eliminar propiedades
    if hasattr(bpy.types.Scene, 'PureQ_loaded_avatar_profiles'):
        delattr(bpy.types.Scene, 'PureQ_loaded_avatar_profiles')
    if hasattr(bpy.types.Scene, 'PureQ_loaded_avatar_profiles_index'):
        delattr(bpy.types.Scene, 'PureQ_loaded_avatar_profiles_index')
    if hasattr(bpy.types.Scene, 'PureQ_avatar_system'):
        delattr(bpy.types.Scene, 'PureQ_avatar_system')
    if hasattr(bpy.types.Scene, 'PureQ_custom_avatar_name'):
        delattr(bpy.types.Scene, 'PureQ_custom_avatar_name')

