"""Planner agent: converts a topic into a list of scene descriptions for the coder."""
import json
import os

import openai
from dotenv import load_dotenv

load_dotenv()

_WORKED_EXAMPLE = {
    "topic": "how a stack works",
    "target_duration_seconds": 180,
    "scenes": [
        {
            "scene_id": 1,
            "title": "The Browser Back Button Mystery",
            "duration_hint": 22,
            "description": (
                "Show three rounded rectangles side by side at the top of the screen, "
                "labeled 'Home', 'Search', 'Article' — like browser tabs. "
                "Below them, centered at mid-screen, fade in the text: "
                "'How does Back know where you were?'\n\n"
                "Animation: tabs appear one-by-one with LaggedStart (total 2s). "
                "Question text writes in (1.5s). Hold 5s — narrator: 'You visit Home, "
                "then Search, then Article. You press Back — you land on Search. "
                "Press again — Home. The order is preserved perfectly. How?' "
                "Flash/Indicate the 'Article' tab (the most recent). Hold 3s. "
                "Fade all out (1s)."
            ),
        },
        {
            "scene_id": 2,
            "title": "The Stack: Last In, First Out",
            "duration_hint": 30,
            "description": (
                "Visualize a stack as a vertical column of colored rectangles, "
                "width=2.0, height=0.9 each, centered at x=0, growing upward "
                "from y=-2.5. Label each box inside with its value.\n\n"
                "Title 'Stack' appears at top-center (scale 1.4).\n\n"
                "Animation — Push three items:\n"
                "1. Box 'A' (BLUE) slides in from below and lands at y=-2.5 (0.8s).\n"
                "2. Box 'B' (GREEN) slides in and lands on top of A at y=-1.4 (0.8s).\n"
                "3. Box 'C' (YELLOW) slides in and lands on top of B at y=-0.3 (0.8s).\n"
                "Hold 4s — narrator: 'We added A first, then B, then C. "
                "C sits on top.'\n"
                "Indicate box C with a pulse (0.8s). "
                "Hold 5s — narrator: 'Only the TOP element is accessible right now. "
                "A and B are buried. This is a stack — a last-in, first-out structure.'\n"
                "Indicate box A (show it's buried). Hold 3s.\n"
                "Fade all out (1s)."
            ),
        },
        {
            "scene_id": 3,
            "title": "Push: Adding to the Stack",
            "duration_hint": 28,
            "description": (
                "Show an existing two-box stack (box '1' at bottom y=-1.5, "
                "box '2' on top at y=-0.3, both WHITE rectangles width=2, height=0.9).\n"
                "Title 'Push' at top-center in YELLOW.\n\n"
                "A new box labeled '3' (color BLUE) appears above the screen top "
                "and slides DOWN to land on top of box '2' at y=0.9 (1.5s, with a "
                "slight bounce or deceleration easing).\n\n"
                "Hold 3s — narrator: 'Push places a new element on top. "
                "The stack now has three items.'\n"
                "Indicate box '3' (the new top) with a yellow flash (0.8s).\n"
                "Hold 5s — narrator: 'Push is O(1) — it always adds to the same spot, "
                "the top, no matter how large the stack is.'\n"
                "Fade all out (1s)."
            ),
        },
        {
            "scene_id": 4,
            "title": "Pop: Removing from the Stack",
            "duration_hint": 28,
            "description": (
                "Show a three-box stack: box '1' (y=-1.5), '2' (y=-0.3), '3' (y=0.9), "
                "all WHITE rectangles width=2, height=0.9.\n"
                "Title 'Pop' at top-center in RED.\n\n"
                "Indicate box '3' (top). Hold 2s.\n"
                "Animate box '3' sliding UP and off the screen (1.2s, ease in). "
                "Simultaneously show a Text 'returns: 3' in GREEN appearing at top-right.\n\n"
                "Hold 4s — narrator: 'Pop removes the top element and returns it. "
                "The stack now has two items again.'\n"
                "Fade 'returns: 3' out. Hold 5s — narrator: 'Pop is also O(1) — "
                "always removes from the same spot.'\n"
                "Indicate box '2' (new top). Hold 3s. Fade all out (1s)."
            ),
        },
        {
            "scene_id": 5,
            "title": "LIFO Demonstrated",
            "duration_hint": 30,
            "description": (
                "Show two columns side by side.\n"
                "Left column header: 'Push order' (top-left, scale 0.9)\n"
                "Right column header: 'Pop order' (top-right, scale 0.9)\n\n"
                "Left side: animate boxes A (BLUE), B (GREEN), C (YELLOW) "
                "appearing bottom-to-top as a stack (0.7s each, LaggedStart).\n\n"
                "Hold 3s — narrator: 'We pushed A, then B, then C.'\n\n"
                "Right side: pop animation — C lifts off the left stack and "
                "lands in the right column at the bottom (move + slight arc, 1s). "
                "Then B (1s). Then A (1s). Each lands one above the other.\n\n"
                "Hold 4s — narrator: 'We get them back in reverse order: C, B, A. "
                "Last In, First Out — LIFO. The insertion order is exactly reversed.'\n\n"
                "Show a big label 'LIFO' centered between the columns (FadeIn, scale 1.5).\n"
                "Hold 4s. Fade all out (1s)."
            ),
        },
        {
            "scene_id": 6,
            "title": "The Call Stack in Programs",
            "duration_hint": 32,
            "description": (
                "Visualize a program's call stack as a vertical column of rectangles "
                "(width=3.5, height=0.85) labeled with function names, centered at x=0, "
                "growing upward from y=-2.8.\n"
                "Title 'The Call Stack' at top-center.\n\n"
                "On the left of each frame, show a small arrow ← pointing to code.\n\n"
                "Animation sequence:\n"
                "1. Frame 'main()' (WHITE) slides up from bottom, lands at y=-2.8 (0.8s).\n"
                "   Hold 3s — narrator: 'When a program starts, main() is pushed.'\n"
                "2. Frame 'foo()' (BLUE) slides up, lands at y=-1.7 (0.8s).\n"
                "   Hold 3s — narrator: 'main calls foo — new frame pushed on top.'\n"
                "3. Frame 'bar()' (GREEN) slides up, lands at y=-0.6 (0.8s).\n"
                "   Hold 3s — narrator: 'foo calls bar — another frame.'\n"
                "4. bar() frame slides off upward (0.8s). Text 'bar() returns' in GREY appears briefly.\n"
                "   Hold 2s — narrator: 'bar finishes — its frame is popped.'\n"
                "5. foo() frame slides off (0.8s). 'foo() returns' in GREY.\n"
                "   Hold 2s — narrator: 'foo finishes — frame popped.'\n"
                "6. main() frame slides off (0.8s). 'main() returns' in GREY.\n"
                "   Hold 3s — narrator: 'Program done — stack is empty.'\n"
                "Fade all out (1s)."
            ),
        },
    ],
}

