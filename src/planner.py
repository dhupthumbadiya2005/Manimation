"""Stage 1 — Scene Planning Engine.

Takes a user topic / algorithm description and produces a structured Markdown
scene plan that the code generator can translate into Manim Python.
"""
from src.llm_client import complete

_SYSTEM_PROMPT = """You are an expert educational content designer specializing in mathematical and computer science visualizations.
When presented with any research paper, algorithm, or mathematical concept, transform it into a structured Markdown scene plan following this layout:

### 1. Topic: [Main Subject Name]

### 2. Conceptual Progression & Key Points:
- Break down the explanation into 3-5 incremental steps (from intuition/analogy to mathematical/code rigor).
- Include precise LaTeX formulas (e.g., $f(x) = \\sigma(W \\cdot x + b)$ or $O(n \\log n)$).
- Ensure each step focuses on reducing cognitive load.

### 3. Visual Elements & Layout Mapping:
- List specific Mobjects to use (e.g., MathTex, Graphs, Arrays, Tree Nodes, Flow Arrows).
- Map spatial arrangements (e.g., Pseudocode on left, Visual tree/array execution on right).
- Specify animation transitions (e.g., Highlight active line in yellow, morph vector to matrix).

### 4. Color & Aesthetic Palette:
- Dark background (default black) or crisp white background.
- High-contrast highlight colors (e.g., Yellow for active computation, Blue/Red for data flows).

════════════════════════════════════════
ADDITIONAL ANIMATION DETAIL REQUIREMENTS
════════════════════════════════════════
Under Section 3, be VERY specific so a Manim programmer can implement without guessing:
  • Array/list: state exact values, e.g. [4, 2, 8, 1, 6, 3].
  • Pointers: describe where they start, how they move, what they represent.
  • Each step: numbered sequence with timing hints (e.g., "3. Pointer moves left → 0.6s").
  • Narration holds: "Hold 5s — narrator: 'The middle element divides...'"
  • Scene close: always "Fade all out (1s)" at the end.
  • Total video: aim for 120–240 seconds across all scenes.

COLOR GUIDE: YELLOW = active/highlighted element, GREEN = success/found,
RED = failure/eliminated, GREY = de-emphasized, BLUE = neutral data.

Output ONLY the Markdown plan — no preamble, no code fences, no extra prose.
"""


def generate(
    topic: str,
    previous_error: str | None = None,
    previous_plan: str | None = None,
) -> str:
    """Return a Markdown scene plan for the given topic."""
    user_msg = (
        f"Create a detailed Manim animation scene plan for: \"{topic}\"\n\n"
        "Include exact data values, animation sequences, timing, and visual layout "
        "so a Manim programmer can implement it directly. Output Markdown only."
    )

    if previous_error and previous_plan:
        user_msg += (
            "\n\nYour previous plan produced code that failed with this error:\n\n"
            f"{previous_error}\n\n"
            "Previous plan for reference:\n\n"
            f"{previous_plan}\n\n"
            "Produce a revised Markdown plan that avoids the error above. "
            "Simplify the visuals if needed — correctness over complexity."
        )

    return complete(_SYSTEM_PROMPT, user_msg, max_tokens=4096)
