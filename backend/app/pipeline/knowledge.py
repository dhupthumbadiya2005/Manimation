"""Static knowledge fed to the agents: toolkit reference, cookbook snippets
(selected per scene by technique tags), and the known-error hint table."""

from __future__ import annotations

import difflib
import inspect
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.config import KNOWLEDGE_DIR, PROMPTS_DIR


@dataclass(frozen=True)
class Snippet:
    name: str
    techniques: frozenset[str]
    summary: str
    code: str


def _header_field(doc: str, field: str) -> str:
    m = re.search(rf"^{field}:\s*(.+)$", doc, re.MULTILINE)
    return m.group(1).strip() if m else ""


@lru_cache
def cookbook() -> tuple[Snippet, ...]:
    snippets = []
    for path in sorted((KNOWLEDGE_DIR / "cookbook").glob("*.py")):
        code = path.read_text()
        doc = code.split('"""')[1] if code.startswith('"""') else ""
        techniques = frozenset(t.strip() for t in _header_field(doc, "techniques").split(",") if t.strip())
        snippets.append(Snippet(path.stem, techniques, _header_field(doc, "summary"), code))
    return tuple(snippets)


@lru_cache
def all_techniques() -> tuple[str, ...]:
    return tuple(sorted(set().union(*(s.techniques for s in cookbook()))))


def select_snippets(techniques: list[str], limit: int = 2) -> list[Snippet]:
    wanted = set(techniques)
    scored = [(len(s.techniques & wanted), s) for s in cookbook()]
    scored = [x for x in scored if x[0] > 0]
    scored.sort(key=lambda x: (-x[0], x[1].name))
    return [s for _, s in scored[:limit]]


@lru_cache
def toolkit_reference() -> str:
    return (KNOWLEDGE_DIR / "toolkit_reference.md").read_text()


@lru_cache
def prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()


@lru_cache
def _error_table() -> tuple[tuple[re.Pattern, str], ...]:
    rows = yaml.safe_load((KNOWLEDGE_DIR / "errors.yaml").read_text())
    return tuple((re.compile(r["pattern"], re.IGNORECASE), r["hint"]) for r in rows)


def hints_for(error_text: str) -> list[str]:
    return [hint for pattern, hint in _error_table() if pattern.search(error_text)]


NO_ATTR = re.compile(r"'(\w+)' object has no attribute '(\w+)'")
BAD_KWARG = re.compile(r"(\w+)\.(\w+)\(\) got an unexpected keyword argument '(\w+)'")
MAX_PARAMS = 25


def _manim_class(name: str):
    import manim
    obj = getattr(manim, name, None)
    return obj if isinstance(obj, type) else None


def _params(func) -> list[str]:
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return []
    return [p for p in sig.parameters if p not in ("self", "args", "kwargs")][:MAX_PARAMS]


def api_hints(error_text: str) -> list[str]:
    """Ground the Fixer in the installed Manim API: real signatures / real
    attribute names for the classes named in the error. Free (introspection)."""
    hints = []
    for cls_name, attr in set(NO_ATTR.findall(error_text)):
        cls = _manim_class(cls_name)
        if cls is None:
            continue
        public = [a for a in dir(cls) if not a.startswith("_")]
        close = difflib.get_close_matches(attr, public, n=5, cutoff=0.5)
        hints.append(f"{cls_name} has no attribute '{attr}'. Closest real names: {close or 'none'}.")
    for cls_name, method, kwarg in set(BAD_KWARG.findall(error_text)):
        cls = _manim_class(cls_name)
        func = getattr(cls, method, None) if cls else None
        if func is None:
            continue
        params = _params(func)
        hints.append(f"{cls_name}.{method} has no '{kwarg}' parameter. Its parameters are: {params}.")
    return hints


