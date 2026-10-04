"""
techniques: data_structure, stack, push_pop, boxes, move_animation, caption_update
domain: computer_science, data_structures
summary: A stack of boxes: push drops a new box on top, pop lifts the top box away (last in, first out).
"""
import numpy as np
from manim import *
from manim_kit import *

BOX_W, BOX_H = 2.4, 0.7


def make_box(value):
    rect = Rectangle(width=BOX_W, height=BOX_H, stroke_color=T.primary, fill_color=T.primary, fill_opacity=0.25)
    return VGroup(rect, Text(str(value), font_size=32).move_to(rect))


class StackPushPop(ThemedVoiceoverScene):
    def construct(self):
        title = title_card("A stack: last in, first out")
        base_y = zone("CENTER").y0 + 0.2
        floor = Line(LEFT * 1.6, RIGHT * 1.6, color=T.muted).move_to([0, base_y, 0])
        status = caption("push 3, push 7, push 1")
        stack_boxes = []

        def slot(i):
            return np.array([0.0, base_y + BOX_H / 2 + i * (BOX_H + 0.08), 0.0])

        with self.voiceover(text="A stack only lets you add or remove items at the top.") as tracker:
            self.play(Write(title), Create(floor), FadeIn(status))

        with self.voiceover(text="Push places a new item on top of the pile.") as tracker:
            for value in [3, 7, 1]:
                box = make_box(value).move_to(slot(len(stack_boxes)) + UP * 2)
                self.play(FadeIn(box), run_time=0.3)
                self.play(box.animate.move_to(slot(len(stack_boxes))), run_time=0.6)
                stack_boxes.append(box)

        with self.voiceover(text="Pop takes the top item back off: the last one in is the first one out.") as tracker:
            self.play(Transform(status, caption("pop -> 1")))
            top = stack_boxes.pop()
            self.play(top.animate.shift(UP * 1.5).set_opacity(0), run_time=0.8)
            self.play(stack_boxes[-1][0].animate.set_fill(T.highlight, opacity=0.4), run_time=0.4)
