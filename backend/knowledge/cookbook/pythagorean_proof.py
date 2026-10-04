"""
techniques: polygon, geometric_proof, labels_at_centers, equation_parts_coloring
domain: math
summary: Right triangle with squares on each side; areas color-linked to the terms of a^2 + b^2 = c^2.
"""
import numpy as np
from manim import *
from manim_kit import *


def p(x, y):
    return np.array([x, y, 0.0])


class PythagoreanProof(ThemedVoiceoverScene):
    def construct(self):
        a, b = 1.2, 1.6  # legs; hypotenuse c = 2
        O, P, Q = p(0, 0), p(b, 0), p(0, a)
        triangle = Polygon(O, P, Q, color=T.text, fill_color=T.muted, fill_opacity=0.3)
        sq_b = Polygon(O, P, P + p(0, -b), O + p(0, -b), color=T.secondary, fill_opacity=0.35)
        sq_a = Polygon(O, Q, Q + p(-a, 0), O + p(-a, 0), color=T.primary, fill_opacity=0.35)
        sq_c = Polygon(P, Q, Q + p(a, b), P + p(a, b), color=T.highlight, fill_opacity=0.35)

        lab_a = tex("a^2").set_color(T.primary).move_to(sq_a)
        lab_b = tex("b^2").set_color(T.secondary).move_to(sq_b)
        lab_c = tex("c^2").set_color(T.highlight).move_to(sq_c)

        figure = VGroup(triangle, sq_a, sq_b, sq_c, lab_a, lab_b, lab_c)
        place_in_zone(figure, "LEFT")

        # Separate args -> separate parts, so each term can be colored by index.
        equation = tex("a^2", "+", "b^2", "=", "c^2", font_size=60)
        equation[0].set_color(T.primary)
        equation[2].set_color(T.secondary)
        equation[4].set_color(T.highlight)
        place_in_zone(equation, "RIGHT")

        with self.voiceover(text="Take a right triangle and build a square on each side.") as tracker:
            self.play(Create(triangle))
            self.play(*[DrawBorderThenFill(s) for s in (sq_a, sq_b, sq_c)])

        with self.voiceover(text="The two smaller areas always add up to the largest one.") as tracker:
            self.play(Write(lab_a), Write(lab_b), Write(lab_c))
            self.play(
                TransformFromCopy(lab_a, equation[0]),
                TransformFromCopy(lab_b, equation[2]),
                TransformFromCopy(lab_c, equation[4]),
                FadeIn(equation[1]), FadeIn(equation[3]),
            )
