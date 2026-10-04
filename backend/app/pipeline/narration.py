"""Narration bank: synthesize every line of a video in ONE Deepgram session so
the voice keeps the same tone across beats and scenes.

Lines are read from the scene files themselves (``self.voiceover(text="...")``),
so edits made by the Fixer or by user change requests are always reflected.
The bank is keyed by (voice, all lines in order): if anything changes, the whole
video is re-narrated in one session rather than patching single lines, because a
line synthesized in a separate session would sound slightly different.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path

from manim_kit.tts_deepgram import DeepgramError, build_bank


def scene_lines(code: str) -> list[str]:
    """Narration strings in the order they appear in a scene file."""
    found = []
    for node in ast.walk(ast.parse(code)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "voiceover"):
            continue
        arg = next((k.value for k in node.keywords if k.arg == "text"), node.args[0] if node.args else None)
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            found.append((node.lineno, node.col_offset, arg.value))
    return [text for *_, text in sorted(found)]


def bank_key(voice: str, lines: list[str]) -> str:
    return hashlib.sha256(json.dumps([voice, lines]).encode()).hexdigest()[:16]


def prepare(scene_files: list[Path], voice: str, root: Path, log: Callable[[str], None]) -> Path | None:
    """Ensure a bank exists for these scenes; returns its manifest, or None if
    synthesis failed (renders then fall back to one request per line)."""
    lines = [line for f in scene_files for line in scene_lines(f.read_text())]
    if not lines:
        return None
    key = bank_key(voice, lines)
    manifest = root / key / "manifest.json"
    if manifest.exists():
        log(f"  narration: reusing {len(lines)} line(s) recorded in one session ({voice})")
        return manifest
    api_key = os.environ.get("DEEPGRAM_API_KEY", "")
    if not api_key:
        log("  narration: DEEPGRAM_API_KEY is not set")
        return None
    chars = sum(len(line) for line in dict.fromkeys(lines))
    log(f"  narration: recording {len(lines)} line(s), {chars} characters, in one Deepgram session ({voice})")
    try:
        return build_bank(lines, voice, api_key, root / key)
    except DeepgramError as err:
        log(f"  narration: one-session recording failed ({err}); falling back to one request per line")
        return None
