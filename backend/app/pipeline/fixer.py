"""Fixer agent: repairs one scene file with small edits, Claude-Code style.

Instead of regenerating the whole file on every failure (expensive, and it
tends to break parts that worked), the model gets the numbered file plus the
error, and works through two tools:

- ``str_replace_based_edit_tool`` (Anthropic's text editor): view / str_replace /
  insert on this one file only; ``create`` (full rewrite) is refused.
- ``render_scene``: validate + preview-render, returns OK or the new problems.

The loop stops the moment a render comes back clean (no extra LLM call), or
after ``max_turns`` calls.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.llm.client import LLM

from . import knowledge

EDITOR_TOOL_NAME = "str_replace_based_edit_tool"
EDITOR_TOOL = {"type": "text_editor_20250728", "name": EDITOR_TOOL_NAME, "max_characters": 16000}
RENDER_TOOL = {
    "name": "render_scene",
    "description": "Validate and render the scene file at preview quality. Returns 'OK' or the "
                   "errors / layout problems found. Call it after making your edits.",
    "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
}
SNIPPET_CONTEXT = 4


@dataclass
class Check:
    """Result of validate + render, as the fixer sees it."""
    clean: bool        # rendered with no errors and no layout problems
    rendered: bool     # produced a video (maybe with layout problems)
    feedback: str


@dataclass
class FixOutcome:
    clean: bool
    rendered: bool
    turns: int
    edits: int
    feedback: str
    summary: str = ""


def numbered(text: str, start: int = 1) -> str:
    return "\n".join(f"{i:4d}\t{line}" for i, line in enumerate(text.splitlines(), start=start))


class SceneEditor:
    """Executes text-editor tool calls against exactly one file."""

    def __init__(self, path: Path):
        self.path = path
        self.edits = 0

    def _check_path(self, raw: str | None) -> str | None:
        if not raw:
            return "Error: missing 'path'."
        if Path(raw).name != self.path.name or ".." in Path(raw).parts:
            return f"Error: only {self.path.name} can be accessed."
        return None

    def _snippet(self, text: str, first: int, last: int) -> str:
        lines = text.splitlines()
        lo = max(1, first - SNIPPET_CONTEXT)
        hi = min(len(lines), last + SNIPPET_CONTEXT)
        return numbered("\n".join(lines[lo - 1:hi]), start=lo)

    def handle(self, inp: dict) -> tuple[str, bool]:
        """Returns (tool_result content, is_error)."""
        command = inp.get("command")
        err = self._check_path(inp.get("path"))
        if err:
            return err, True
        text = self.path.read_text()

        if command == "view":
            rng = inp.get("view_range")
            lines = text.splitlines()
            if rng:
                start, end = int(rng[0]), int(rng[1])
                end = len(lines) if end == -1 else end
                return numbered("\n".join(lines[start - 1:end]), start=start), False
            return numbered(text), False

        if command == "str_replace":
            old, new = inp.get("old_str"), inp.get("new_str", "")
            if not old:
                return "Error: 'old_str' is required.", True
            count = text.count(old)
            if count == 0:
                return ("Error: old_str was not found. It must match the file exactly, including "
                        "indentation. Use view to check the current text."), True
            if count > 1:
                return f"Error: old_str matches {count} places; add surrounding lines to make it unique.", True
            first_line = text[: text.index(old)].count("\n") + 1
            text = text.replace(old, new, 1)
            self.path.write_text(text)
            self.edits += 1
            last_line = first_line + new.count("\n")
            return "Edited. Region now:\n" + self._snippet(text, first_line, last_line), False

        if command == "insert":
            line_no = inp.get("insert_line")
            new = inp.get("insert_text", inp.get("new_str"))
            lines = text.splitlines(keepends=True)
            if new is None or line_no is None or not (0 <= int(line_no) <= len(lines)):
                return f"Error: insert needs insert_line in [0, {len(lines)}] and insert_text.", True
            line_no = int(line_no)
            if not new.endswith("\n"):
                new += "\n"
            if line_no > 0 and not lines[line_no - 1].endswith("\n"):
                lines[line_no - 1] += "\n"
            lines.insert(line_no, new)
            text = "".join(lines)
            self.path.write_text(text)
            self.edits += 1
            return "Inserted. Region now:\n" + self._snippet(text, line_no + 1, line_no + 1 + new.count("\n")), False

        if command == "create":
            return ("Error: rewriting the whole file is disabled. Fix it with small str_replace "
                    "edits to the lines that are wrong."), True
        return f"Error: unsupported command {command!r}. Use view, str_replace or insert.", True


def _first_message(path: Path, class_name: str, report: str) -> str:
    return (
        f"File: {path.name} (scene class {class_name})\n\n"
        f"{numbered(path.read_text())}\n\n"
        f"Latest report:\n{report}\n\n"
        "Fix it with minimal edits, then call render_scene."
    )


def fix_scene(llm: LLM, path: Path, class_name: str, check: Callable[[], Check],
              first: Check, max_turns: int, log: Callable[[str], None] = print,
              require_edits: bool = False) -> FixOutcome:
    """``require_edits``: success needs at least one edit (used for user change
    requests, where the file already renders cleanly before any edit)."""
    system = knowledge.prompt("fixer").replace("{toolkit_reference}", knowledge.toolkit_reference())
    tools = [EDITOR_TOOL, RENDER_TOOL]
    editor = SceneEditor(path)
    messages: list[dict] = [{"role": "user", "content": _first_message(path, class_name, first.feedback)}]
    last = first
    edits_at_last_check = 0

    def run_check() -> Check:
        nonlocal last, edits_at_last_check
        last = check()
        edits_at_last_check = editor.edits
        log(f"    render_scene -> {'clean' if last.clean else 'issues remain'}")
        return last

    for turn in range(1, max_turns + 1):
        response = llm.message("fixer", system, messages, tools)
        messages.append({"role": "assistant", "content": response.content})
        tool_uses = [b for b in response.content if b.type == "tool_use"]

        if not tool_uses:
            # The model says it is done (or got cut off). Verify instead of trusting it.
            if editor.edits != edits_at_last_check:
                run_check()
            if last.clean and (editor.edits or not require_edits):
                text = "".join(b.text for b in response.content if b.type == "text").strip()
                return FixOutcome(True, True, turn, editor.edits, last.feedback, text)
            messages.append({"role": "user", "content":
                             "Not fixed yet. Latest report:\n" + last.feedback + "\nKeep editing, then call render_scene."})
            continue

        results = []
        for tu in tool_uses:
            if tu.name == EDITOR_TOOL_NAME:
                content, is_error = editor.handle(dict(tu.input))
                cmd = tu.input.get("command")
                log(f"    edit {cmd}{' (rejected)' if is_error else ''}")
            elif tu.name == "render_scene":
                content, is_error = run_check().feedback, False
            else:
                content, is_error = f"Error: unknown tool {tu.name}", True
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": content,
                            "is_error": is_error})
        if last.clean and edits_at_last_check == editor.edits and (editor.edits or not require_edits):
            return FixOutcome(True, True, turn, editor.edits, last.feedback, "fixed")
        messages.append({"role": "user", "content": results})

    if editor.edits != edits_at_last_check:
        run_check()
    return FixOutcome(last.clean, last.rendered, max_turns, editor.edits, last.feedback)
