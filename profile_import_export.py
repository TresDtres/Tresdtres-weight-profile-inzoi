"""
Módulo para importar/exportar perfiles de modelos
"""
import bpy
import json
import os
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper
from .model_profile_db import PureQ_ProfileDatabase


class PureQ_OT_ExportProfile(bpy.types.Operator, ExportHelper):
    """Exporta un perfil de modelo a un archivo JSON"""
    bl_idname = "pureq.export_profile"
    bl_label = "Export Profile"
    bl_description = "Export the selected model profile to a JSON file"
    
    # Propiedades para ExportHelper
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    
    # Propiedad para seleccionar qué perfil exportar
    profile_to_export: bpy.props.EnumProperty(
        name="Profile to Export",
        description="Select which profile to export",
        items=lambda self, context: [
            (key, data.get("name", key), data.get("description", "")) 
            for key, data in PureQ_ProfileDatabase.load_model_profiles().items()
        ] if PureQ_ProfileDatabase.load_model_profiles() else [("NONE", "No Profiles", "No profiles available")]
    )
    
    def execute(self, context):
        if not self.profile_to_export or self.profile_to_export == "NONE":
            self.report({'ERROR'}, "No profile selected for export")
            return {'CANCELLED'}
        
        # Obtener el perfil seleccionado
        models = PureQ_ProfileDatabase.load_model_profiles()
        profile_data = models.get(self.profile_to_export)
        
        if not profile_data:
            self.report({'ERROR'}, f"Profile '{self.profile_to_export}' not found")
            return {'CANCELLED'}
        
        # Preparar datos para exportar
        export_data = {
            "version": "1.0",
            "export_type": "model_profile",
            "profile_key": self.profile_to_export,
            "profile_data": profile_data
        }
        
        # Escribir archivo
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.report({'INFO'}, f"Exported profile '{self.profile_to_export}' to {self.filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export profile: {str(e)}")
            return {'CANCELLED'}


class PureQ_OT_ImportProfile(bpy.types.Operator, ImportHelper):
    """Importa un perfil de modelo desde un archivo JSON"""
    bl_idname = "pureq.import_profile"
    bl_label = "Import Profile"
    bl_description = "Import a model profile from a JSON file"
    
    # Propiedades para ImportHelper
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    
    # Opciones de importación
    overwrite_existing: bpy.props.BoolProperty(
        name="Overwrite Existing",
        description="Overwrite existing profile if it has the same key",
        default=False
    )
    
    new_profile_key: bpy.props.StringProperty(
        name="New Profile Key",
        description="Use this key instead of the one in the file (to avoid conflicts)",
        default=""
    )
    
    def execute(self, context):
        # Leer archivo
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read file: {str(e)}")
            return {'CANCELLED'}
        
        # Verificar formato del archivo
        if not isinstance(import_data, dict):
            self.report({'ERROR'}, "Invalid file format: not a JSON object")
            return {'CANCELLED'}
        
        if import_data.get("export_type") != "model_profile":
            self.report({'ERROR'}, "Invalid file format: not a model profile export")
            return {'CANCELLED'}
        
        profile_key = import_data.get("profile_key")
        profile_data = import_data.get("profile_data")
        
        if not profile_key or not profile_data:
            self.report({'ERROR'}, "Invalid file format: missing profile key or data")
            return {'CANCELLED'}
        
        # Determinar la clave final para el perfil
        final_key = self.new_profile_key if self.new_profile_key else profile_key
        
        if not final_key:
            self.report({'ERROR'}, "No valid profile key provided")
            return {'CANCELLED'}
        
        # Verificar si ya existe y si no se permite sobrescribir
        merged_models = PureQ_ProfileDatabase.load_model_profiles()
        if final_key in merged_models and not self.overwrite_existing:
            self.report({'ERROR'}, f"Profile '{final_key}' already exists. Enable 'Overwrite Existing' to replace it.")
            return {'CANCELLED'}

        # Guardar siempre en User_Profiles (override sobre base si misma clave)
        try:
            PureQ_ProfileDatabase.upsert_user_profile(final_key, profile_data)
            self.report({'INFO'}, f"Imported profile '{final_key}' from {self.filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save imported profile: {str(e)}")
            return {'CANCELLED'}


