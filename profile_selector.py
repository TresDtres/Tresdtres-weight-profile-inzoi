import bpy
import json
import os
from bpy.props import EnumProperty, StringProperty, FloatProperty, IntProperty, BoolProperty, CollectionProperty


class PureQ_ProfileSelector:
    """Clase para manejar la selección de perfiles de huesos"""
    
    _PROFILES_CACHE = {}
    
    @staticmethod
    def _get_data_path():
        return os.path.join(
            os.path.dirname(__file__),
            "data",
            "bone_profiles.json"
        )
    
    @classmethod
    def load_bone_profiles(cls):
        """Carga los perfiles de huesos desde el archivo JSON"""
        path = cls._get_data_path()
        
        if not os.path.exists(path):
            # Crear archivo de ejemplo si no existe
            cls._create_default_profiles(path)
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        profiles = data.get("profiles", {})
        validated = {}
        
        for name, profile in profiles.items():
            validated[name] = cls._validate_profile(name, profile)
        
        cls._PROFILES_CACHE = validated
        return validated
    
    @classmethod
    def _validate_profile(cls, name, profile):
        """Valida y normaliza un perfil de huesos"""
        if "allowed_bones" not in profile:
            raise ValueError(f"Profile '{name}' has no allowed_bones")
        
        return {
            "allowed_bones": set(profile.get("allowed_bones", [])),
            "forbidden_bones": set(profile.get("forbidden_bones", [])),
            "min_weight": float(profile.get("min_weight", 0.0)),
            "max_influences": int(profile.get("max_influences", 4))
        }
    
    @classmethod
    def get_bone_profile(cls, profile_name):
        """Obtiene un perfil específico por nombre"""
        if not cls._PROFILES_CACHE:
            cls.load_bone_profiles()
        
        return cls._PROFILES_CACHE.get(profile_name)
    
    @classmethod
    def get_bone_profile_names(cls):
        """Obtiene lista de nombres de perfiles disponibles"""
        if not cls._PROFILES_CACHE:
            cls.load_bone_profiles()
        return list(cls._PROFILES_CACHE.keys())
    
    @classmethod
    def _create_default_profiles(cls, path):
        """Crea un archivo de perfiles por defecto si no existe"""
        default_profiles = {
            "version": "1.0",
            "profiles": {
                "SHORT_SKIRT": {
                    "allowed_bones": [
                        "pelvis",
                        "thigh_l", "thigh_r",
                        "thigh_twist_01_l", "thigh_twist_01_r",
                        "thigh_twist_02_l", "thigh_twist_02_r"
                    ],
                    "min_weight": 0.001,
                    "max_influences": 4
                },
                "MEDIUM_SKIRT": {
                    "allowed_bones": [
                        "pelvis",
                        "thigh_l", "thigh_r",
                        "thigh_twist_01_l", "thigh_twist_01_r",
                        "calf_l", "calf_r"
                    ],
                    "min_weight": 0.001,
                    "max_influences": 4
                },
                "LONG_SKIRT": {
                    "allowed_bones": [
                        "pelvis",
                        "thigh_l", "thigh_r",
                        "thigh_twist_01_l", "thigh_twist_01_r",
                        "thigh_twist_02_l", "thigh_twist_02_r",
                        "calf_l", "calf_r"
                    ],
                    "forbidden_bones": [
                        "foot_l", "foot_r",
                        "ball_l", "ball_r",
                        "bigtoe_01_l", "bigtoe_01_r"
                    ],
                    "min_weight": 0.001,
                    "max_influences": 3
                },
                "TROUSERS": {
                    "allowed_bones": [
                        "pelvis",
                        "thigh_l", "thigh_r",
                        "thigh_twist_01_l", "thigh_twist_01_r",
                        "thigh_twist_02_l", "thigh_twist_02_r",
                        "calf_l", "calf_r",
                        "calf_twist_01_l", "calf_twist_01_r"
                    ],
                    "min_weight": 0.001,
                    "max_influences": 4
                },
                "SHIRT": {
                    "allowed_bones": [
                        "spine_01", "spine_02", "spine_03",
                        "clavicle_l", "clavicle_r",
                        "upperarm_l", "upperarm_r",
                        "lowerarm_l", "lowerarm_r"
                    ],
                    "forbidden_bones": [
                        "pelvis", "thigh_l", "thigh_r",
                        "calf_l", "calf_r", "foot_l", "foot_r"
                    ],
                    "min_weight": 0.001,
                    "max_influences": 4
                },
                "JACKET": {
                    "allowed_bones": [
                        "spine_01", "spine_02", "spine_03", "spine_04",
                        "clavicle_l", "clavicle_r",
                        "upperarm_l", "upperarm_r",
                        "lowerarm_l", "lowerarm_r"
                    ],
                    "forbidden_bones": [
                        "pelvis", "thigh_l", "thigh_r",
                        "calf_l", "calf_r", "foot_l", "foot_r"
                    ],
                    "min_weight": 0.001,
                    "max_influences": 4
                },
                "CUSTOM": {
                    "allowed_bones": [],
                    "min_weight": 0.01,
                    "max_influences": 8
                }
            },
            "lod_rules": {
                "LOD0": {
                    "max_influences": 4,
                    "weight_multiplier": 1.0,
                    "smooth": 0.5
                },
                "LOD1": {
                    "max_influences": 3,
                    "weight_multiplier": 1.25,
                    "smooth": 0.3
                },
                "LOD2": {
                    "max_influences": 2,
                    "weight_multiplier": 1.5,
                    "smooth": 0.0
                }
            }
        }
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_profiles, f, indent=2, ensure_ascii=False)


