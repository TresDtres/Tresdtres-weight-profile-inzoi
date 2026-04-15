import bpy


def get_ui_language():
    """Return short language code used by UI text selection."""
    locale = ""
    try:
        locale = (bpy.app.translations.locale or "").strip()
    except Exception:
        locale = ""
    if not locale:
        try:
            locale = (bpy.context.preferences.view.language or "").strip()
        except Exception:
            locale = ""
    l = locale.lower()
    if l.startswith("es"):
        return "es"
    if l.startswith("ko"):
        return "ko"
    return "en"


def pick(messages, default_en=""):
    if isinstance(messages, str):
        return messages
    lang = get_ui_language()
    return messages.get(lang) or messages.get("en") or default_en


def tr(key, table, default_en=""):
    return pick(table.get(key, {"en": default_en or key}), default_en=default_en or key)
