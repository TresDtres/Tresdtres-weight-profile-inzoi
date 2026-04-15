"""
Módulo para la gestión de perfiles de modelos específicos
"""
import bpy
import json
import os
from bpy.props import StringProperty, EnumProperty, BoolProperty, IntProperty, FloatProperty, CollectionProperty

BASE_CATEGORIES = [
    "skirt", "shorts", "pants", "dress", "top", "jacket", "shirt", "coat", "hoodie",
    "sweater", "blazer", "vest", "bodysuit", "underwear", "swimwear", "activewear",
    "sleepwear", "accessory", "gloves", "socks", "stockings", "shoes", "boots", "cape",
    "custom"
]

BASE_LENGTHS = [
    "micro", "mini", "short", "mid", "medium", "knee", "midi", "long", "maxi", "floor",
    "cropped", "hip", "thigh", "ankle", "custom"
]

BASE_MODEL_TYPES = [
    "skirt", "shorts", "pants", "jeans", "leggings", "dress", "top", "shirt", "blouse",
    "jacket", "coat", "hoodie", "sweater", "blazer", "vest", "bodysuit", "swimsuit",
    "underwear", "cape", "gloves", "socks", "stockings", "shoes", "boots", "custom"
]

BASE_STYLES = [
    "casual", "formal", "sport", "streetwear", "punk", "gothic", "fantasy", "scifi",
    "military", "traditional", "vintage", "business", "party", "sleepwear", "swimwear",
    "uniform", "minimal", "oversized", "tight", "loose", "custom"
]


