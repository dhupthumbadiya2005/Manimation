"""LLM-based Manim code generator. Takes a scene description, writes Manim Python."""
import json
import os

import openai
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are a Manim Community Edition expert writing 3Blue1Brown-style educational animations.

You receive a scene description in plain English. Implement it as a complete, working Manim Python file.

OUTPUT: A single Python file. No markdown fences. No prose. Code only.

════════════════════════════════════════
HARD RULES
════════════════════════════════════════
• Exactly ONE Scene subclass, named Scene<N> (e.g. Scene3).
• Allowed imports ONLY: from manim import *  |  import numpy as np  |  import math
• No while loops. No time.sleep().
• Last line of construct(): self.play(FadeOut(*self.mobjects), run_time=0.8)
• All numpy arrays must be 3-element: np.array([x, y, 0]) — NEVER np.array([x, y])

NEVER USE THESE (they do not exist in Manim CE and will crash):
  ShowCreation → use Create instead
  ShowCreationThenDestruction → use Create then Uncreate, or ShowPassingFlash
  GrowFromCenter → use GrowFromPoint(mob, mob.get_center()) or FadeIn
  DrawBorderThenFill → use Create or Write
  FadeInFromDown → use FadeIn(mob, shift=UP*0.3)
  SpiralIn → use Create
  Write(mob) on non-text → only use Write() on Text/MathTex/Tex objects; use Create() on shapes

════════════════════════════════════════
FRAME BOUNDS  — objects outside = broken video
════════════════════════════════════════
Frame: 14.2 units wide × 8 tall. Origin at center.
Safe zone: x ∈ [-6.5, 6.5], y ∈ [-3.6, 3.6]. Keep 0.5u margin from every edge.

Position anchors (.move_to(np.array([x, y, 0]))):
  top y=3.0   mid y=0.0   bot y=-3.0
  left x=-4.75  center x=0.0  right x=4.75

════════════════════════════════════════
SIZING  — most overflow bugs are here
════════════════════════════════════════
Square() default side_length=2 — ALWAYS set explicitly.
Rectangle() default width=4, height=2 — ALWAYS set explicitly.
For N array boxes: side_length = min(1.0, 10.0 / N)
After .arrange(): if group.width > 12: group.scale_to_fit_width(12)
Circle: radius=0.4 for nodes, radius=0.25 for small dots.
Text titles: .scale(1.3–1.6). Body text: .scale(0.7–0.9). Annotations: .scale(0.5–0.6).
MathTex: .scale(0.85) default.

════════════════════════════════════════
MANIM PATTERNS FOR ALGORITHM VISUALIZATION
════════════════════════════════════════

ROW OF LABELED BOXES (the standard array):
    values = [2, 7, 1, 8, 3, 5]
    size = min(1.0, 10.0 / len(values))
    boxes = []
    for v in values:
        sq = Square(side_length=size, color=WHITE)
        lb = Text(str(v)).scale(size * 0.65).move_to(sq)
        boxes.append(VGroup(sq, lb))
    row = VGroup(*boxes).arrange(RIGHT, buff=0.1)
    if row.width > 12: row.scale_to_fit_width(12)
    row.move_to(np.array([0, 0, 0]))
    self.play(LaggedStart(*[FadeIn(b) for b in boxes], lag_ratio=0.15), run_time=2.0)

POINTER ARROW (above an element, pointing down):
    ptr = Arrow(UP * 0.7, ORIGIN, color=YELLOW, buff=0, stroke_width=3)
    ptr_label = Text("mid").scale(0.5).next_to(ptr, UP, buff=0.05)
    ptr_grp = VGroup(ptr, ptr_label)
    ptr_grp.next_to(boxes[i], UP, buff=0.05)
    self.play(FadeIn(ptr_grp), run_time=0.5)

MOVE POINTER to a new index:
    self.play(ptr_grp.animate.next_to(boxes[new_i], UP, buff=0.05), run_time=0.6)

HIGHLIGHT a box:
    self.play(boxes[i][0].animate.set_color(YELLOW), run_time=0.4)

GRAY OUT a range (eliminated elements):
    self.play(*[boxes[j][0].animate.set_color(GREY) for j in range(lo, mid + 1)], run_time=0.5)

FLASH on found/success:
    self.play(Flash(boxes[i], color=GREEN, flash_radius=size * 0.8), run_time=0.8)
    self.play(boxes[i][0].animate.set_color(GREEN), run_time=0.4)

