"""
techniques: number_plane, apply_matrix, basis_vectors, matrix_display, linear_algebra
domain: math
summary: Shear the whole grid with a matrix while the basis vectors ride along (3B1B linear-algebra look).
"""
from manim import *
from manim_kit import *


class LinearTransform(ThemedVoiceoverScene):
    def construct(self):
        plane = NumberPlane(
            background_line_style={"stroke_color": T.primary, "stroke_opacity": 0.5, "stroke_width": 2},
            axis_config={"stroke_color": T.text},
        )
        i_hat = Vector([1, 0], color=T.secondary)
        j_hat = Vector([0, 1], color=T.accent)

        matrix = Matrix([[1, 1], [0, 1]])
        matrix_box = VGroup(BackgroundRectangle(matrix, fill_opacity=0.85, buff=0.15), matrix)
        # Matrices are taller than the TOP band; pin to the corner at full size instead.
        matrix_box.to_corner(UL, buff=0.4)

        with self.voiceover(text="Here is the plane, with the basis vectors i hat and j hat.") as tracker:
            self.play(Create(plane), run_time=1.5)
            self.play(GrowArrow(i_hat), GrowArrow(j_hat))

        with self.voiceover(text="Applying this shear matrix drags every grid line along with them.") as tracker:
            self.play(FadeIn(matrix_box))
            self.play(ApplyMatrix([[1, 1], [0, 1]], VGroup(plane, i_hat, j_hat)), run_time=2.5)
