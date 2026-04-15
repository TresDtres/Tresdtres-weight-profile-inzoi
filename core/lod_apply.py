import bpy

def apply_lod_rules(obj, base_profile, lod_rule):
    """
    obj: mesh LOD
    base_profile: bone profile dict
    lod_rule: lod config dict
    """

    max_inf = lod_rule.get("max_influences", base_profile["max_influences"])
    multiplier = lod_rule.get("weight_multiplier", 1.0)
    smooth_factor = lod_rule.get("smooth", 0.0)

    for v in obj.data.vertices:
        weights = {}

        for g in v.groups:
            vg = obj.vertex_groups[g.group]
            w = g.weight * multiplier
            weights[vg.name] = w

        # Limit influences
        weights = dict(
            sorted(weights.items(), key=lambda x: x[1], reverse=True)[:max_inf]
        )

        # Apply smoothing if factor > 0
        if smooth_factor > 0:
            # Simple smoothing: blend with neighboring vertices
            neighbor_weights = {}
            neighbor_count = 0

            # Find connected vertices (simplified approach)
            for edge in obj.data.edges:
                if v.index in [edge.vertices[0], edge.vertices[1]]:
                    other_v_idx = edge.vertices[1] if edge.vertices[0] == v.index else edge.vertices[0]
                    other_v = obj.data.vertices[other_v_idx]

                    # Get weights from neighboring vertex
                    for g in other_v.groups:
                        vg = obj.vertex_groups[g.group]
                        if vg.name not in neighbor_weights:
                            neighbor_weights[vg.name] = 0.0
                        neighbor_weights[vg.name] += g.weight
                    neighbor_count += 1

            # Blend current weights with neighbor average
            if neighbor_count > 0:
                for bone in neighbor_weights:
                    neighbor_weights[bone] /= neighbor_count

                for bone in weights:
                    if bone in neighbor_weights:
                        weights[bone] = weights[bone] * (1.0 - smooth_factor) + neighbor_weights[bone] * smooth_factor

        # Normalize
        total = sum(weights.values())
        if total > 0:
            for bone, w in weights.items():
                obj.vertex_groups[bone].add([v.index], w / total, 'REPLACE')

def find_lods(base_obj):
    """Detecta LODs automáticamente basados en convención de nombres"""
    name = base_obj.name
    return {
        "LOD0": bpy.data.objects.get(f"{name}_LOD0"),
        "LOD1": bpy.data.objects.get(f"{name}_LOD1"),
        "LOD2": bpy.data.objects.get(f"{name}_LOD2"),
    }