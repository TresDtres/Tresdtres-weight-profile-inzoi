"""
Módulo para validar la integridad y compatibilidad de los perfiles
"""
import bpy
from bpy.props import StringProperty, EnumProperty, BoolProperty, IntProperty, FloatProperty, CollectionProperty
from .model_profile_db import PureQ_ProfileDatabase


class PureQ_ProfileValidator:
    """Clase para validar perfiles de modelos"""
    
    @classmethod
    def validate_profile_integrity(cls, profile_data):
        """Valida la integridad estructural de un perfil"""
        errors = []
        warnings = []
        
        if not profile_data:
            errors.append("Profile data is empty")
            return errors, warnings
        
        # Validar que exista la estructura básica
        required_keys = ["allowed_bones"]
        for key in required_keys:
            if key not in profile_data:
                errors.append(f"Missing required key: {key}")
        
        # Validar tipos de datos
        if "allowed_bones" in profile_data and not isinstance(profile_data["allowed_bones"], (list, set)):
            errors.append("allowed_bones must be a list or set")
        
        if "forbidden_bones" in profile_data and not isinstance(profile_data["forbidden_bones"], (list, set)):
            errors.append("forbidden_bones must be a list or set")
        
        if "min_weight" in profile_data and not isinstance(profile_data["min_weight"], (int, float)):
            errors.append("min_weight must be a number")
        
        if "max_influences" in profile_data and not isinstance(profile_data["max_influences"], int):
            errors.append("max_influences must be an integer")
        
        # Validar rangos de valores
        if "min_weight" in profile_data:
            min_weight = profile_data["min_weight"]
            if min_weight < 0 or min_weight > 1:
                warnings.append(f"min_weight ({min_weight}) seems unusual, should be between 0 and 1")
        
        if "max_influences" in profile_data:
            max_inf = profile_data["max_influences"]
            if max_inf < 1 or max_inf > 8:
                warnings.append(f"max_influences ({max_inf}) seems unusual, typically 1-8")
        
        # Validar que no haya huecos en blanco en las listas
        if "allowed_bones" in profile_data:
            allowed_bones = profile_data["allowed_bones"]
            empty_bones = [bone for bone in allowed_bones if not bone or bone.strip() == ""]
            if empty_bones:
                errors.append(f"Found empty bone names in allowed_bones: {empty_bones}")
        
        if "forbidden_bones" in profile_data:
            forbidden_bones = profile_data["forbidden_bones"]
            empty_bones = [bone for bone in forbidden_bones if not bone or bone.strip() == ""]
            if empty_bones:
                errors.append(f"Found empty bone names in forbidden_bones: {empty_bones}")
        
        return errors, warnings
    
    @classmethod
    def validate_profile_compatibility(cls, profile_data, armature_obj):
        """Valida la compatibilidad de un perfil con un armature específico"""
        if not armature_obj or armature_obj.type != 'ARMATURE':
            return ["No armature object provided"], []
        
        errors = []
        warnings = []
        
        # Obtener huesos del armature
        armature_bones = {bone.name.lower() for bone in armature_obj.data.bones}
        
        # Validar huesos permitidos
        allowed_bones = profile_data.get("allowed_bones", [])
        missing_allowed = []
        for bone in allowed_bones:
            if bone.lower() not in armature_bones:
                missing_allowed.append(bone)
        
        if missing_allowed:
            errors.append(f"Allowed bones not found in armature: {missing_allowed}")
        
        # Validar huesos prohibidos
        forbidden_bones = profile_data.get("forbidden_bones", [])
        missing_forbidden = []
        for bone in forbidden_bones:
            if bone.lower() not in armature_bones:
                missing_forbidden.append(bone)
        
        if missing_forbidden:
            warnings.append(f"Forbidden bones not found in armature: {missing_forbidden}")
        
        # Verificar conflicto entre allowed y forbidden
        allowed_set = set(bone.lower() for bone in allowed_bones)
        forbidden_set = set(bone.lower() for bone in forbidden_bones)
        conflicts = allowed_set.intersection(forbidden_set)
        
        if conflicts:
            errors.append(f"Conflicting bones (both allowed and forbidden): {list(conflicts)}")
        
        return errors, warnings
    
    @classmethod
    def validate_all_profiles(cls):
        """Valida todos los perfiles en la base de datos"""
        all_models = PureQ_ProfileDatabase.load_model_profiles()
        results = {}
        
        for profile_key, model_data in all_models.items():
            profile = model_data.get("profile", {})
            integrity_errors, integrity_warnings = cls.validate_profile_integrity(profile)
            
            # No podemos validar compatibilidad sin un armature específico
            results[profile_key] = {
                "integrity": {
                    "errors": integrity_errors,
                    "warnings": integrity_warnings
                },
                "compatibility": {
                    "errors": [],
                    "warnings": []
                }
            }
        
        return results


