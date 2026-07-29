"""Schema and validation for the simplified scene plan."""

DEFAULT_TARGET_DURATION = 180.0


def validate(plan: dict) -> tuple[bool, str]:
    if not isinstance(plan, dict):
        return False, "Plan must be a JSON object"

    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or len(scenes) == 0:
        return False, "plan.scenes must be a non-empty list"

    for i, scene in enumerate(scenes):
        sid = scene.get("scene_id")
        if not isinstance(sid, int) or sid != i + 1:
            return False, f"scene[{i}].scene_id must be {i + 1}, got {sid!r}"
        for field in ("title", "description"):
            val = scene.get(field, "")
            if not isinstance(val, str) or not val.strip():
                return False, f"scene {sid}: '{field}' must be a non-empty string"

    return True, ""


def scene_duration_hint(scene: dict) -> float:
    return float(scene.get("duration_hint", 0))