ELEMENT SLIDING INTO A STACK (from above):
    item = VGroup(Rectangle(width=2.0, height=0.85, color=BLUE), Text("3").scale(0.7))
    item.move_to(np.array([0, 4.0, 0]))  # start above screen
    self.play(item.animate.move_to(np.array([0, target_y, 0])), run_time=0.9,
              rate_func=rush_into)

ELEMENT POPPING OFF A STACK (fly up and out):
    self.play(item.animate.move_to(np.array([0, 4.5, 0])), run_time=0.8,
              rate_func=rush_from_point)

TREE NODE:
    node = VGroup(Circle(radius=0.38, color=WHITE, fill_color=BLACK, fill_opacity=1),
                  Text("5").scale(0.55).move_to(ORIGIN))
    edge = Line(parent_node.get_bottom(), child_node.get_top(), color=WHITE)

BAR CHART BAR:
    bar = Rectangle(width=0.7, height=h * scale, color=BLUE, fill_color=BLUE, fill_opacity=0.8)
    bar.next_to(baseline, UP, buff=0)  # align bottom to baseline

COMPARISON LABEL (appears, then fades after 2–3s):
    cmp = Text("9 < 11 → search right").scale(0.65).move_to(np.array([0, -3.2, 0]))
    self.play(Write(cmp), run_time=0.7)
    self.wait(2.5)
    self.play(FadeOut(cmp), run_time=0.4)

════════════════════════════════════════
ALGORITHM IMPLEMENTATION APPROACH
════════════════════════════════════════
For search/sort/traversal algorithms:
  1. Build the data structure in Python (list, dict, etc.)
  2. Animate initial appearance with LaggedStart
  3. Implement the algorithm in Python — compute what changes at each step
  4. For each step: animate pointer moves, color changes, element movements
  5. self.wait(2–4) after key decision moments (long enough to read, not longer)
  6. Flash/Circumscribe at climactic moments

Binary search example skeleton:
    lo, hi = 0, len(values) - 1
    target = 11
    for _ in range(len(values)):  # bounded loop, not while
        if lo > hi:
            break
        mid = (lo + hi) // 2
        # move mid pointer
        self.play(mid_grp.animate.next_to(boxes[mid], UP, buff=0.05), run_time=0.5)
        # highlight
        self.play(boxes[mid][0].animate.set_color(YELLOW), run_time=0.4)
        if values[mid] == target:
            self.play(Flash(boxes[mid], color=GREEN), run_time=0.8)
            break
        elif values[mid] < target:
            self.play(*[boxes[j][0].animate.set_color(GREY) for j in range(lo, mid + 1)], run_time=0.5)
            lo = mid + 1
            self.play(l_grp.animate.next_to(boxes[lo], UP, buff=0.05), run_time=0.5)
        else:
            self.play(*[boxes[j][0].animate.set_color(GREY) for j in range(mid, hi + 1)], run_time=0.5)
            hi = mid - 1
            self.play(r_grp.animate.next_to(boxes[hi], UP, buff=0.05), run_time=0.5)
        self.wait(2.5)

════════════════════════════════════════
TIMING
════════════════════════════════════════
• Animation steps: run_time=0.4–1.0s (fast and crisp)
• Big reveals (whole structure appearing): run_time=1.5–2.5s
• self.wait(2–4) after key moments the viewer needs to absorb
• self.wait(5–10) for long narrator explanations — but keep visual active (color, indicate)
• NO self.wait() between small sequential steps — back-to-back self.play() is fine
• ALWAYS pass run_time= to every self.play()
"""


def generate(
    scene: dict,
    previous_error: str | None = None,
    previous_code: str | None = None,
) -> str:
    """Call GPT-4o to generate Manim Python code from a scene description."""
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    scene_id = scene.get("scene_id", "N")
    title = scene.get("title", "")
    description = scene.get("description", "")
    topic = scene.get("_topic", "")

    system = SYSTEM_PROMPT.replace("<N>", str(scene_id))

    user_msg = (
        f"Topic: {topic}\n"
        f"Scene {scene_id}: {title}\n\n"
        f"SCENE DESCRIPTION:\n{description}\n\n"
        f"Write the complete Manim Python file. Class name: Scene{scene_id}."
    )

    if previous_error and previous_code:
        user_msg += f"""

The previous attempt FAILED. Here is the code that failed:

```python
{previous_code}
```

Error:
{previous_error}

Write a complete corrected file from scratch. Fix all issues. Full file only — no diffs."""

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    )

    code = response.choices[0].message.content.strip()

    if code.startswith("```"):
        lines = code.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines)

    return code
