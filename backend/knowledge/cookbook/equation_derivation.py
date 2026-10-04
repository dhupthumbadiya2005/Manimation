"""
techniques: equation_derivation, transform_matching_tex, algebra
domain: math
summary: Step-by-step algebra where matching terms glide between lines (3B1B derivation look).
"""
from manim import *
from manim_kit import *


class EquationDerivation(ThemedVoiceoverScene):
    def construct(self):
        title = title_card("Completing the square")
        with self.voiceover(text="Let's solve a quadratic by completing the square.") as tracker:
            self.play(Write(title), run_time=min(1.5, tracker.duration))

        with self.voiceover(text="Move the constant over, add nine to both sides, then factor.") as tracker:
            # {{ }} marks terms that should glide between steps instead of fading.
            final = equation_chain(self, [
                "{{x^2}} + {{6x}} - 7 = 0",
                "{{x^2}} + {{6x}} = 7",
                "{{x^2}} + {{6x}} + 9 = 16",
                "(x + 3)^2 = 16",
            ], run_time=1.0, pause=0.3)

        with self.voiceover(text="So x plus three is plus or minus four.") as tracker:
            box = highlight_box(final)
            self.play(Create(box))
