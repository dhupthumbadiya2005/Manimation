"""Schema definition and validator for Phase 2 planner output."""

GRID_CELLS = [
    "top-left", "top-center", "top-right",
    "mid-left", "mid-center", "mid-right",
    "bot-left", "bot-center", "bot-right",
    "full",
]

MAX_TOTAL_DURATION_SECONDS = 300
DEFAULT_TARGET_DURATION = 240.0

_REMOVING_ACTIONS = {"fadeout", "uncreate"}
_WAIT_ACTIONS = {"wait", "pause"}


def _action_type(action: str) -> str:
    a = action.lower().replace(" ", "_").replace("-", "_")
    if any(w in a for w in _REMOVING_ACTIONS):
        return "remove"
    if any(w in a for w in _WAIT_ACTIONS):
        return "wait"
    return "add"


def scene_beat_total(scene: dict) -> float:
    """Sum of all beat durations in a scene (the actual animation runtime)."""
    return sum(float(b.get("duration", 0)) for b in scene.get("beats", []))


def validate(plan: dict) -> tuple[bool, str]:
    """
    Validate a planner-generated plan dict.
    Returns (True, "") on success or (False, human-readable error) on failure.

    Scene duration is determined entirely by beat sums — there is no per-scene
    budget that beats must match. The only duration constraint is that the total
    of all beats across all scenes must not exceed MAX_TOTAL_DURATION_SECONDS.
    """
    if not isinstance(plan, dict):
        return False, "Plan must be a JSON object"

    # --- top-level ---
    target_dur = plan.get("target_duration_seconds", DEFAULT_TARGET_DURATION)
    if not isinstance(target_dur, (int, float)) or target_dur <= 0:
        return False, "target_duration_seconds must be a positive number"
    if target_dur > MAX_TOTAL_DURATION_SECONDS:
        return False, (
            f"target_duration_seconds {target_dur}s exceeds hard cap "
            f"of {MAX_TOTAL_DURATION_SECONDS}s"
        )

    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or len(scenes) == 0:
        return False, "scenes must be a non-empty list"

    # --- scene_ids must be sequential starting at 1 ---
    for i, scene in enumerate(scenes):
        sid = scene.get("scene_id")
        if not isinstance(sid, int):
            return False, f"Scene at index {i}: scene_id must be an integer"
        if sid != i + 1:
            return False, (
                f"scene_id {sid} at index {i} is out of order "
                f"(expected {i + 1}); scene_ids must start at 1 and be sequential"
            )

    # --- per-scene structural validation ---
    for scene in scenes:
        sid = scene["scene_id"]
        p = f"Scene {sid}"

        goal = scene.get("goal", "")
        if not isinstance(goal, str) or not goal.strip():
            return False, f"{p}: goal must be a non-empty string"

        max_sim = scene.get("max_simultaneous_mobjects")
        if not isinstance(max_sim, int) or max_sim < 1:
            return False, f"{p}: max_simultaneous_mobjects must be a positive integer"

        mobjects = scene.get("mobjects")
        if not isinstance(mobjects, list) or len(mobjects) == 0:
            return False, f"{p}: mobjects must be a non-empty list"

        mob_ids: set[str] = set()
        for mob in mobjects:
            mid = mob.get("id")
            if not isinstance(mid, str) or not mid.strip():
                return False, f"{p}: each mobject must have a non-empty string id"
            if mid in mob_ids:
                return False, f"{p}: duplicate mobject id '{mid}'"
            mob_ids.add(mid)
            cell = mob.get("cell")
            if cell not in GRID_CELLS:
                return False, (
                    f"{p}: mobject '{mid}' has invalid cell '{cell}'; "
                    f"valid cells: {GRID_CELLS}"
                )
            for field in ("type", "content"):
                if not isinstance(mob.get(field), str) or not mob[field].strip():
                    return False, f"{p}: mobject '{mid}' must have a non-empty '{field}'"

        beats = scene.get("beats")
        if not isinstance(beats, list) or len(beats) == 0:
            return False, f"{p}: beats must be a non-empty list"

        on_screen: set[str] = set()
        for bi, beat in enumerate(beats):
            bp = f"{p}, beat {bi + 1}"
            action = beat.get("action", "")
            target = beat.get("target", "")
            duration = beat.get("duration")

            if not isinstance(duration, (int, float)) or duration <= 0:
                return False, f"{bp}: duration must be a positive number"

            atype = _action_type(action)

            if atype != "wait" and target not in mob_ids:
                return False, (
                    f"{bp}: target '{target}' does not match any mobject id "
                    f"(available: {sorted(mob_ids)})"
                )

            if atype == "remove":
                on_screen.discard(target)
            elif atype == "add":
                on_screen.add(target)

            if len(on_screen) > max_sim:
                return False, (
                    f"{bp}: {len(on_screen)} mobjects on screen exceeds "
                    f"max_simultaneous_mobjects={max_sim} "
                    f"(on screen: {sorted(on_screen)})"
                )

    # --- total video duration must not exceed hard cap ---
    total_beats = sum(scene_beat_total(s) for s in scenes)
    if total_beats > MAX_TOTAL_DURATION_SECONDS:
        return False, (
            f"Total animation time ({total_beats:.1f}s) exceeds hard cap "
            f"of {MAX_TOTAL_DURATION_SECONDS}s — remove scenes or shorten beats"
        )

    return True, ""
