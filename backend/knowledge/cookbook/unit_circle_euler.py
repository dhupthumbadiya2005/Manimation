"""
techniques: unit_circle, trigonometry, euler_formula, value_tracker, always_redraw, projections, complex_numbers, decimal_number
domain: math, trigonometry, complex_numbers
summary: A point rotating on the unit circle; its cos and sin projections and the formula e^{i theta} = cos + i sin.
"""
import numpy as np
from manim import *
from manim_kit import *


class UnitCircleEuler(ThemedVoiceoverScene):
    def construct(self):
        z = zone("LEFT")
        center = np.array([*z.center, 0.0])
        r = 1.8
        theta = ValueTracker(0.6)

        axes = VGroup(
            Line(center + LEFT * 2.3, center + RIGHT * 2.3, color=T.muted),
            Line(center + DOWN * 2.2, center + UP * 2.2, color=T.muted),
        )
        circle = Circle(radius=r, color=T.text, stroke_width=2).move_to(center)

        def point():
            a = theta.get_value()
            return center + r * np.array([np.cos(a), np.sin(a), 0.0])

        radius = always_redraw(lambda: Line(center, point(), color=T.highlight, stroke_width=4))
        dot = always_redraw(lambda: Dot(point(), color=T.highlight))
        cos_line = always_redraw(lambda: Line(center, [point()[0], center[1], 0], color=T.primary, stroke_width=6))
        sin_line = always_redraw(lambda: Line([point()[0], center[1], 0], point(), color=T.secondary, stroke_width=6))

        formula = tex(r"e^{i\theta}", "=", r"\cos\theta", "+", r"i\sin\theta", font_size=52)
        formula[0].set_color(T.highlight)
        formula[2].set_color(T.primary)
        formula[4].set_color(T.secondary)
        angle_label = tex(r"\theta =", font_size=44)
        angle_value = DecimalNumber(theta.get_value(), num_decimal_places=2, font_size=44)
        angle_value.add_updater(lambda m: m.set_value(theta.get_value()))
        readout = VGroup(angle_label, angle_value).arrange(RIGHT, buff=0.2)
        right = place_in_zone(stack(formula, readout, buff=0.8), "RIGHT")
        angle_value.add_updater(lambda m: m.next_to(angle_label, RIGHT, buff=0.2))

        with self.voiceover(text="Take a point on the unit circle at angle theta.") as tracker:
            self.play(Create(axes), Create(circle))
            self.play(Create(radius), FadeIn(dot), Write(right))
        with self.voiceover(text="Its horizontal shadow is cosine, its vertical shadow is sine, and together they are e to the i theta.") as tracker:
            self.play(Create(cos_line), Create(sin_line))
            self.play(theta.animate.set_value(0.6 + TAU), run_time=tracker.get_remaining_duration() or 4,
                      rate_func=linear)
