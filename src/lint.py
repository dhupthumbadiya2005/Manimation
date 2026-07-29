"""Static pre-render checks for generated Manim code."""
import ast
import re
from dataclasses import dataclass


ALLOWED_IMPORTS = {"manim", "numpy", "np", "math"}


@dataclass
class LintResult:
    passed: bool
    message: str = ""


def check(code: str) -> LintResult:
    """Run static checks; return LintResult with passed=False and a reason on failure."""

    # 1. Parse to AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return LintResult(passed=False, message=f"SyntaxError: {e}")

    # 2. Check imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in ALLOWED_IMPORTS:
                    return LintResult(passed=False, message=f"Disallowed import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            top = node.module.split(".")[0]
            if top not in ALLOWED_IMPORTS:
                return LintResult(passed=False, message=f"Disallowed import: from {node.module}")

    # 3. Check for while loops
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            return LintResult(passed=False, message="while loops are not allowed")

    # 4. Check for time.sleep
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "sleep":
                if isinstance(func.value, ast.Name) and func.value.id == "time":
                    return LintResult(passed=False, message="time.sleep() is not allowed")

    # 5. Exactly one Scene subclass (Scene, ThreeDScene, or MovingCameraScene)
    _SCENE_BASES = {"Scene", "ThreeDScene", "MovingCameraScene", "ZoomedScene"}
    scene_classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                base_name = ""
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                if base_name in _SCENE_BASES:
                    scene_classes.append(node.name)

    if len(scene_classes) == 0:
        return LintResult(passed=False, message="No Scene subclass found")
    if len(scene_classes) > 1:
        return LintResult(passed=False, message=f"Multiple Scene subclasses found: {scene_classes}")

    # 6. Check for suspiciously large or negative literal coordinates in move_to/shift
    # Regex heuristic: look for move_to or shift with a bare large number
    coord_pattern = re.compile(r'\.(move_to|shift)\s*\(\s*[-]?\s*(\d+\.?\d*)', re.MULTILINE)
    for match in coord_pattern.finditer(code):
        val = float(match.group(2))
        sign = -1 if '-' in code[match.start():match.start() + 20].split('(')[1][:5] else 1
        val *= sign
        if abs(val) > 15:
            return LintResult(
                passed=False,
                message=f"Suspicious large coordinate {val} in {match.group(1)}() — use grid constants"
            )

    return LintResult(passed=True)