class PureQ_ProfileDatabase:
    """Clase para manejar la base de datos de perfiles de modelos"""
    
    @staticmethod
    def get_profiles_data_path():
        """Obtiene la ruta al archivo de datos de perfiles"""
        return os.path.join(
            os.path.dirname(__file__),
            "data",
            "model_profiles.json"
        )

    @staticmethod
    def get_user_profiles_dir():
        """Directorio para perfiles de usuario distribuido con el addon."""
        return os.path.join(os.path.dirname(__file__), "User_Profiles")

    @classmethod
    def get_user_model_profiles_path(cls):
        return os.path.join(cls.get_user_profiles_dir(), "model_profiles.json")

    @classmethod
    def ensure_user_profile_storage(cls):
        """Crea carpeta/archivo de perfiles de usuario si no existen."""
        os.makedirs(cls.get_user_profiles_dir(), exist_ok=True)
        user_path = cls.get_user_model_profiles_path()
        if not os.path.exists(user_path):
            data = {"version": "1.0", "models": {}}
            with open(user_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _read_models_file(path):
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("models", {})
        except Exception as e:
            print(f"Warning: Could not read model profiles from {path}: {e}")
            return {}
    
    @classmethod
    def load_model_profiles(cls):
        """Carga los perfiles de modelos desde el archivo JSON"""
        base_path = cls.get_profiles_data_path()
        user_path = cls.get_user_model_profiles_path()

        if not os.path.exists(base_path):
            # Crear archivo base si no existe
            cls.create_default_model_profiles(base_path)

        cls.ensure_user_profile_storage()
        base_models = cls._read_models_file(base_path)
        user_models = cls._read_models_file(user_path)

        # User profiles override base profiles with same key.
        merged = dict(base_models)
        merged.update(user_models)
        return merged

    @classmethod
    def load_base_model_profiles(cls):
        """Carga solo perfiles base distribuidos con el addon."""
        base_path = cls.get_profiles_data_path()
        if not os.path.exists(base_path):
            cls.create_default_model_profiles(base_path)
        return cls._read_models_file(base_path)

    @classmethod
    def load_user_model_profiles(cls):
        """Carga solo perfiles de usuario."""
        cls.ensure_user_profile_storage()
        return cls._read_models_file(cls.get_user_model_profiles_path())
    
    @classmethod
    def save_model_profiles(cls, models_data, target="base"):
        """Guarda perfiles (base por compatibilidad; user para perfiles personalizados)."""
        cls.ensure_user_profile_storage()
        if target == "base":
            path = cls.get_profiles_data_path()
        else:
            path = cls.get_user_model_profiles_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        data = {
            "version": "1.0",
            "models": models_data
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def save_user_model_profiles(cls, models_data):
        """Guarda perfiles en el almacenamiento de usuario."""
        cls.save_model_profiles(models_data, target="user")
    
    @classmethod
    def create_default_model_profiles(cls, path):
        """Crea un archivo de perfiles por defecto"""
        default_data = {
            "version": "1.0",
            "models": {
                "default_skirt": {
                    "name": "Default Skirt",
                    "category": "skirt",
                    "length": "medium",
                    "model_type": "skirt",
                    "style": "casual",
                    "description": "Default skirt profile",
                    "profile": {
                        "allowed_bones": [
                            "pelvis",
                            "thigh_l", "thigh_r",
                            "thigh_twist_01_l", "thigh_twist_01_r",
                            "calf_l", "calf_r"
                        ],
                        "forbidden_bones": [],
                        "min_weight": 0.001,
                        "max_influences": 4
                    }
                }
            }
        }
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def add_model_profile(cls, model_name, category, length, model_type, description, profile_data, style="custom"):
        """Añade un nuevo perfil de modelo a la base de datos"""
        model_key = f"{category}_{model_name}".replace(" ", "_").lower()

        model_data = {
            "name": model_name,
            "category": category,
            "length": length,
            "model_type": model_type,
            "style": style or "custom",
            "description": description,
            "profile": profile_data
        }
        cls.upsert_user_profile(model_key, model_data)
        return model_key

    @classmethod
    def upsert_user_profile(cls, model_key, profile_data):
        """Crea o actualiza un perfil solo en User_Profiles."""
        models = cls.load_user_model_profiles()
        models[model_key] = profile_data
        cls.save_user_model_profiles(models)

    @classmethod
    def delete_user_profile(cls, model_key):
        """
        Elimina un perfil solo de User_Profiles.
        Devuelve True si se eliminó, False si no existía en usuario.
        """
        models = cls.load_user_model_profiles()
        if model_key not in models:
            return False
        del models[model_key]
        cls.save_user_model_profiles(models)
        return True
    
    @classmethod
    def get_model_profile(cls, model_key):
        """Obtiene un perfil de modelo específico"""
        models = cls.load_model_profiles()
        return models.get(model_key)
    
    @classmethod
    def get_all_model_keys(cls):
        """Obtiene todas las claves de modelos"""
        models = cls.load_model_profiles()
        return list(models.keys())
    
    @classmethod
    def get_models_by_category(cls, category):
        """Obtiene modelos por categoría"""
        models = cls.load_model_profiles()
        return {k: v for k, v in models.items() if v.get("category", "").lower() == category.lower()}
    
    @classmethod
    def get_models_by_type(cls, model_type):
        """Obtiene modelos por tipo"""
        models = cls.load_model_profiles()
        return {k: v for k, v in models.items() if v.get("model_type", "").lower() == model_type.lower()}


def enum_model_profiles(self, context):
    """Función para enumerar perfiles de modelos para el EnumProperty"""
    try:
        items = [("NONE", "Select Model Profile", "Choose model profile manually")]
        items.extend(
            [(key, data.get("name", key), data.get("description", ""))
             for key, data in PureQ_ProfileDatabase.load_model_profiles().items()]
        )
        return items
    except Exception:
        return [("NONE", "No Models Found", "No model profiles available")]


def enum_categories(self, context):
    """Función para enumerar categorías de modelos"""
    models = PureQ_ProfileDatabase.load_model_profiles()
    dynamic = [model.get("category", "custom") for model in models.values() if model.get("category")]
    categories = list(dict.fromkeys(BASE_CATEGORIES + sorted(set(dynamic))))
    return [(cat, cat.title(), f"Category: {cat}") for cat in categories]


def enum_lengths(self, context):
    """Función para enumerar longitudes de modelos"""
    lengths = BASE_LENGTHS
    return [(length, length.title(), f"Length: {length}") for length in lengths]


def enum_model_types(self, context):
    """Función para enumerar tipos de modelos"""
    models = PureQ_ProfileDatabase.load_model_profiles()
    dynamic = [model.get("model_type", "custom") for model in models.values() if model.get("model_type")]
    types = list(dict.fromkeys(BASE_MODEL_TYPES + sorted(set(dynamic))))
    return [(type_, type_.title(), f"Model type: {type_}") for type_ in types]


def enum_styles(self, context):
    """Función para enumerar estilos de modelos"""
    models = PureQ_ProfileDatabase.load_model_profiles()
    dynamic = [model.get("style", "custom") for model in models.values() if model.get("style")]
    styles = list(dict.fromkeys(BASE_STYLES + sorted(set(dynamic))))
    return [(style, style.title(), f"Style: {style}") for style in styles]

