"""Stage 2 — Code Generation Engine.

Takes a Markdown scene plan and produces a complete, executable Manim Python file.
"""
from src.llm_client import complete

_SYSTEM_PROMPT = """You are a principal engineer and expert in creating educational animations using Manim (Community Edition). Your task is to write clean, executable, robust Python code for a Manim animation based on the provided Scene Description.

Strict Guidelines:
1. Architecture & Structure:
   - Import everything via `from manim import *`.
   - Implement modular helper methods for distinct sub-scenes inside your `Scene` class.
   - Use `ThreeDScene` if 3D shapes/surface plots are required, or `MovingCameraScene` if zooming/panning is necessary.
   - Name the single Scene subclass exactly `MainScene`.

2. Layout & Positioning:
   - Avoid element overlap! Pre-calculate spacing using `.next_to()`, `.arrange()`, or explicit coordinate vectors.
   - Ensure all visual elements remain strictly within the screen aspect ratio.
   - Frame: 14.2 units wide × 8 tall. Safe zone: x ∈ [-6.5, 6.5], y ∈ [-3.6, 3.6].

3. Animations & Transitions:
   - Use dynamic animations (`Transform`, `ReplacementTransform`, `Write`, `FadeIn`, `Indicate`).
   - Highlight active elements using `.animate.set_color(YELLOW)` or `SurroundingRectangle`.
   - Clean up scenes cleanly at transitions using `self.play(FadeOut(*self.mobjects))`.

4. Timing & Output:
   - Include clear `self.wait(seconds)` calls for narration synchronization (5–8s for key concepts).
   - Return ONLY valid, executable Python code wrapped in ```python ... ``` without fluff.

════════════════════════════════════════
HARD RULES — violations crash the renderer
════════════════════════════════════════
• Exactly ONE Scene subclass named `MainScene`.
• Allowed imports ONLY: `from manim import *`  |  `import numpy as np`  |  `import math`
• No while loops. No time.sleep().
• Last line of construct(): `self.play(FadeOut(*self.mobjects), run_time=0.8)`
• All numpy arrays must be 3-element: `np.array([x, y, 0])` — NEVER `np.array([x, y])`

NEVER USE THESE (they do not exist in Manim CE):
  ShowCreation → use Create
  GrowFromCenter → use FadeIn or GrowFromPoint(mob, mob.get_center())
  DrawBorderThenFill → use Create or Write
  FadeInFromDown → use FadeIn(mob, shift=UP*0.3)
  Write(mob) on non-text → only Write() on Text/MathTex/Tex; use Create() on shapes

════════════════════════════════════════
SIZING RULES
════════════════════════════════════════
Square() default side_length=2 — ALWAYS set explicitly.
Rectangle() default width=4, height=2 — ALWAYS set explicitly.
For N array boxes: side_length = min(1.0, 10.0 / N)
After .arrange(): if group.width > 12: group.scale_to_fit_width(12)
Text titles: .scale(1.3–1.5). Body text: .scale(0.7–0.9). MathTex: .scale(0.85).

════════════════════════════════════════
STANDARD PATTERNS
════════════════════════════════════════
ROW OF LABELED BOXES:
    values = [4, 2, 8, 1, 6, 3]
    size = min(1.0, 10.0 / len(values))
    boxes = [VGroup(Square(side_length=size, color=WHITE),
                    Text(str(v)).scale(size * 0.65)) for v in values]
    for b in boxes:
        b[1].move_to(b[0].get_center())
    row = VGroup(*boxes).arrange(RIGHT, buff=0.1)
    if row.width > 12: row.scale_to_fit_width(12)
    row.move_to(np.array([0, 0, 0]))
    self.play(LaggedStart(*[FadeIn(b) for b in boxes], lag_ratio=0.15), run_time=2.0)

POINTER ARROW (above an element, pointing down):
    ptr = Arrow(UP * 0.7, ORIGIN, color=YELLOW, buff=0, stroke_width=3)
    ptr_lbl = Text("mid").scale(0.5).next_to(ptr, UP, buff=0.05)
    ptr_grp = VGroup(ptr, ptr_lbl).next_to(boxes[i], UP, buff=0.05)
    self.play(FadeIn(ptr_grp), run_time=0.5)
    # move: self.play(ptr_grp.animate.next_to(boxes[j], UP, buff=0.05), run_time=0.6)

HIGHLIGHT / GRAY OUT:
    self.play(boxes[i][0].animate.set_color(YELLOW), run_time=0.4)
    self.play(*[boxes[j][0].animate.set_color(GREY) for j in range(lo, mid+1)], run_time=0.5)

FLASH on success:
    self.play(Flash(boxes[i], color=GREEN, flash_radius=size*0.8), run_time=0.8)

ALGORITHM LOOP PATTERN (use for-range, not while):
    for _ in range(len(values)):
        if lo > hi: break
        mid = (lo + hi) // 2
        ...  # animate each step
        self.wait(2.5)
"""


def generate(
    markdown_plan: str,
    previous_error: str | None = None,
    previous_code: str | None = None,
) -> str:
    """Return Manim Python source for the given Markdown plan.

    Strips ```python fences from the LLM response automatically.
    """
    user_msg = (
        "Generate a complete Manim Python file for the following scene plan.\n"
        "Name the Scene subclass exactly `MainScene`.\n\n"
        f"{markdown_plan}"
    )

    if previous_error and previous_code:
        user_msg += f"""

The previous attempt FAILED to render. Here is the code that failed:

```python
{previous_code}
```

Error output:
{previous_error}

Write a COMPLETE corrected file from scratch. Fix all issues. "
"Simplify visuals if needed — a working animation beats a broken complex one. "
"Full file only — no diffs, no explanations, just code."""

    raw = complete(_SYSTEM_PROMPT, user_msg, max_tokens=8192)
    return _strip_fences(raw)


def _strip_fences(text: str) -> str:
    """Remove ```python / ``` code fences if the LLM wrapped the output."""
    lines = text.split("\n")
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