class PureQ_ValidationResult(bpy.types.PropertyGroup):
    """Resultado de validación de perfil"""
    profile_key: StringProperty(name="Profile Key")
    has_errors: BoolProperty(name="Has Errors", default=False)
    has_warnings: BoolProperty(name="Has Warnings", default=False)
    error_count: IntProperty(name="Error Count", default=0)
    warning_count: IntProperty(name="Warning Count", default=0)
    error_details: StringProperty(name="Error Details")
    warning_details: StringProperty(name="Warning Details")


class PureQ_OT_ValidateProfile(bpy.types.Operator):
    """Valida un perfil específico"""
    bl_idname = "pureq.validate_profile"
    bl_label = "Validate Profile"
    bl_description = "Validate the selected profile for integrity and compatibility"
    
    profile_key: StringProperty(name="Profile Key")
    check_compatibility: BoolProperty(name="Check Compatibility", default=True)
    
    def execute(self, context):
        if not self.profile_key:
            self.report({'ERROR'}, "No profile selected for validation")
            return {'CANCELLED'}
        
        # Obtener el perfil
        model_data = PureQ_ProfileDatabase.get_model_profile(self.profile_key)
        if not model_data:
            self.report({'ERROR'}, f"Profile '{self.profile_key}' not found")
            return {'CANCELLED'}
        
        profile = model_data.get("profile", {})
        
        # Validar integridad
        integrity_errors, integrity_warnings = PureQ_ProfileValidator.validate_profile_integrity(profile)
        
        # Validar compatibilidad si se solicitó
        compatibility_errors = []
        compatibility_warnings = []
        
        if self.check_compatibility:
            obj = context.active_object
            armature_obj = None
            
            # Buscar armature asociado
            if obj and obj.type == 'MESH':
                for modifier in obj.modifiers:
                    if modifier.type == 'ARMATURE' and modifier.object:
                        armature_obj = modifier.object
                        break
            elif obj and obj.type == 'ARMATURE':
                armature_obj = obj
            
            if armature_obj:
                compatibility_errors, compatibility_warnings = PureQ_ProfileValidator.validate_profile_compatibility(profile, armature_obj)
            else:
                self.report({'WARNING'}, "No armature found for compatibility check")
        
        # Mostrar resultados
        total_errors = len(integrity_errors) + len(compatibility_errors)
        total_warnings = len(integrity_warnings) + len(compatibility_warnings)
        
        if total_errors > 0:
            self.report({'ERROR'}, f"Profile '{self.profile_key}' has {total_errors} errors and {total_warnings} warnings")
        elif total_warnings > 0:
            self.report({'WARNING'}, f"Profile '{self.profile_key}' has {total_warnings} warnings")
        else:
            self.report({'INFO'}, f"Profile '{self.profile_key}' is valid")
        
        # Imprimir detalles en la consola
        print(f"\n=== VALIDATION RESULTS FOR '{self.profile_key}' ===")
        print(f"Integrity Errors ({len(integrity_errors)}):")
        for error in integrity_errors:
            print(f"  - ERROR: {error}")
        
        print(f"Integrity Warnings ({len(integrity_warnings)}):")
        for warning in integrity_warnings:
            print(f"  - WARNING: {warning}")
        
        print(f"Compatibility Errors ({len(compatibility_errors)}):")
        for error in compatibility_errors:
            print(f"  - ERROR: {error}")
        
        print(f"Compatibility Warnings ({len(compatibility_warnings)}):")
        for warning in compatibility_warnings:
            print(f"  - WARNING: {warning}")
        print("=" * 40)
        
        return {'FINISHED'}


