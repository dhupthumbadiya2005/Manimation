"""Static checks that run in milliseconds and cost nothing, before any render.

- syntax, required class shape, import allow-list, dangerous builtins
- unknown names (hallucinated Manim classes) with "did you mean" suggestions
- free auto-fixes for well-known ManimGL -> Manim CE renames

This is a guard rail, not a sandbox: renders also run in a separate process
with a timeout and a scratch working directory.
"""

from __future__ import annotations

import ast
import builtins
import difflib
import re
from dataclasses import dataclass, field
from functools import lru_cache

from app.config import BACKEND_DIR

ALLOWED_IMPORTS = {
    "manim", "manim_kit", "numpy", "math", "random", "itertools",
    "functools", "collections", "typing", "dataclasses", "fractions",
}
BANNED_CALLS = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint",
                "globals", "locals", "vars", "exit", "quit"}
BANNED_ATTRS = {"__subclasses__", "__globals__", "__builtins__", "__code__", "__loader__"}
# Text renders characters literally; x^2, a_1, \frac would show up as typed.
TEXT_ONLY_CALLS = {"Text", "MarkupText", "title_card", "caption"}
LATEX_IN_TEXT = re.compile(r"\w\^[\w{]|\w_[{\d]|\\[a-zA-Z]+")
# ManimGL / legacy names with a 1:1 Manim CE replacement.
AUTO_RENAMES = {
    "ShowCreation": "Create",
    "TextMobject": "Text",
    "TexMobject": "MathTex",
    "ShowCreationThenDestruction": "ShowPassingFlash",
}


@dataclass
class Issue:
    line: int | None
    message: str

    def __str__(self) -> str:
        return f"line {self.line}: {self.message}" if self.line else self.message


@dataclass
class ValidationResult:
    code: str
    issues: list[Issue] = field(default_factory=list)
    autofixes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues

    def report(self) -> str:
        return "Static validation failed:\n" + "\n".join(f"- {i}" for i in self.issues)


@lru_cache
def known_names() -> frozenset[str]:
    import manim  # heavy import; done once per process

    kit_init = ast.parse((BACKEND_DIR / "manim_kit" / "__init__.py").read_text())
    kit_names: set[str] = set()
    for node in kit_init.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            kit_names = set(ast.literal_eval(node.value))
    return frozenset(set(dir(manim)) | kit_names | set(dir(builtins)))


def _bound_names(tree: ast.AST) -> set[str]:
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
    return bound


def _apply_renames(code: str, tree: ast.AST) -> tuple[str, list[str]]:
    edits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in AUTO_RENAMES:
            edits.append((node.lineno, node.col_offset, node.end_col_offset, node.id))
    if not edits:
        return code, []
    lines = code.splitlines(keepends=True)
    fixes = []
    for lineno, start, end, old in sorted(edits, reverse=True):
        line = lines[lineno - 1]
        lines[lineno - 1] = line[:start] + AUTO_RENAMES[old] + line[end:]
        fixes.append(f"line {lineno}: {old} -> {AUTO_RENAMES[old]}")
    return "".join(lines), sorted(fixes)


def validate(code: str, class_name: str) -> ValidationResult:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return ValidationResult(code, [Issue(e.lineno, f"SyntaxError: {e.msg}")])

    code, autofixes = _apply_renames(code, tree)
    if autofixes:
        tree = ast.parse(code)
    result = ValidationResult(code, autofixes=autofixes)
    issues = result.issues

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [(node.module or "").split(".")[0]]
        else:
            mods = []
        for mod in mods:
            if mod not in ALLOWED_IMPORTS:
                issues.append(Issue(node.lineno, f"import of '{mod}' is not allowed (allowed: {sorted(ALLOWED_IMPORTS)})"))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
            issues.append(Issue(node.lineno, f"call to '{node.func.id}' is not allowed"))
        if isinstance(node, ast.Attribute) and node.attr in BANNED_ATTRS:
            issues.append(Issue(node.lineno, f"attribute '{node.attr}' is not allowed"))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in TEXT_ONLY_CALLS and node.args
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
                and LATEX_IN_TEXT.search(node.args[0].value)):
            issues.append(Issue(node.lineno, f"{node.func.id}({node.args[0].value!r}) contains math markup that Text "
                                             f"shows literally; use Tex(r\"... $math$ ...\") or MathTex instead"))
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CONFIG" for t in node.targets):
            issues.append(Issue(node.lineno, "CONFIG dicts are ManimGL-only; pass parameters directly in Manim CE"))

    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    target = next((c for c in classes if c.name == class_name), None)
    if target is None:
        issues.append(Issue(None, f"expected a class named {class_name}; found {[c.name for c in classes]}"))
    else:
        bases = {b.id for b in target.bases if isinstance(b, ast.Name)}
        if "ThemedVoiceoverScene" not in bases:
            issues.append(Issue(target.lineno, f"{class_name} must subclass ThemedVoiceoverScene"))
        if not any(isinstance(n, ast.FunctionDef) and n.name == "construct" for n in target.body):
            issues.append(Issue(target.lineno, f"{class_name} has no construct(self) method"))
    scene_classes = [c for c in classes if any(isinstance(b, ast.Name) and b.id.endswith("Scene") for b in c.bases)]
    if len(scene_classes) > 1:
        issues.append(Issue(None, "only one Scene subclass is allowed per file"))

    known = known_names() | _bound_names(tree)
    reported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in known:
            if node.id in reported:
                continue
            reported.add(node.id)
            guess = difflib.get_close_matches(node.id, known, n=1)
            hint = f" (did you mean {guess[0]}?)" if guess else ""
            issues.append(Issue(node.lineno, f"name '{node.id}' is not defined in Manim CE / manim_kit{hint}"))
    return result
