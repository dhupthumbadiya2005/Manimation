from manim import *


class Math(Scene):
    def construct(self):
        eq = MathTex(r"\int_0^1 x^2 dx")
        self.play(Write(eq))
        self.wait()


if __name__ == "__main__":
    Math().render()