_SYSTEM_PROMPT = """You are the director of a 3Blue1Brown-style educational animation. \
Your job is to plan a multi-scene video on the given topic.

Output ONLY a JSON object — no markdown, no prose, no code fences.

════════════════════════════════════════
OUTPUT FORMAT
════════════════════════════════════════
{
  "topic": "<topic string>",
  "target_duration_seconds": <total video length in seconds, 120–300>,
  "scenes": [
    {
      "scene_id": <int, starting at 1>,
      "title": "<short scene title>",
      "duration_hint": <expected seconds for this scene, 20–45>,
      "description": "<rich natural-language description — see below>"
    }
  ]
}

════════════════════════════════════════
HOW TO WRITE A SCENE DESCRIPTION
════════════════════════════════════════
The description is instructions to a Manim programmer. Be SPECIFIC — they cannot \
read your mind. Include:

1. VISUAL LAYOUT: what objects appear, where, what size, what color.
   - For arrays: list the exact values. e.g. "[2, 7, 1, 8, 3, 5]"
   - For trees/graphs: specify nodes and edges explicitly.
   - For text: write the exact string content.
   - Positions: use terms like "centered", "top-left quadrant", "below the array".

2. ANIMATION SEQUENCE: numbered steps, in order, with timing hints.
   - e.g. "1. Array boxes appear one-by-one LaggedStart (2s total)"
   - e.g. "2. Yellow arrow pointer appears above index 4 (0.5s)"
   - e.g. "3. Pointer moves from index 4 to index 7 — animate with .animate.next_to() (0.7s)"
   - e.g. "4. Boxes 0–4 fade to GREY to show they're eliminated (0.6s)"

3. NARRATOR MOMENTS: where to hold and for how long. Be generous — viewers need
   time to read and absorb. Key narration holds should be 5–10s, not 2–3s.
   - e.g. "Hold 6s — narrator: 'The pointer starts at the middle of the array...'"
   - e.g. "Hold 8s — narrator: 'Since 9 is less than 11, everything to the left is eliminated...'"

4. KEY VISUAL EFFECTS: what to flash/highlight/circumscribe at dramatic moments.
   - e.g. "Flash the found element in GREEN (0.8s)"
   - e.g. "Circumscribe the minimum value with a yellow rectangle"

5. SCENE CLOSE: fade out all elements (1s).

For ALGORITHM scenes: specify the data, describe each algorithmic step as an \
animation. The coder will implement the algorithm in Python and animate each step. \
Do NOT just say "show binary search" — describe WHAT CHANGES at each step.

════════════════════════════════════════
3B1B STYLE PRINCIPLES
════════════════════════════════════════
• Every scene delivers exactly ONE insight.
• Show the algorithm running, not just the result. Moving pointers, colors changing, \
  elements being eliminated — these are what make it educational.
• Use YELLOW for highlights, GREEN for success, RED for failure/elimination, \
  GREY for de-emphasized elements, BLUE/WHITE for neutral elements.
• Avoid long static holds — even during narration, something subtle should move \
  or be highlighted to maintain visual interest.
• No standalone title-card scene. Scene 1 should already show the core concept.
• Total 5–8 scenes. Each 20–45s. Total 120–300s.

════════════════════════════════════════
WORKED EXAMPLE — topic: "how a stack works"
Study how each description specifies exact values, positions, colors, and animation steps.
════════════════════════════════════════
""" + json.dumps(_WORKED_EXAMPLE, indent=2)


def generate(
    topic: str,
    previous_error: str | None = None,
    previous_plan: dict | None = None,
) -> dict:
    """Call GPT-4o to produce a scene plan. On retry, appends error + prior plan."""
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    user_msg = (
        f'Plan a 3Blue1Brown-style educational video on: "{topic}"\n\n'
        "Write 5–8 scenes. Each description must specify exact data values, "
        "positions, colors, and numbered animation steps so a Manim programmer "
        "can implement it without guessing. Output JSON only."
    )

    if previous_error and previous_plan:
        user_msg += (
            "\n\nYour previous plan failed validation:\n\n"
            + json.dumps(previous_plan, indent=2)
            + "\n\nError:\n"
            + previous_error
            + "\n\nOutput a fully corrected JSON object. JSON only."
        )

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=8192,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )

    raw = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        lines = raw.split("\n")[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines)

    return json.loads(raw)
