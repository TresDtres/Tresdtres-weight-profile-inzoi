# core/lod_rules.py

from .bone_profiles import load_bone_profiles

def get_lod_rules():
    load_bone_profiles()
    from .bone_profiles import _PROFILES_CACHE
    # Return the lod_rules from the main data structure
    if not _PROFILES_CACHE:
        load_bone_profiles()
    # Get the original data structure and extract lod_rules
    path = _get_data_path()  # This needs to be imported from bone_profiles
    import json
    import os
    
    def _get_data_path():
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "bone_profiles.json"
        )
    
    if not os.path.exists(path):
        return {}
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return data.get("lod_rules", {})

def get_lod_rules_direct():
    """Direct function to load LOD rules"""
    import json
    import os
    
    def _get_data_path():
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "bone_profiles.json"
        )
    
    path = _get_data_path()
    
    if not os.path.exists(path):
        return {}
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return data.get("lod_rules", {})