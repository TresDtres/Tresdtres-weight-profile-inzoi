def cleanup_vertex_groups(obj, profile):
    if not profile:
        return

    allowed = profile.get("allowed_bones", set())
    forbidden = profile.get("forbidden_bones", set())
    min_weight = profile.get("min_weight", 0.01)

    # Si allowed está vacío (set vacío), no eliminar ningún grupo
    if len(allowed) == 0:
        return

    # Identificar qué grupos de vértices tienen influencia significativa
    groups_to_remove = []
    for vg in list(obj.vertex_groups):
        # Si está prohibido, eliminarlo inmediatamente
        if vg.name in forbidden:
            groups_to_remove.append(vg)
        # Si no está permitido, eliminarlo independientemente de la influencia
        # (esto asegura que los huesos no permitidos no se mantengan)
        elif vg.name not in allowed:
            groups_to_remove.append(vg)

    # Eliminar los grupos identificados
    for vg in groups_to_remove:
        obj.vertex_groups.remove(vg)