"""LLM-based Manim code generator."""
import json
import os

import openai
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

SYSTEM_PROMPT = f"""You are a Manim Community Edition expert writing animation scenes for a 3Blue1Brown-style educational video. Output ONLY a single complete Python file — no markdown fences, no prose.

════════════════════════════════════════════════
OUTPUT RULES
════════════════════════════════════════════════
• Exactly ONE Scene subclass, named Scene<scene_id> (e.g. Scene1).
• Allowed imports only: from manim import *  |  import numpy as np  |  import math
• No while loops, no time.sleep().
• Scene starts from an empty frame. End with self.play(FadeOut(*self.mobjects)) to clear everything.

════════════════════════════════════════════════
FRAME BOUNDS  (CRITICAL — objects outside = broken video)
════════════════════════════════════════════════
Frame: 14.2 units wide × 8 units tall, origin at center.
Safe zone: x ∈ [-6.5, 6.5], y ∈ [-3.6, 3.6]. Keep 0.5 unit margin from every edge.

Grid anchors — use .move_to(np.array([x, y, 0])):
{json.dumps(GRID_COORDS, indent=2)}

════════════════════════════════════════════════
SIZING  (CRITICAL — most frame-overflow bugs are here)
════════════════════════════════════════════════
• Square() default side_length = 2.0 — this is HUGE. ALWAYS pass side_length explicitly.
• For arrays: side_length = min(1.0, 10.0 / N) where N = number of items.
• After any .arrange(), check width: if group.width > 12: group.scale_to_fit_width(12)
• Circle default radius = 1.0 — use radius=0.4 for tree nodes, radius=0.5 for small shapes.
• Text default is large — always .scale(0.6–0.9) for body text, .scale(1.0–1.2) for titles.

LABELED BOX PATTERN (numbers INSIDE the box, not next to it):
    box   = Square(side_length=1.0)
    label = Text("5").scale(0.65).move_to(box.get_center())
    item  = VGroup(box, label)

ROW OF N LABELED BOXES:
    size  = min(1.0, 10.0 / len(values))
    items = []
    for v in values:
        b = Square(side_length=size)
        l = Text(str(v)).scale(size * 0.6).move_to(b.get_center())
        items.append(VGroup(b, l))
    row = VGroup(*items).arrange(RIGHT, buff=0.15)
    if row.width > 12:
        row.scale_to_fit_width(12)
    row.move_to(ORIGIN)

TREE NODE:
    node = VGroup(Circle(radius=0.4), Text("A").scale(0.5).move_to(Circle(radius=0.4).get_center()))

════════════════════════════════════════════════
3BLUE1BROWN STYLE
════════════════════════════════════════════════
Colors: BLUE, YELLOW, GREEN, RED, WHITE, GREY, BLUE_D, YELLOW_D (Manim constants, no hex strings).
Highlight: Indicate(mob), Circumscribe(mob, color=YELLOW), Flash(mob), SurroundingRectangle(mob, color=YELLOW, buff=0.1)
Math: always MathTex(r"...") — never Text() for equations or formulas.
Annotations: always smaller than the mobject they annotate (scale 0.5–0.7).

ANIMATION REFERENCE:
• self.play(FadeIn(mob, shift=UP*0.3))   — smooth entrance
• self.play(Write(mob))                  — for text/equations
• self.play(Create(mob))                 — for shapes/lines
• self.play(Indicate(mob, color=YELLOW)) — pulse highlight
• self.play(FadeOut(mob1, mob2, ...))    — fade multiple at once
• self.wait(n)                           — pause (keep short, 2–5s)
• For arrow pointing at something: Arrow(start=UP*1.5 + mob.get_top(), end=mob.get_top(), color=YELLOW)
  — always derive arrow endpoints from mobject methods (.get_top(), .get_center(), etc.), never raw coords.
"""


def generate(scene: dict, previous_error: str | None = None, previous_code: str | None = None) -> str:
    """Call GPT-4o to generate Manim Python code for the given scene JSON."""
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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

    system = SYSTEM_PROMPT.replace("<scene_id>", str(scene.get("scene_id", "N")))

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
    )

    code = response.choices[0].message.content.strip()

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
