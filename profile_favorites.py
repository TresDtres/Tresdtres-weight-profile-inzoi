"""
Módulo para el sistema de favoritos de perfiles
"""
import bpy
import json
import os
from bpy.props import StringProperty, BoolProperty, CollectionProperty, IntProperty
from .model_profile_db import PureQ_ProfileDatabase


class PureQ_FavoriteProfile(bpy.types.PropertyGroup):
    """Item para la lista de perfiles favoritos"""
    profile_key: StringProperty(name="Profile Key")
    profile_name: StringProperty(name="Profile Name")
    is_favorite: BoolProperty(name="Is Favorite", default=True)
    category: StringProperty(name="Category")
    model_type: StringProperty(name="Model Type")
    length: StringProperty(name="Length")
    description: StringProperty(name="Description")


class PureQ_OT_AddToFavorites(bpy.types.Operator):
    """Añade el perfil seleccionado a favoritos"""
    bl_idname = "pureq.add_to_favorites"
    bl_label = "Add to Favorites"
    bl_description = "Add the selected profile to favorites"
    
    profile_key: StringProperty(name="Profile Key")
    
    def execute(self, context):
        scene = context.scene
        
        if not self.profile_key or self.profile_key == "NONE":
            self.report({'ERROR'}, "No profile selected")
            return {'CANCELLED'}
        
        # Cargar datos del perfil
        model_data = PureQ_ProfileDatabase.get_model_profile(self.profile_key)
        if not model_data:
            self.report({'ERROR'}, f"Profile '{self.profile_key}' not found")
            return {'CANCELLED'}
        
        # Verificar si ya está en favoritos
        for item in scene.PureQ_favorite_profiles:
            if item.profile_key == self.profile_key:
                self.report({'WARNING'}, f"Profile '{self.profile_key}' is already in favorites")
                return {'CANCELLED'}
        
        # Añadir a favoritos
        item = scene.PureQ_favorite_profiles.add()
        item.profile_key = self.profile_key
        item.profile_name = model_data.get("name", self.profile_key)
        item.category = model_data.get("category", "unknown")
        item.model_type = model_data.get("model_type", "unknown")
        item.length = model_data.get("length", "unknown")
        item.description = model_data.get("description", "")
        item.is_favorite = True
        
        self.report({'INFO'}, f"Added '{item.profile_name}' to favorites")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # Si no se especificó una clave, usar la seleccionada actualmente
        if not self.profile_key:
            self.profile_key = context.scene.PureQ_selected_model_profile
        return {'FINISHED'}


class PureQ_OT_RemoveFromFavorites(bpy.types.Operator):
    """Elimina el perfil seleccionado de favoritos"""
    bl_idname = "pureq.remove_from_favorites"
    bl_label = "Remove from Favorites"
    bl_description = "Remove the selected profile from favorites"
    
    profile_key: StringProperty(name="Profile Key")
    
    def execute(self, context):
        scene = context.scene
        
        # Buscar y eliminar de favoritos
        for i, item in enumerate(scene.PureQ_favorite_profiles):
            if item.profile_key == self.profile_key:
                scene.PureQ_favorite_profiles.remove(i)
                self.report({'INFO'}, f"Removed '{item.profile_name}' from favorites")
                return {'FINISHED'}
        
        self.report({'ERROR'}, f"Profile '{self.profile_key}' not found in favorites")
        return {'CANCELLED'}


class PureQ_OT_ToggleFavorite(bpy.types.Operator):
    """Conmuta el estado de favorito de un perfil"""
    bl_idname = "pureq.toggle_favorite"
    bl_label = "Toggle Favorite"
    bl_description = "Toggle the favorite status of the selected profile"
    
    profile_key: StringProperty(name="Profile Key")
    is_adding: BoolProperty(name="Is Adding", default=True)
    
    def execute(self, context):
        if self.is_adding:
            # Añadir a favoritos
            bpy.ops.pureq.add_to_favorites(profile_key=self.profile_key)
        else:
            # Eliminar de favoritos
            bpy.ops.pureq.remove_from_favorites(profile_key=self.profile_key)
        
        return {'FINISHED'}


class PureQ_OT_LoadFavoriteProfile(bpy.types.Operator):
    """Carga un perfil favorito"""
    bl_idname = "pureq.load_favorite_profile"
    bl_label = "Load Favorite Profile"
    bl_description = "Load the selected favorite profile"
    
    profile_key: StringProperty(name="Profile Key")
    
    def execute(self, context):
        if not self.profile_key:
            self.report({'ERROR'}, "No profile key specified")
            return {'CANCELLED'}
        
        # Cargar el perfil como el perfil seleccionado actual
        context.scene.PureQ_selected_model_profile = self.profile_key
        
        # Aquí también podríamos aplicar el perfil si se desea
        model_data = PureQ_ProfileDatabase.get_model_profile(self.profile_key)
        if model_data:
            self.report({'INFO'}, f"Loaded favorite profile: {model_data.get('name', self.profile_key)}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Favorite profile '{self.profile_key}' not found in database")
            return {'CANCELLED'}


