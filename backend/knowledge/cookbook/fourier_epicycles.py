"""
techniques: epicycles, rotating_vectors, traced_path, value_tracker, always_redraw, fourier
domain: math, signal_processing
summary: Chain of rotating vectors (Fourier terms of a square wave) whose tip traces a path.
"""
import numpy as np
from manim import *
from manim_kit import *


class FourierEpicycles(ThemedVoiceoverScene):
    def construct(self):
        title = title_card("Adding rotating vectors")
        t = ValueTracker(0)
        # (frequency, radius): first odd harmonics of a square wave
        terms = [(1, 1.3), (3, 1.3 / 3), (5, 1.3 / 5), (7, 1.3 / 7)]
        origin = np.array([0.0, -0.4, 0.0])

        def joints():
            pts = [origin]
            for k, r in terms:
                angle = k * t.get_value()
                pts.append(pts[-1] + r * np.array([np.cos(angle), np.sin(angle), 0.0]))
            return pts

        def draw_chain():
            pts = joints()
            circles = VGroup(*[
                Circle(radius=r, stroke_color=T.muted, stroke_width=1.5).move_to(c)
                for (_, r), c in zip(terms, pts[:-1])
            ])
            arrows = VGroup(*[
                Arrow(s, e, buff=0, stroke_width=3, color=T.primary,
                      max_tip_length_to_length_ratio=0.2)
                for s, e in zip(pts[:-1], pts[1:])
            ])
            return VGroup(circles, arrows)

        chain = always_redraw(draw_chain)
        tip = always_redraw(lambda: Dot(joints()[-1], radius=0.05, color=T.highlight))
        trail = TracedPath(tip.get_center, stroke_color=T.highlight, stroke_width=3)

        with self.voiceover(text="Each vector spins at its own frequency, and they are added tip to tail.") as tracker:
            self.play(Write(title), FadeIn(chain), FadeIn(tip))
        self.add(trail)
        with self.voiceover(text="Follow the last tip, and a shape emerges.") as tracker:
            self.play(t.animate.set_value(2 * PI), run_time=6, rate_func=linear)
