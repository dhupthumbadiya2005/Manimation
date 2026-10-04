# manim_kit reference (Manim Community Edition 0.21)

Every scene file is a standalone Python module rendered with `manim render`.

## File shape (mandatory)

```python
from manim import *
from manim_kit import *
# optional: import numpy as np, math, random, itertools, functools, collections

class Scene01(ThemedVoiceoverScene):          # exact class name is given in the task
    def construct(self):
        with self.voiceover(text="First narration sentence.") as tracker:
            ...animations for this beat...
        with self.voiceover(text="Next beat narration.") as tracker:
            ...
```

- One `with self.voiceover(text=...)` block per storyboard beat, narration text copied verbatim.
- Inside a block, animations may take longer or shorter than the speech; the block waits for the speech to end.
  To stretch one animation over the whole beat use `run_time=tracker.duration`
  (or `tracker.get_remaining_duration()` after earlier plays in the same block).
- Only the imports above are allowed. No file, network, os or subprocess access.

## Theme — never hard-code colors

`T` is the active theme. Color roles: `T.text`, `T.muted`, `T.primary` (blue), `T.secondary` (green),
`T.highlight` (yellow), `T.accent` (red), `T.gold`, `T.teal`, `T.purple`, `T.background`.
Use the storyboard's `color_role` for every object, e.g. `color=T.primary`. Do not use RED/BLUE/hex literals.

## Layout zones — never place things by guessing coordinates

Frame is 14.2 x 8 units. Zones: `TOP` (title band), `BOTTOM` (caption band), `CENTER` (main area),
`LEFT` / `RIGHT` (halves of the main area), `FULL`.

- `place_in_zone(mob, "CENTER", align="center"|"top"|"bottom"|"left"|"right")` -> shrinks to fit, moves; returns mob.
- `zone("LEFT")` -> Zone with `.x0 .x1 .y0 .y1 .width .height .center`.
- Two objects in the same zone overlap unless you `stack(...)` them or `.next_to(...)` one off the other.
- Clear the stage between beats when the next beat shows new content: `clear_scene(self)`.

## Helpers (prefer these over hand-rolled equivalents)

| helper | returns | notes |
|---|---|---|
| `title_card(text, font_size=44)` | Text in TOP | scene titles |
| `caption(text, font_size=30)` | Text in BOTTOM, muted | short on-screen notes; update with `Transform(old, caption(new))` |
| `tex(*parts, font_size=48)` | MathTex | applies the storyboard symbol colors to whole parts; split symbols with `{{ }}` or separate args: `tex("{{f(x)}} = {{x}}^2")` |
| `labeled_axes(x_range, y_range, x_label="x", y_label="y", zone_name="CENTER")` | `(axes, group)` | plot on `axes` (`axes.plot`, `axes.c2p`, `axes.get_area`), animate `group` (`Create(group)`) |
| `equation_chain(self, [step1, step2, ...], zone_name="CENTER", run_time=1.5, pause=0.6)` | final MathTex | Write + TransformMatchingTex through the steps; wrap shared terms in `{{ }}` |
| `highlight_box(mob)` | SurroundingRectangle (highlight color) | |
| `stack(*mobs, direction=DOWN, buff=0.4)` | VGroup arranged | |
| `clear_scene(self)` | — | fades out everything |

## Manim CE rules (the most common mistakes)

- This is **Manim Community**, not ManimGL/3b1b's manim: use `Create` (not ShowCreation), `Text` (not TextMobject),
  `MathTex` (not TexMobject), `Tex` for text-mode LaTeX, `Axes` (not GraphScene), no `CONFIG = {...}`,
  no `self.camera.frame` (scene is not a MovingCameraScene).
- `MathTex` is math mode: no `$...$`. Use `\text{...}` for words inside math.
- `Text` renders characters literally: never put math in it (`Text("y = x^2")` shows a caret). For titles or
  sentences containing math use `Tex(r"How steep is $y = x^2$?")`; `title_card`/`caption` are Text-only.
- Never use `tex_to_color_map` / `set_color_by_tex` with single letters (they split inside commands like `\exp`);
  use `tex(...)` with `{{ }}` parts or index parts: `eq = tex("a^2", "+", "b^2"); eq[0].set_color(T.primary)`.
- Animating values: `x = ValueTracker(0)`; `dot = always_redraw(lambda: Dot(axes.c2p(x.get_value(), f(x.get_value()))))`;
  `self.play(x.animate.set_value(3), run_time=3)`.
- Live numbers: `DecimalNumber(0, num_decimal_places=2)` + `.add_updater(lambda m: m.set_value(x.get_value()))`.
- Trails: `TracedPath(mob.get_center, stroke_color=T.highlight)`; `self.add(trail)` right before the motion starts.
- `Graph(..., labels=True)` vertices are LabeledDots: recolor with `.set_fill(color, family=False)` so labels stay visible;
  pass `label_fill_color=T.background`. For small trees give an explicit `layout={v: [x, y, 0]}`.
- `Arrow(start, end, buff=0)` for exact endpoints; `Vector([x, y])` from the origin.
- `ApplyMatrix(matrix, mobject)` for linear maps; `NumberPlane()` for grids.
- `Transform(a, b)` keeps `a` on screen (now looking like b); `ReplacementTransform(a, b)` puts `b` on screen.
- Text sizes: body Text `font_size` >= 28, MathTex >= 36, so they stay readable at 480p.
- Keep each beat to at most ~4 new objects; 3B1B style is uncluttered: one idea on screen at a time.