class PureQ_OT_ValidateAllProfiles(bpy.types.Operator):
    """Valida todos los perfiles"""
    bl_idname = "pureq.validate_all_profiles"
    bl_label = "Validate All Profiles"
    bl_description = "Validate all profiles in the database"
    
    check_compatibility: BoolProperty(name="Check Compatibility", default=False)
    
    def execute(self, context):
        results = PureQ_ProfileValidator.validate_all_profiles()
        
        total_errors = 0
        total_warnings = 0
        invalid_profiles = []
        
        for profile_key, result in results.items():
            error_count = len(result["integrity"]["errors"])
            warning_count = len(result["integrity"]["warnings"]) + len(result["compatibility"]["warnings"])
            
            total_errors += error_count
            total_warnings += warning_count
            
            if error_count > 0:
                invalid_profiles.append(profile_key)
        
        if total_errors > 0:
            self.report({'ERROR'}, f"Found {total_errors} errors in {len(invalid_profiles)} profiles")
        elif total_warnings > 0:
            self.report({'WARNING'}, f"Found {total_warnings} warnings in profiles")
        else:
            self.report({'INFO'}, "All profiles are valid!")
        
        # Guardar resultados en la escena
        context.scene.PureQ_validation_results.clear()
        for profile_key, result in results.items():
            item = context.scene.PureQ_validation_results.add()
            item.profile_key = profile_key
            item.has_errors = len(result["integrity"]["errors"]) > 0
            item.has_warnings = len(result["integrity"]["warnings"]) > 0 or len(result["compatibility"]["warnings"]) > 0
            item.error_count = len(result["integrity"]["errors"])
            item.warning_count = len(result["integrity"]["warnings"]) + len(result["compatibility"]["warnings"])
            
            # Guardar detalles
            errors = result["integrity"]["errors"]
            warnings = result["integrity"]["warnings"]
            item.error_details = "; ".join(errors) if errors else ""
            item.warning_details = "; ".join(warnings) if warnings else ""
        
        print(f"\n=== VALIDATION SUMMARY ===")
        print(f"Total profiles checked: {len(results)}")
        print(f"Profiles with errors: {len([k for k, r in results.items() if r['integrity']['errors']])}")
        print(f"Total errors: {total_errors}")
        print(f"Total warnings: {total_warnings}")
        print("=" * 25)
        
        return {'FINISHED'}


class PUREQ_UL_ValidationResults(bpy.types.UIList):
    """UI List para mostrar resultados de validación"""
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # Icono indicando estado
            if item.has_errors:
                layout.label(text="", icon='ERROR')
            elif item.has_warnings:
                layout.label(text="", icon='WARN')
            else:
                layout.label(text="", icon='CHECKMARK')
            
            # Nombre del perfil
            layout.label(text=item.profile_key)
            
            # Contador de errores/warnings
            error_text = f"E:{item.error_count}" if item.error_count > 0 else ""
            warning_text = f"W:{item.warning_count}" if item.warning_count > 0 else ""
            layout.label(text=f"{error_text} {warning_text}")
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            if item.has_errors:
                layout.label(text="", icon='ERROR')
            elif item.has_warnings:
                layout.label(text="", icon='WARN')
            else:
                layout.label(text="", icon='CHECKMARK')


