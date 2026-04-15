import json
import os

_PROFILES_CACHE = {}
_LOD_RULES_CACHE = {}
_VERSION = None


def _get_data_path():
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "bone_profiles.json"
    )

def _get_user_profiles_dir():
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "User_Profiles"
    )

def _get_user_bone_profiles_path():
    return os.path.join(_get_user_profiles_dir(), "bone_profiles.json")

def ensure_user_bone_profile_storage():
    """Create user profile folder/files shipped with addon installation."""
    os.makedirs(_get_user_profiles_dir(), exist_ok=True)
    path = _get_user_bone_profiles_path()
    if not os.path.exists(path):
        data = {
            "version": "1.0",
            "profiles": {},
            "lod_rules": {}
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def load_bone_profiles():
    global _PROFILES_CACHE, _LOD_RULES_CACHE, _VERSION

    path = _get_data_path()

    if not os.path.exists(path):
        raise FileNotFoundError(f"Bone profile file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    _VERSION = data.get("version", "unknown")

    profiles = data.get("profiles", {})
    validated = {}

    for name, profile in profiles.items():
        validated[name] = _validate_profile(name, profile)

    _PROFILES_CACHE = validated
    _LOD_RULES_CACHE = data.get("lod_rules", {})

    # Load custom profiles from model-specific files if they exist
    _load_custom_model_profiles()
    _load_user_profiles()


def _load_custom_model_profiles():
    """Load custom profiles from model-specific files"""
    import os
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

    # Look for model-specific profile files
    for file_name in os.listdir(data_dir):
        if file_name.startswith("model_") and file_name.endswith("_profiles.json"):
            file_path = os.path.join(data_dir, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    model_data = json.load(f)

                model_profiles = model_data.get("profiles", {})
                for name, profile in model_profiles.items():
                    _PROFILES_CACHE[name] = _validate_profile(name, profile)

            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"Could not load model-specific profile file {file_name}: {e}")


def _load_user_profiles():
    """Load user profiles from User_Profiles folder."""
    ensure_user_bone_profile_storage()
    user_path = _get_user_bone_profiles_path()

    try:
        with open(user_path, "r", encoding="utf-8") as f:
            user_data = json.load(f)
        for name, profile in user_data.get("profiles", {}).items():
            _PROFILES_CACHE[name] = _validate_profile(name, profile)
    except Exception as e:
        print(f"Could not load user bone profile file {user_path}: {e}")


def _validate_profile(name, profile):
    if "allowed_bones" not in profile:
        raise ValueError(f"Profile '{name}' has no allowed_bones")

    return {
        "allowed_bones": set(profile.get("allowed_bones", [])),
        "forbidden_bones": set(profile.get("forbidden_bones", [])),
        "min_weight": float(profile.get("min_weight", 0.0)),
        "max_influences": int(profile.get("max_influences", 4))
    }


def get_bone_profile(profile_name):
    if not _PROFILES_CACHE:
        load_bone_profiles()

    return _PROFILES_CACHE.get(profile_name)


def get_profiles_version():
    return _VERSION

def get_bone_profile_names():
    """Get list of available bone profile names"""
    if not _PROFILES_CACHE:
        load_bone_profiles()
    return list(_PROFILES_CACHE.keys())

def get_lod_rules():
    """Get LOD rules from the JSON file"""
    if not _LOD_RULES_CACHE:
        load_bone_profiles()
    return _LOD_RULES_CACHE
