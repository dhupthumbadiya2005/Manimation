"""
techniques: array_cells, sorting, bubble_sort, swap_animation, compare_highlight, algorithm_trace, caption_update
domain: computer_science, algorithms
summary: Bubble sort on boxed numbers: compare neighbours, swap them in place, and lock in the largest each pass.
"""
from manim import *
from manim_kit import *


def make_cell(value):
    box = Square(side_length=1.0, stroke_color=T.muted, stroke_width=3)
    return VGroup(box, Text(str(value), font_size=36).move_to(box))


class BubbleSort(ThemedVoiceoverScene):
    def construct(self):
        values = [5, 2, 4, 6, 1, 3]
        cells = [make_cell(v) for v in values]
        row = VGroup(*cells).arrange(RIGHT, buff=0.15)
        place_in_zone(row, "CENTER")
        slots = [c.get_center() for c in cells]   # fixed positions; cells move between them
        title = title_card("Bubble sort")
        status = caption("compare neighbours, swap if out of order")

        with self.voiceover(text="Bubble sort walks along the array, swapping neighbours that are out of order.") as tracker:
            self.play(Write(title), *[FadeIn(c) for c in cells], FadeIn(status))

        with self.voiceover(text="After each pass, the largest remaining number has bubbled to the end.") as tracker:
            n = len(values)
            for end in range(n - 1, 0, -1):
                for i in range(end):
                    a, b = cells[i], cells[i + 1]
                    self.play(a[0].animate.set_stroke(T.highlight), b[0].animate.set_stroke(T.highlight), run_time=0.2)
                    if values[i] > values[i + 1]:
                        self.play(a.animate.move_to(slots[i + 1]), b.animate.move_to(slots[i]), run_time=0.35)
                        values[i], values[i + 1] = values[i + 1], values[i]
                        cells[i], cells[i + 1] = b, a
                    self.play(cells[i][0].animate.set_stroke(T.muted), cells[i + 1][0].animate.set_stroke(T.muted), run_time=0.1)
                self.play(cells[end][0].animate.set_fill(T.secondary, opacity=0.4), run_time=0.2)
            self.play(cells[0][0].animate.set_fill(T.secondary, opacity=0.4),
                      Transform(status, caption("sorted")), run_time=0.4)