def enum_bone_profiles(self, context):
    """Función para enumerar perfiles de huesos para el EnumProperty"""
    try:
        profiles = PureQ_ProfileSelector.get_bone_profile_names()
        return [(p, p.replace("_", " ").title(), "") for p in profiles]
    except Exception:
        return [("NONE", "No Profiles Found", "")]


class PureQ_OT_LoadProfile(bpy.types.Operator):
    """Carga un perfil de huesos específico"""
    bl_idname = "pureq.load_profile"
    bl_label = "Load Bone Profile"
    bl_description = "Load a specific bone profile for weight transfer"
    bl_options = {'REGISTER', 'UNDO'}
    
    profile_name: StringProperty(
        name="Profile Name",
        description="Name of the profile to load"
    )
    
    def execute(self, context):
        if self.profile_name:
            profile = PureQ_ProfileSelector.get_bone_profile(self.profile_name)
            if profile:
                # Aquí iría la lógica para aplicar el perfil al objeto seleccionado
                # Por ahora solo mostramos información
                allowed_bones = profile.get("allowed_bones", set())
                self.report({'INFO'}, f"Loaded profile '{self.profile_name}' with {len(allowed_bones)} allowed bones")
                print(f"Profile '{self.profile_name}' - Allowed bones: {list(allowed_bones)}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"Profile '{self.profile_name}' not found")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, "No profile name specified")
            return {'CANCELLED'}


class PureQ_OT_CreateCustomProfile(bpy.types.Operator):
    """Crea un perfil personalizado"""
    bl_idname = "pureq.create_custom_profile"
    bl_label = "Create Custom Profile"
    bl_description = "Create a new custom bone profile"
    bl_options = {'REGISTER', 'UNDO'}
    
    profile_name: StringProperty(
        name="Profile Name",
        description="Name for the new profile"
    )
    
    def execute(self, context):
        if self.profile_name:
            # Aquí iría la lógica para crear un perfil personalizado
            self.report({'INFO'}, f"Created custom profile: {self.profile_name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Profile name is required")
            return {'CANCELLED'}


def register():
    bpy.utils.register_class(PureQ_OT_LoadProfile)
    bpy.utils.register_class(PureQ_OT_CreateCustomProfile)

    # Note: PureQtw_bone_profile property is registered in the main __init__.py file
    # to avoid duplicate registration conflicts


def unregister():
    bpy.utils.unregister_class(PureQ_OT_LoadProfile)
    bpy.utils.unregister_class(PureQ_OT_CreateCustomProfile)

    # Note: PureQtw_bone_profile property is managed in the main __init__.py file


