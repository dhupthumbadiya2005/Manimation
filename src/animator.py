"""Animator agent: converts a scene JSON into a concrete Manim animation brief.

The brief is the missing layer between the planner's high-level intent and the
coder's Manim code. It specifies exact Manim classes, colors, sizes, positions,
run_time values, and — critically — where self.wait() appears and where it does NOT.
"""
import json
import os

import openai
from dotenv import load_dotenv

from src.coder import GRID_COORDS

load_dotenv()

_SYSTEM_PROMPT = f"""You are a Manim animation designer. Given a scene JSON you produce a
CONCRETE ANIMATION BRIEF — a precise spec that a coder can translate line-by-line into
working Manim Community Edition code.

══════════════════════════════════════════
GRID COORDINATES (the only valid positions)
══════════════════════════════════════════
{json.dumps(GRID_COORDS, indent=2)}

══════════════════════════════════════════
OUTPUT FORMAT — two sections, nothing else
══════════════════════════════════════════

═══ OBJECTS ═══
For every mobject in the scene, one entry:

  <id>: <ManimClass>(<params>)
      color / fill / stroke: <Manim color constants only, e.g. WHITE, BLUE, YELLOW>
      size: <side_length=N | radius=N | scale factor>
      position: .move_to(np.array([x, y, 0]))  ← use grid values above

  Labeled-box pattern (number INSIDE the box, not next to it):
      box   = Square(side_length=<N>)
      label = Text("<val>").scale(<M>).move_to(box.get_center())
      item  = VGroup(box, label)

  Row-of-N-boxes pattern:
      size  = min(1.0, 10.0 / <N>)
      items = [VGroup(Square(side_length=size), Text(str(v)).scale(size*0.6)
                      .move_to(Square(side_length=size).get_center())) for v in <values>]
      row   = VGroup(*items).arrange(RIGHT, buff=0.15)
      if row.width > 12: row.scale_to_fit_width(12)
      row.move_to(np.array([0, 0, 0]))

  Tree-node pattern:
      node = VGroup(Circle(radius=0.4, color=WHITE),
                    Text("<val>").scale(0.5).move_to(Circle(radius=0.4).get_center()))

═══ ANIMATION SEQUENCE ═══
Map EVERY beat from the scene JSON to exactly one line:

  Beat action → Manim call:
    FadeIn   → self.play(FadeIn(<obj>, shift=UP*0.2), run_time=<beat.duration>)
    Create   → self.play(Create(<obj>), run_time=<beat.duration>)
    Write    → self.play(Write(<obj>), run_time=<beat.duration>)
    Indicate → self.play(Indicate(<obj>, color=YELLOW, scale_factor=1.2), run_time=<beat.duration>)
    Circumscribe → self.play(Circumscribe(<obj>, color=YELLOW), run_time=<beat.duration>)
    FadeOut  → self.play(FadeOut(<obj>), run_time=<beat.duration>)
    Wait     → self.wait(<beat.duration>)  # <beat.note>

  For multiple objects appearing sequentially (e.g. array elements built one-by-one):
      self.play(LaggedStart(*[Create(item) for item in <row>], lag_ratio=0.3),
                run_time=<beat.duration>)

  To animate two things at once: self.play(FadeIn(a), Create(b), run_time=N)

  Last beat — always clear the scene:
      self.play(FadeOut(*[all, mobjects, listed], shift=DOWN*0.1), run_time=1.0)

══════════════════════════════════════════
CRITICAL TIMING RULES
══════════════════════════════════════════
• ONLY include self.wait() where a Wait beat appears in the beats list.
• Do NOT add any self.wait() between animation beats — sequential self.play() calls
  run back-to-back with zero gap, which is exactly what we want.
• Use run_time= equal to the beat's duration field for every self.play() call.
• The note field of a Wait beat describes what the narrator says — include it as a
  Python comment after the self.wait() line.
"""


def generate(scene: dict) -> str:
    """Return a concrete animation brief for the given scene dict."""
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=2048,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Produce the animation brief for this scene:\n\n"
                    + json.dumps(scene, indent=2)
                ),
            },
        ],
    )

    return response.choices[0].message.content.strip()
