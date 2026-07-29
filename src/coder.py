"""LLM-based Manim code generator."""
import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

# Fixed grid-to-coordinate mapping (frame is 14.2 wide x 8 tall, origin at center)
GRID_COORDS = {
    "top-left":    [-4.75,  3.0, 0],
    "top-center":  [ 0.0,   3.0, 0],
    "top-right":   [ 4.75,  3.0, 0],
    "mid-left":    [-4.75,  0.0, 0],
    "mid-center":  [ 0.0,   0.0, 0],
    "mid-right":   [ 4.75,  0.0, 0],
    "bot-left":    [-4.75, -3.0, 0],
    "bot-center":  [ 0.0,  -3.0, 0],
    "bot-right":   [ 4.75, -3.0, 0],
    "full":        [ 0.0,   0.0, 0],
}

SYSTEM_PROMPT = f"""You are an expert Manim Community Edition animator. You write complete, self-contained Python files that use Manim Community Edition (version 0.20.1) syntax ONLY. Never use ManimGL or manim-cairo syntax.

HARD RULES — violating any of these will cause immediate rejection:
1. Output ONLY the Python source code. No markdown fences, no prose, no explanations.
2. The file must contain exactly ONE Scene subclass. Name it Scene<scene_id> (e.g. Scene1 for scene_id 1).
3. Use ONLY these imports: from manim import *, import numpy as np, import math. No other imports.
4. Frame dimensions: 14.2 units wide × 8 units tall. Use ONLY the coordinate grid below — never invent absolute coordinates.
5. Never use while loops or time.sleep().
6. Scene must start from an empty frame. The LAST action must always be FadeOut of ALL on-screen mobjects (even if not in the beats list).
7. Never exceed max_simultaneous_mobjects on screen at the same time.
8. For coordinate placement, use move_to() with the values from this grid (no other coordinates allowed):

GRID COORDINATES:
{json.dumps(GRID_COORDS, indent=2)}

When placing mobjects, call .move_to(np.array([x, y, 0])) using the grid values above.

MANIM COMMUNITY EDITION PATTERNS:
- Text("string") for plain text
- MathTex(r"latex") for equations
- Square(), Circle(), Rectangle() for shapes
- Arrow(start, end) for arrows — use UP, DOWN, LEFT, RIGHT direction vectors, not raw coords
- VGroup(*items) to group multiple mobjects
- For an array/row of boxes: create individual Square() mobjects, label them with Text(), group with VGroup, arrange with .arrange(RIGHT)
- For a tree node: use Circle() + Text() overlaid in a VGroup
- self.play(FadeIn(mob)), self.play(Write(mob)), self.play(Create(mob)) for animations
- self.play(FadeOut(mob1, mob2, ...)) to fade out — accepts multiple args
- self.wait(n) to pause

IMPORTANT: LabeledNode does NOT exist in Manim. Use VGroup(Circle(), Text("label")) instead.
"""


def generate(scene: dict, previous_error: str | None = None, previous_code: str | None = None) -> str:
    """Call Claude to generate Manim Python code for the given scene JSON."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    user_message = f"Generate a complete Manim Python file for this scene:\n\n{json.dumps(scene, indent=2)}"

    if previous_error and previous_code:
        user_message += f"""

The previous attempt FAILED. Here is the code that failed:

```python
{previous_code}
```

Error / reason for failure:
{previous_error}

Write a complete, corrected Python file from scratch. Fix all issues. Do not output a diff or patch — output the entire file."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT.replace("<scene_id>", str(scene.get("scene_id", "N"))),
        messages=[{"role": "user", "content": user_message}],
    )

    code = response.content[0].text.strip()

    # Strip markdown fences if the model added them despite instructions
    if code.startswith("```"):
        lines = code.split("\n")
        # Remove first and last fence lines
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines)

    return code