class PureQ_OT_ImportMultipleProfiles(bpy.types.Operator, ImportHelper):
    """Importa múltiples perfiles desde un archivo ZIP o JSON"""
    bl_idname = "pureq.import_multiple_profiles"
    bl_label = "Import Multiple Profiles"
    bl_description = "Import multiple model profiles from a JSON file"
    
    # Propiedades para ImportHelper
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})
    
    # Opciones de importación
    overwrite_existing: bpy.props.BoolProperty(
        name="Overwrite Existing",
        description="Overwrite existing profiles if they have the same keys",
        default=False
    )
    
    def execute(self, context):
        # Leer archivo
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read file: {str(e)}")
            return {'CANCELLED'}
        
        # Verificar formato - puede ser un solo perfil o múltiples perfiles
        if not isinstance(import_data, dict):
            self.report({'ERROR'}, "Invalid file format: not a JSON object")
            return {'CANCELLED'}
        
        imported_count = 0
        error_count = 0
        
        # Si es un solo perfil exportado
        if import_data.get("export_type") == "model_profile":
            profile_key = import_data.get("profile_key")
            profile_data = import_data.get("profile_data")
            
            if profile_key and profile_data:
                merged_models = PureQ_ProfileDatabase.load_model_profiles()

                if profile_key in merged_models and not self.overwrite_existing:
                    error_count += 1
                else:
                    PureQ_ProfileDatabase.upsert_user_profile(profile_key, profile_data)
                    imported_count += 1
            else:
                error_count += 1
        
        # Si es un archivo con múltiples perfiles (como el archivo completo de perfiles)
        elif "models" in import_data:
            merged_models = PureQ_ProfileDatabase.load_model_profiles()
            imported_profiles = import_data.get("models", {})
            
            for profile_key, profile_data in imported_profiles.items():
                if profile_key in merged_models and not self.overwrite_existing:
                    error_count += 1
                else:
                    PureQ_ProfileDatabase.upsert_user_profile(profile_key, profile_data)
                    imported_count += 1
        
        # Guardar cambios si se importó algo
        if imported_count > 0:
            self.report({'INFO'}, f"Imported {imported_count} profiles, {error_count} errors")
            return {'FINISHED'}
        else:
            if error_count > 0:
                self.report({'WARNING'}, f"No profiles imported, {error_count} errors occurred")
            else:
                self.report({'WARNING'}, "No valid profiles found in file")
            return {'CANCELLED'}


class PUREQ_PT_ProfileImportExport(bpy.types.Panel):
    """Panel para importar/exportar perfiles"""
    bl_label = "Profile Import/Export"
    bl_idname = "PUREQ_PT_profile_import_export"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PureQ Weight Transfer'
    bl_parent_id = 'PUREQ_PT_model_profile_manager'
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Exportar perfil
        export_box = layout.box()
        export_box.label(text="Export Profile", icon='EXPORT')
        
        row = export_box.row()
        row.operator("pureq.export_profile", icon='EXPORT', text="Export Selected Profile")
        
        # Importar perfil
        import_box = layout.box()
        import_box.label(text="Import Profile", icon='IMPORT')
        
        import_row = import_box.row()
        import_row.operator("pureq.import_profile", icon='IMPORT', text="Import Single Profile")
        
        # Importar múltiples perfiles
        multi_import_row = import_box.row()
        multi_import_row.operator("pureq.import_multiple_profiles", icon='IMPORT', text="Import Multiple Profiles")


def register():
    bpy.utils.register_class(PureQ_OT_ExportProfile)
    bpy.utils.register_class(PureQ_OT_ImportProfile)
    bpy.utils.register_class(PureQ_OT_ImportMultipleProfiles)
    bpy.utils.register_class(PUREQ_PT_ProfileImportExport)


def unregister():
    bpy.utils.unregister_class(PureQ_OT_ExportProfile)
    bpy.utils.unregister_class(PureQ_OT_ImportProfile)
    bpy.utils.unregister_class(PureQ_OT_ImportMultipleProfiles)
    bpy.utils.unregister_class(PUREQ_PT_ProfileImportExport)

