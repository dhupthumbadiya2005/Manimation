"""
techniques: vectors, vector_addition, forces, tip_to_tail, number_plane, labels_next_to
domain: physics, math, linear_algebra
summary: Two force vectors from the origin, moved tip to tail, and the resultant net force.
"""
import numpy as np
from manim import *
from manim_kit import *


class VectorAddition(ThemedVoiceoverScene):
    def construct(self):
        plane = NumberPlane(x_range=[-7, 7, 1], y_range=[-4, 4, 1],
                            background_line_style={"stroke_color": T.muted, "stroke_opacity": 0.25})
        origin = np.array([-3.0, -1.5, 0])
        f1, f2 = np.array([3.0, 1.0, 0]), np.array([1.0, 2.5, 0])

        v1 = Arrow(origin, origin + f1, buff=0, color=T.primary)
        v2 = Arrow(origin, origin + f2, buff=0, color=T.secondary)
        l1 = tex(r"\vec F_1").set_color(T.primary).next_to(v1.get_end(), DOWN, buff=0.15)
        l2 = tex(r"\vec F_2").set_color(T.secondary).next_to(v2.get_end(), LEFT, buff=0.15)

        v2_moved = Arrow(origin + f1, origin + f1 + f2, buff=0, color=T.secondary)
        net = Arrow(origin, origin + f1 + f2, buff=0, color=T.highlight, stroke_width=8)
        l_net = tex(r"\vec F_{\text{net}}").set_color(T.highlight).next_to(net.get_end(), UP, buff=0.15)
        equation = place_in_zone(tex(r"\vec F_{\text{net}} = \vec F_1 + \vec F_2", font_size=44), "TOP", align="right")

        with self.voiceover(text="Two forces pull on the same object.") as tracker:
            self.play(FadeIn(plane))
            self.play(GrowArrow(v1), GrowArrow(v2), Write(l1), Write(l2))
        with self.voiceover(text="Slide the second force so it starts where the first one ends: tip to tail.") as tracker:
            self.play(Transform(v2, v2_moved), l2.animate.next_to(v2_moved.get_center(), RIGHT, buff=0.15), run_time=1.5)
        with self.voiceover(text="The arrow from the start to the final tip is the net force.") as tracker:
            self.play(GrowArrow(net), Write(l_net))
            self.play(Write(equation))
