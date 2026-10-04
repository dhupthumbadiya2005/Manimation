"""
techniques: polygon, angle_arcs, sector, geometric_proof, parallel_line, transform_from_copy
domain: math, geometry
summary: Angles of a triangle copied along a parallel line through the apex to show they form a straight angle.
"""
import numpy as np
from manim import *
from manim_kit import *


def direction(p, q):
    d = q - p
    return np.arctan2(d[1], d[0])


def wedge(center, start, angle, color, radius=0.55):
    return Sector(radius=radius, start_angle=start, angle=angle, arc_center=center,
                  fill_color=color, fill_opacity=0.8, stroke_width=0)


class TriangleAngles(ThemedVoiceoverScene):
    def construct(self):
        A, B, C = np.array([-3.0, -1.8, 0]), np.array([3.0, -1.8, 0]), np.array([0.8, 1.6, 0])
        triangle = Polygon(A, B, C, color=T.text, stroke_width=3)

        ca, cb = direction(C, A), direction(C, B)
        angle_a = wedge(A, 0, direction(A, C), T.primary)
        angle_b = wedge(B, direction(B, C), PI - direction(B, C), T.secondary)
        angle_c = wedge(C, ca, cb - ca, T.highlight)
        a_copy = wedge(C, -PI, PI + ca, T.primary)      # alternate interior angle to A
        b_copy = wedge(C, cb, -cb, T.secondary)          # alternate interior angle to B
        parallel = DashedLine(C + LEFT * 4, C + RIGHT * 3.5, color=T.muted)

        figure = VGroup(triangle, angle_a, angle_b, angle_c, a_copy, b_copy, parallel)
        place_in_zone(figure, "CENTER")
        result = tex(r"\alpha + \beta + \gamma = 180^\circ", font_size=44)
        result[0][0].set_color(T.primary)
        result[0][2].set_color(T.secondary)
        result[0][4].set_color(T.highlight)
        place_in_zone(result, "BOTTOM")

        with self.voiceover(text="Mark the three angles of any triangle.") as tracker:
            self.play(Create(triangle))
            self.play(FadeIn(angle_a), FadeIn(angle_b), FadeIn(angle_c))
        with self.voiceover(text="Draw a line through the top, parallel to the base. Alternate angles copy alpha and beta up there.") as tracker:
            self.play(Create(parallel))
            self.play(TransformFromCopy(angle_a, a_copy), TransformFromCopy(angle_b, b_copy), run_time=1.5)
        with self.voiceover(text="Together they fill a straight line, so they add up to one hundred eighty degrees.") as tracker:
            self.play(Write(result))
