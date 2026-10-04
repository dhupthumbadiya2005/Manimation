"""
techniques: axes, plot_function, multiple_graphs, legend, big_o, complexity, growth_comparison
domain: computer_science, algorithms
summary: Plot n, n log n and n^2 on the same axes with a color-matched legend to compare growth rates.
"""
import numpy as np
from manim import *
from manim_kit import *


class ComplexityGrowth(ThemedVoiceoverScene):
    def construct(self):
        axes, axes_group = labeled_axes([0, 10, 2], [0, 100, 20], "n", r"\text{steps}", zone_name="LEFT")
        curves = [
            (lambda n: n, T.secondary, "O(n)"),
            (lambda n: n * np.log2(max(n, 1)), T.primary, r"O(n \log n)"),
            (lambda n: n**2, T.accent, "O(n^2)"),
        ]
        graphs = [axes.plot(f, x_range=[0.01, 10], color=c, stroke_width=4) for f, c, _ in curves]
        legend = VGroup(*[
            VGroup(Line(ORIGIN, RIGHT * 0.6, color=c, stroke_width=6), tex(label, font_size=40))
            .arrange(RIGHT, buff=0.25)
            for _, c, label in curves
        ]).arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        place_in_zone(legend, "RIGHT")

        with self.voiceover(text="How does the work grow as the input gets bigger?") as tracker:
            self.play(Create(axes_group))
        with self.voiceover(text="Linear time grows steadily, n log n a little faster, and n squared quickly leaves both behind.") as tracker:
            for graph, entry in zip(graphs, legend):
                self.play(Create(graph), FadeIn(entry), run_time=1.2)