class PUREQ_PT_ProfileValidator(bpy.types.Panel):
    """Panel para validación de perfiles"""
    bl_label = "Profile Validator"
    bl_idname = "PUREQ_PT_profile_validator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PureQ Weight Transfer'
    bl_parent_id = 'PUREQ_PT_model_profile_manager'
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Validar perfil seleccionado
        validate_box = layout.box()
        validate_box.label(text="Validate Profile", icon='CHECKMARK')
        
        row = validate_box.row()
        row.prop(scene, "PureQ_validate_compatibility", text="Check Compatibility")
        
        if scene.PureQ_selected_model_profile and scene.PureQ_selected_model_profile != "NONE":
            row = validate_box.row()
            row.operator("pureq.validate_profile", text=f"Validate '{scene.PureQ_selected_model_profile}'").profile_key = scene.PureQ_selected_model_profile
        else:
            row = validate_box.row()
            row.operator("pureq.validate_profile", text="Validate Selected Profile").profile_key = scene.PureQ_selected_model_profile
        
        # Validar todos los perfiles
        validate_all_box = layout.box()
        validate_all_box.label(text="Validate All Profiles", icon='CHECKMARK')
        
        row = validate_all_box.row()
        row.prop(scene, "PureQ_validate_all_compatibility", text="Check Compatibility")
        
        row = validate_all_box.row()
        row.operator("pureq.validate_all_profiles", text="Validate All Profiles")
        
        # Resultados de validación
        if len(scene.PureQ_validation_results) > 0:
            results_box = layout.box()
            results_box.label(text="Validation Results", icon='INFO')
            
            # Estadísticas
            error_count = sum(1 for r in scene.PureQ_validation_results if r.has_errors)
            warning_count = sum(1 for r in scene.PureQ_validation_results if r.has_warnings)
            
            stats_row = results_box.row()
            stats_row.label(text=f"Errors: {error_count} | Warnings: {warning_count}")
            
            # Lista de resultados
            rows = min(8, max(3, len(scene.PureQ_validation_results)))
            results_box.template_list("PUREQ_UL_ValidationResults", "", scene, "PureQ_validation_results", scene, "PureQ_validation_results_index", rows=rows)
            
            # Detalles si hay selección
            if len(scene.PureQ_validation_results) > 0 and scene.PureQ_validation_results_index >= 0:
                idx = scene.PureQ_validation_results_index
                if idx < len(scene.PureQ_validation_results):
                    result = scene.PureQ_validation_results[idx]
                    
                    details_box = results_box.box()
                    details_box.label(text=f"Details for: {result.profile_key}", icon='TEXT')
                    
                    if result.error_details:
                        details_box.label(text="Errors:", icon='ERROR')
                        details_box.label(text=result.error_details, icon='DOT')
                    
                    if result.warning_details:
                        details_box.label(text="Warnings:", icon='WARN')
                        details_box.label(text=result.warning_details, icon='DOT')


def register():
    bpy.utils.register_class(PureQ_ValidationResult)
    bpy.utils.register_class(PureQ_OT_ValidateProfile)
    bpy.utils.register_class(PureQ_OT_ValidateAllProfiles)
    bpy.utils.register_class(PUREQ_UL_ValidationResults)
    bpy.utils.register_class(PUREQ_PT_ProfileValidator)
    
    # Registrar propiedades
    bpy.types.Scene.PureQ_validation_results = CollectionProperty(type=PureQ_ValidationResult)
    bpy.types.Scene.PureQ_validation_results_index = IntProperty(name="Index for validation results", default=0)
    bpy.types.Scene.PureQ_validate_compatibility = BoolProperty(
        name="Validate Compatibility",
        description="Check if profile is compatible with current armature",
        default=True
    )
    bpy.types.Scene.PureQ_validate_all_compatibility = BoolProperty(
        name="Validate All Compatibility",
        description="Check compatibility for all profiles (requires armature)",
        default=False
    )


def unregister():
    bpy.utils.unregister_class(PureQ_ValidationResult)
    bpy.utils.unregister_class(PureQ_OT_ValidateProfile)
    bpy.utils.unregister_class(PureQ_OT_ValidateAllProfiles)
    bpy.utils.unregister_class(PUREQ_UL_ValidationResults)
    bpy.utils.unregister_class(PUREQ_PT_ProfileValidator)
    
    # Eliminar propiedades
    if hasattr(bpy.types.Scene, 'PureQ_validation_results'):
        delattr(bpy.types.Scene, 'PureQ_validation_results')
    if hasattr(bpy.types.Scene, 'PureQ_validation_results_index'):
        delattr(bpy.types.Scene, 'PureQ_validation_results_index')
    if hasattr(bpy.types.Scene, 'PureQ_validate_compatibility'):
        delattr(bpy.types.Scene, 'PureQ_validate_compatibility')
    if hasattr(bpy.types.Scene, 'PureQ_validate_all_compatibility'):
        delattr(bpy.types.Scene, 'PureQ_validate_all_compatibility')