class PUREQ_UL_FavoriteProfiles(bpy.types.UIList):
    """UI List para mostrar los perfiles favoritos"""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Mostrar nombre del perfil y categoría
            layout.label(text=item.profile_name, icon='HEART')
            layout.label(text=f"{item.category}/{item.model_type}")
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='HEART')


class PUREQ_PT_FavoritesPanel(bpy.types.Panel):
    """Panel para la gestión de perfiles favoritos"""
    bl_label = "Profile Favorites"
    bl_idname = "PUREQ_PT_favorites_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PureQ Weight Transfer'
    bl_parent_id = 'PUREQ_PT_model_profile_manager'
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Información de favoritos
        favorite_count = len(scene.PureQ_favorite_profiles)
        layout.label(text=f"Favorites: {favorite_count}", icon='HEART')
        
        # Botón para añadir el perfil actual a favoritos
        if scene.PureQ_selected_model_profile and scene.PureQ_selected_model_profile != "NONE":
            model_data = PureQ_ProfileDatabase.get_model_profile(scene.PureQ_selected_model_profile)
            if model_data:
                add_row = layout.row()
                add_row.operator("pureq.add_to_favorites", text=f"Add '{model_data.get('name', scene.PureQ_selected_model_profile)}' to Favorites", icon='ADD')
        
        # Lista de favoritos
        if favorite_count > 0:
            favorites_box = layout.box()
            favorites_box.label(text="Favorite Profiles", icon='HEART')
            
            # Lista de favoritos
            rows = min(8, max(3, favorite_count))
            favorites_box.template_list("PUREQ_UL_FavoriteProfiles", "", scene, "PureQ_favorite_profiles", scene, "PureQ_favorite_profiles_index", rows=rows)
            
            # Acciones para el favorito seleccionado
            if favorite_count > 0 and scene.PureQ_favorite_profiles_index >= 0:
                idx = scene.PureQ_favorite_profiles_index
                if idx < len(scene.PureQ_favorite_profiles):
                    fav_item = scene.PureQ_favorite_profiles[idx]
                    
                    # Información del perfil favorito
                    info_box = favorites_box.box()
                    info_box.label(text=fav_item.profile_name, icon='FILE_BLEND')
                    col = info_box.column(align=True)
                    col.label(text=f"Key: {fav_item.profile_key}")
                    col.label(text=f"Category: {fav_item.category}")
                    col.label(text=f"Type: {fav_item.model_type}")
                    col.label(text=f"Length: {fav_item.length}")
                    
                    # Botones de acción
                    action_row = info_box.row(align=True)
                    action_row.operator("pureq.load_favorite_profile", text="Load Profile").profile_key = fav_item.profile_key
                    action_row.operator("pureq.remove_from_favorites", text="Remove").profile_key = fav_item.profile_key
        else:
            # Mensaje cuando no hay favoritos
            no_fav_box = layout.box()
            no_fav_box.label(text="No favorite profiles yet", icon='INFO')
            no_fav_box.label(text="Select a profile and click 'Add to Favorites'")


def register():
    bpy.utils.register_class(PureQ_FavoriteProfile)
    bpy.utils.register_class(PureQ_OT_AddToFavorites)
    bpy.utils.register_class(PureQ_OT_RemoveFromFavorites)
    bpy.utils.register_class(PureQ_OT_ToggleFavorite)
    bpy.utils.register_class(PureQ_OT_LoadFavoriteProfile)
    bpy.utils.register_class(PUREQ_UL_FavoriteProfiles)
    bpy.utils.register_class(PUREQ_PT_FavoritesPanel)
    
    # Registrar propiedades
    bpy.types.Scene.PureQ_favorite_profiles = CollectionProperty(type=PureQ_FavoriteProfile)
    bpy.types.Scene.PureQ_favorite_profiles_index = IntProperty(name="Index for favorite profiles", default=0)


def unregister():
    bpy.utils.unregister_class(PureQ_FavoriteProfile)
    bpy.utils.unregister_class(PureQ_OT_AddToFavorites)
    bpy.utils.unregister_class(PureQ_OT_RemoveFromFavorites)
    bpy.utils.unregister_class(PureQ_OT_ToggleFavorite)
    bpy.utils.unregister_class(PureQ_OT_LoadFavoriteProfile)
    bpy.utils.unregister_class(PUREQ_UL_FavoriteProfiles)
    bpy.utils.unregister_class(PUREQ_PT_FavoritesPanel)
    
    # Eliminar propiedades
    if hasattr(bpy.types.Scene, 'PureQ_favorite_profiles'):
        delattr(bpy.types.Scene, 'PureQ_favorite_profiles')
    if hasattr(bpy.types.Scene, 'PureQ_favorite_profiles_index'):
        delattr(bpy.types.Scene, 'PureQ_favorite_profiles_index')

