"""
techniques: physics_simulation, parametric_motion, value_tracker, traced_path, velocity_vector, axes
domain: physics, kinematics
summary: Projectile launched at an angle; ball, trail and live velocity vector driven by a time tracker.
"""
import numpy as np
from manim import *
from manim_kit import *


class ProjectileMotion(ThemedVoiceoverScene):
    def construct(self):
        v0, theta, g = 8.0, np.radians(50), 9.8
        vx, vy0 = v0 * np.cos(theta), v0 * np.sin(theta)
        flight_time = 2 * vy0 / g

        equations = place_in_zone(
            tex(r"x(t) = v_0 \cos\theta \, t", r"\qquad", r"y(t) = v_0 \sin\theta \, t - \tfrac{1}{2} g t^2",
                font_size=40),
            "TOP",
        )
        axes, axes_group = labeled_axes([0, 7, 1], [0, 2.5, 0.5], "x", "y", zone_name="CENTER")
        t = ValueTracker(0)

        def state(time):
            return vx * time, vy0 * time - 0.5 * g * time**2, vy0 - g * time

        def ball_point():
            x, y, _ = state(t.get_value())
            return axes.c2p(x, y)

        ball = always_redraw(lambda: Dot(ball_point(), radius=0.1, color=T.highlight))
        trail = TracedPath(ball.get_center, stroke_color=T.primary, stroke_width=4)

        def velocity_arrow():
            x, y, vy = state(t.get_value())
            k = 0.12  # seconds of travel the arrow represents
            return Arrow(axes.c2p(x, y), axes.c2p(x + k * vx, y + k * vy), buff=0, color=T.accent,
                         stroke_width=4, max_tip_length_to_length_ratio=0.3)

        velocity = always_redraw(velocity_arrow)

        with self.voiceover(text="A ball is launched at fifty degrees. Horizontally it moves steadily; vertically, gravity pulls it back.") as tracker:
            self.play(Write(equations), Create(axes_group))
            self.play(FadeIn(ball), FadeIn(velocity))
        self.add(trail)
        with self.voiceover(text="Notice the velocity vector tilting down as gravity acts.") as tracker:
            self.play(t.animate.set_value(flight_time), run_time=4, rate_func=linear)
