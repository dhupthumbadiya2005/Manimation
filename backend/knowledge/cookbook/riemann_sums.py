"""
techniques: axes, plot_function, riemann_sum, integral, limit, rectangles_refine, caption_update
domain: math, calculus
summary: Approximate the area under a curve with rectangles that get thinner until they match the integral.
"""
from manim import *
from manim_kit import *


class RiemannSums(ThemedVoiceoverScene):
    def construct(self):
        title = title_card("Area as a limit of rectangles")
        axes, axes_group = labeled_axes([0, 3, 1], [0, 5, 1], zone_name="CENTER")
        graph = axes.plot(lambda x: 0.5 * x**2 + 0.5, x_range=[0, 3], color=T.highlight)

        def rects(dx):
            return axes.get_riemann_rectangles(graph, x_range=[0, 3], dx=dx, stroke_width=1,
                                               stroke_color=T.background, fill_opacity=0.7,
                                               color=[T.primary, T.secondary])

        bars = rects(0.75)
        label = caption("4 rectangles")
        with self.voiceover(text="To find the area under this curve, start with a few rectangles.") as tracker:
            self.play(Write(title), Create(axes_group), Create(graph))
            self.play(Create(bars), FadeIn(label))

        with self.voiceover(text="Make them thinner, and the leftover error shrinks. In the limit, the sum becomes the integral.") as tracker:
            for dx, n in [(0.375, 8), (0.15, 20), (0.05, 60)]:
                self.play(Transform(bars, rects(dx)), Transform(label, caption(f"{n} rectangles")), run_time=1.2)
