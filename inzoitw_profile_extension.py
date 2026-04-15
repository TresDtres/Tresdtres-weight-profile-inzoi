"""
Extensión para el addon funcional que agrega selección de perfiles de huesos
"""
import bpy
from bpy.props import EnumProperty, PointerProperty, BoolProperty
from .profile_selector import PureQ_ProfileSelector, enum_bone_profiles, PureQ_OT_LoadProfile, PureQ_OT_CreateCustomProfile


class PureQ_ProfileProperties(bpy.types.PropertyGroup):
    """Propiedades para la selección de perfiles de huesos"""
    
    bone_profile: EnumProperty(
        name="Bone Profile",
        description="Bone influence profile loaded from JSON",
        items=enum_bone_profiles
    )
    
    # Otras propiedades que podrían ser útiles
    use_profile_filtering: BoolProperty(
        name="Use Profile Filtering",
        description="Apply bone profile filtering to weight transfer",
        default=True
    )
    
    auto_apply_profile: BoolProperty(
        name="Auto Apply Profile",
        description="Automatically apply profile when selecting clothing",
        default=True
    )


class PureQ_OT_ApplyProfileToSelection(bpy.types.Operator):
    """Aplica el perfil seleccionado al objeto activo"""
    bl_idname = "pureq.apply_profile_to_selection"
    bl_label = "Apply Profile to Selection"
    bl_description = "Apply the selected bone profile to the active object"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "No mesh object selected")
            return {'CANCELLED'}
        
        scene = context.scene
        profile_name = scene.PureQ_profile_props.bone_profile
        
        if profile_name and profile_name != "NONE":
            # Sincronizar con la propiedad principal del addon para que el transferidor use este perfil
            scene.PureQ_bone_profile = profile_name
            
            profile = PureQ_ProfileSelector.get_bone_profile(profile_name)
            if profile:
                # Guardar información del perfil en el objeto
                obj["PureQ_bone_profile"] = profile_name
                obj["PureQ_allowed_bones"] = list(profile.get("allowed_bones", set()))
                
                self.report({'INFO'}, f"Profile '{profile_name}' applied to {obj.name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"Profile '{profile_name}' not found")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, "No profile selected")
            return {'CANCELLED'}


class PUREQ_PT_ProfilePanel(bpy.types.Panel):
    """Panel para la selección de perfiles de huesos"""
    bl_label = "Bone Profile Selector"
    bl_idname = "PUREQ_PT_profile_selector"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PureQ Weight Transfer'
    
    @classmethod
    def poll(cls, context):
        # Only show if in TRANSFER mode
        return getattr(context.scene, "PureQ_addon_mode", "TRANSFER") == 'TRANSFER'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.PureQ_profile_props
        
        # Selección de perfil
        box = layout.box()
        box.label(text="Bone Profile", icon='GROUP_BONE')
        row = box.row()
        row.prop(props, "bone_profile", text="")
        
        # Botón para aplicar perfil
        row = box.row()
        row.operator("pureq.apply_profile_to_selection", icon='FILE_TICK')
        
        # Opciones adicionales
        col = box.column()
        col.prop(props, "use_profile_filtering")
        col.prop(props, "auto_apply_profile")
        
        # Información del perfil seleccionado
        if props.bone_profile and props.bone_profile != "NONE":
            profile = PureQ_ProfileSelector.get_bone_profile(props.bone_profile)
            if profile:
                info_box = box.box()
                info_box.label(text="Profile Info", icon='INFO')
                info_box.label(text=f"Allowed bones: {len(profile.get('allowed_bones', set()))}")
                info_box.label(text=f"Max influences: {profile.get('max_influences', 4)}")
                info_box.label(text=f"Min weight: {profile.get('min_weight', 0.01):.3f}")


def register():
    bpy.utils.register_class(PureQ_ProfileProperties)
    bpy.utils.register_class(PureQ_OT_ApplyProfileToSelection)
    bpy.utils.register_class(PUREQ_PT_ProfilePanel)
    
    # Registrar la propiedad en la escena
    bpy.types.Scene.PureQ_profile_props = PointerProperty(type=PureQ_ProfileProperties)


def unregister():
    bpy.utils.unregister_class(PureQ_ProfileProperties)
    bpy.utils.unregister_class(PureQ_OT_ApplyProfileToSelection)
    bpy.utils.unregister_class(PUREQ_PT_ProfilePanel)
    
    # Eliminar la propiedad de la escena
    if hasattr(bpy.types.Scene, 'PureQ_profile_props'):
        delattr(bpy.types.Scene, 'PureQ_profile_props')


if __name__ == "__main__":
    register()

