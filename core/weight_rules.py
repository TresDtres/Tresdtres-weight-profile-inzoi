def filter_weights_by_profile(weights: dict, profile: dict) -> dict:
    """
    weights: { bone_name: weight }
    """
    if not profile:
        return weights

    allowed = profile.get("allowed_bones")
    forbidden = profile.get("forbidden_bones", set())
    min_weight = profile.get("min_weight", 0.0)

    filtered = {}

    for bone, weight in weights.items():
        # Si allowed está vacío (set vacío), permitir todos los huesos
        if allowed is not None and len(allowed) > 0 and bone not in allowed:
            continue
        if bone in forbidden:
            continue
        if weight < min_weight:
            continue

        filtered[bone] = weight

    return filtered


def normalize_weights(weights: dict, max_influences: int = None) -> dict:
    if not weights:
        return {}

    # Limitar influencias
    if max_influences:
        weights = dict(
            sorted(weights.items(), key=lambda x: x[1], reverse=True)[:max_influences]
        )

    total = sum(weights.values())
    if total == 0:
        return {}

    return {k: v / total for k, v in weights.items()}