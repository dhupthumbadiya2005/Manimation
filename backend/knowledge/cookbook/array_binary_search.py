"""
techniques: array_cells, pointers, binary_search, algorithm_trace, dim_discarded, caption_update
domain: computer_science, algorithms
summary: Sorted array as boxed cells; lo/hi pointers below, mid above, discarded halves dim each step.
"""
from manim import *
from manim_kit import *


def make_cell(value, index):
    box = Square(side_length=0.9, stroke_color=T.muted, stroke_width=3)
    num = Text(str(value), font_size=32).move_to(box)
    idx = Text(str(index), font_size=20, color=T.muted).next_to(box, UP, buff=0.1)
    return VGroup(box, num, idx)


def pointer(cell, name, color, below=True):
    direction = DOWN if below else UP
    anchor = cell[0].get_bottom() if below else cell[2].get_top()
    arrow = Arrow(anchor + direction * 0.8, anchor + direction * 0.05, buff=0, color=color)
    label = Text(name, font_size=26, color=color).next_to(arrow, direction, buff=0.1)
    return VGroup(arrow, label)


class ArrayBinarySearch(ThemedVoiceoverScene):
    def construct(self):
        values = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]
        target = 23
        cells = VGroup(*[make_cell(v, i) for i, v in enumerate(values)]).arrange(RIGHT, buff=0)
        place_in_zone(cells, "CENTER")
        title = title_card(f"Binary search for {target}")

        lo, hi = 0, len(values) - 1
        lo_ptr = pointer(cells[lo], "lo", T.primary)
        hi_ptr = pointer(cells[hi], "hi", T.accent)
        status = caption("Compare the target with the middle element")

        with self.voiceover(text="Binary search keeps halving a sorted array.") as tracker:
            self.play(Write(title), Create(cells))
            self.play(FadeIn(lo_ptr), FadeIn(hi_ptr), FadeIn(status))

        mid_ptr = None
        with self.voiceover(text="Check the middle. If it is too small, drop the left half; too big, drop the right half.") as tracker:
            while lo <= hi:
                mid = (lo + hi) // 2
                new_mid = pointer(cells[mid], "mid", T.highlight, below=False)
                if mid_ptr is None:
                    mid_ptr = new_mid
                    self.play(FadeIn(mid_ptr), run_time=0.5)
                else:
                    self.play(Transform(mid_ptr, new_mid), run_time=0.5)

                if values[mid] == target:
                    self.play(cells[mid][0].animate.set_fill(T.secondary, opacity=0.5),
                              Transform(status, caption(f"Found {target} at index {mid}")))
                    break
                if values[mid] < target:
                    dropped, lo = range(lo, mid + 1), mid + 1
                    msg = f"{values[mid]} < {target}: search right"
                else:
                    dropped, hi = range(mid, hi + 1), mid - 1
                    msg = f"{values[mid]} > {target}: search left"
                self.play(
                    *[cells[i].animate.set_opacity(0.25) for i in dropped],
                    Transform(lo_ptr, pointer(cells[lo], "lo", T.primary)),
                    Transform(hi_ptr, pointer(cells[hi], "hi", T.accent)),
                    Transform(status, caption(msg)),
                    run_time=0.8,
                )
