"""
techniques: axes, plot_function, waves, superposition, interference, value_tracker, always_redraw, phase_shift
domain: physics, waves
summary: Two sine waves and their sum; shifting one wave's phase turns constructive into destructive interference.
"""
import numpy as np
from manim import *
from manim_kit import *


class WaveInterference(ThemedVoiceoverScene):
    def construct(self):
        title = title_card("Adding two waves")
        axes = Axes(x_range=[0, 4 * PI, PI], y_range=[-2.2, 2.2, 1], x_length=12, y_length=4.4,
                    axis_config={"color": T.muted})
        place_in_zone(axes, "CENTER")
        phase = ValueTracker(0)

        def wave(f, color, width=3):
            return axes.plot(f, x_range=[0, 4 * PI], color=color, stroke_width=width)

        w1 = always_redraw(lambda: wave(lambda x: np.sin(x), T.primary))
        w2 = always_redraw(lambda: wave(lambda x: np.sin(x + phase.get_value()), T.secondary))
        total = always_redraw(lambda: wave(lambda x: np.sin(x) + np.sin(x + phase.get_value()), T.highlight, 5))
        status = caption("in phase: constructive")

        with self.voiceover(text="Two identical waves in step add up to a wave twice as tall.") as tracker:
            self.play(Write(title), Create(axes))
            self.play(Create(w1), Create(w2))
            self.play(Create(total), FadeIn(status))
        with self.voiceover(text="Shift one by half a wavelength and they cancel completely.") as tracker:
            self.play(phase.animate.set_value(PI), Transform(status, caption("half a wave apart: destructive")),
                      run_time=3)
