"""
techniques: axes, plot_function, area_under_curve, integral
domain: math
summary: Plot a function on labeled axes, shade the area under it, show the integral beside it.
"""
from manim import *
from manim_kit import *


class FunctionGraph(ThemedVoiceoverScene):
    def construct(self):
        title = title_card("Area under a curve")
        axes, axes_group = labeled_axes([0, 3, 1], [0, 9, 3], zone_name="LEFT")
        graph = axes.plot(lambda x: x**2, x_range=[0, 3], color=T.primary)
        label = tex("f(x) = x^2", font_size=36).set_color(T.primary)
        label.next_to(axes.c2p(3, 9), LEFT, buff=0.2)

        with self.voiceover(text="Here is the parabola f of x equals x squared.") as tracker:
            self.play(Write(title), Create(axes_group))
            self.play(Create(graph), Write(label))

        area = axes.get_area(graph, x_range=[0, 2], color=T.secondary, opacity=0.45)
        result = place_in_zone(tex(r"\int_0^2 x^2\,dx = \frac{8}{3}", font_size=48), "RIGHT")
        with self.voiceover(text="The shaded region, from zero to two, has area eight thirds.") as tracker:
            self.play(FadeIn(area))
            self.play(Write(result))
