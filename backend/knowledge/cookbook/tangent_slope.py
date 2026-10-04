"""
techniques: value_tracker, always_redraw, updater, decimal_number, derivative, tangent_line
domain: math
summary: Slide a point along a curve with a ValueTracker; tangent line and live slope readout follow it.
"""
from manim import *
from manim_kit import *


class TangentSlope(ThemedVoiceoverScene):
    def construct(self):
        def f(x):
            return 0.5 * x**2

        axes, axes_group = labeled_axes([-1, 4, 1], [-1, 8, 2], zone_name="LEFT")
        graph = axes.plot(f, x_range=[-1, 3.9], color=T.primary)
        x = ValueTracker(0.5)

        # always_redraw rebuilds the mobject every frame from the tracker's value.
        dot = always_redraw(lambda: Dot(axes.c2p(x.get_value(), f(x.get_value())), color=T.highlight))

        def tangent_line():
            x0 = x.get_value()
            m = x0  # f'(x) = x
            return Line(axes.c2p(x0 - 1, f(x0) - m), axes.c2p(x0 + 1, f(x0) + m), color=T.highlight)

        tangent = always_redraw(tangent_line)

        slope_label = tex(r"\text{slope} =", font_size=44)
        slope_value = DecimalNumber(x.get_value(), num_decimal_places=2, font_size=44, color=T.highlight)
        readout = VGroup(slope_label, slope_value).arrange(RIGHT, buff=0.2)
        place_in_zone(readout, "RIGHT")
        slope_value.add_updater(lambda m: m.set_value(x.get_value()))

        with self.voiceover(text="Watch the tangent line as the point slides along the curve.") as tracker:
            self.play(Create(axes_group), Create(graph))
            self.play(FadeIn(dot), Create(tangent), Write(readout))

        with self.voiceover(text="The slope grows exactly as fast as x does. That is the derivative.") as tracker:
            self.play(x.animate.set_value(3), run_time=tracker.get_remaining_duration())
