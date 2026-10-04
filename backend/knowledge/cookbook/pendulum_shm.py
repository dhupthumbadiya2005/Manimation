"""
techniques: physics_simulation, simple_harmonic_motion, pendulum, live_graph, traced_path, value_tracker
domain: physics, oscillations
summary: Swinging pendulum on the left, its angle plotted against time on the right, both driven by one tracker.
"""
import numpy as np
from manim import *
from manim_kit import *


class PendulumSHM(ThemedVoiceoverScene):
    def construct(self):
        theta0, omega = 0.5, 2.0
        length = 3.2
        pivot = np.array([-3.4, 2.1, 0.0])
        t = ValueTracker(0)

        def theta(time):
            return theta0 * np.cos(omega * time)

        def bob_point():
            a = theta(t.get_value())
            return pivot + length * np.array([np.sin(a), -np.cos(a), 0.0])

        ceiling = Line(pivot + LEFT * 0.8, pivot + RIGHT * 0.8, color=T.muted)
        rod = always_redraw(lambda: Line(pivot, bob_point(), color=T.text, stroke_width=3))
        bob = always_redraw(lambda: Dot(bob_point(), radius=0.18, color=T.primary))

        axes, axes_group = labeled_axes([0, 6, 1], [-0.6, 0.6, 0.3], "t", r"\theta", zone_name="RIGHT")
        tracer = always_redraw(lambda: Dot(axes.c2p(t.get_value(), theta(t.get_value())),
                                           radius=0.05, color=T.highlight))
        curve = TracedPath(tracer.get_center, stroke_color=T.highlight, stroke_width=3)

        with self.voiceover(text="For small swings, a pendulum's angle follows a cosine wave.") as tracker:
            self.play(Create(ceiling), Create(rod), FadeIn(bob), Create(axes_group))
            self.add(tracer, curve)
        with self.voiceover(text="That is simple harmonic motion.") as tracker:
            self.play(t.animate.set_value(6), run_time=6, rate_func=linear)
