"""Planner agent: converts a topic string into a validated scene JSON array."""
import json
import os

import openai
from dotenv import load_dotenv

from src.plan_schema import DEFAULT_TARGET_DURATION, GRID_CELLS, MAX_TOTAL_DURATION_SECONDS

load_dotenv()

# ---------------------------------------------------------------------------
# 3B1B-style worked example — topic: "how a stack works"
#
# Pacing model:
#   • Animation beats (FadeIn/Create/Indicate): 0.8–1.5s — snappy, visual change
#   • Narrator Wait beats: 5–12s — narrator explains while visual is held
#   • Transition Wait beats: 1–3s — brief pause at a state change
#   • FadeOut beats: 0.5–1.0s each
#
# Each scene's beat durations sum within ±20% of duration_budget_seconds.
# Total budget 212s is within ±15% of target 240s: [204, 276].
# ---------------------------------------------------------------------------
_WORKED_EXAMPLE = {
    "target_duration_seconds": 240,
    "scenes": [
        {
            "scene_id": 1,
            "goal": "Hook: a growing browser history raises the question of how the Back button knows where you were",
            "duration_budget_seconds": 24,
            "mobjects": [
                {"id": "tab1", "type": "Rectangle", "content": "browser tab labeled 'Home'", "cell": "top-left"},
                {"id": "tab2", "type": "Rectangle", "content": "browser tab labeled 'Search'", "cell": "top-center"},
                {"id": "tab3", "type": "Rectangle", "content": "browser tab labeled 'Article'", "cell": "top-right"},
                {"id": "question", "type": "Text", "content": "How does Back know where you were?", "cell": "mid-center"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "tab1", "duration": 0.8, "note": "first page visited"},
                {"action": "FadeIn", "target": "tab2", "duration": 0.8, "note": "second page"},
                {"action": "FadeIn", "target": "tab3", "duration": 0.8, "note": "third page — history growing"},
                {"action": "Wait", "target": "tab3", "duration": 10.0, "note": "narrator: you have visited three pages in order"},
                {"action": "Indicate", "target": "tab3", "duration": 1.0, "note": "highlight the most recent tab"},
                {"action": "Wait", "target": "tab3", "duration": 6.0, "note": "narrator: pressing Back returns to the previous page — how?"},
                {"action": "FadeIn", "target": "question", "duration": 1.5, "note": "the central question appears"},
                {"action": "Wait", "target": "question", "duration": 2.0, "note": "brief pause"},
                {"action": "FadeOut", "target": "tab1", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "tab2", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "tab3", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "question", "duration": 1.0, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 4,
        },
        {
            "scene_id": 2,
            "goal": "Introduce the stack: a vertical column of elements where only the top is accessible",
            "duration_budget_seconds": 28,
            "mobjects": [
                {"id": "label", "type": "Text", "content": "Stack", "cell": "top-center"},
                {"id": "box_a", "type": "Square", "content": "box labeled A at bottom of column", "cell": "bot-center"},
                {"id": "box_b", "type": "Square", "content": "box labeled B stacked above A", "cell": "mid-center"},
                {"id": "box_c", "type": "Square", "content": "box labeled C on top (last added)", "cell": "mid-center"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "label", "duration": 1.0, "note": "title"},
                {"action": "Create", "target": "box_a", "duration": 0.8, "note": "A placed first"},
                {"action": "Create", "target": "box_b", "duration": 0.8, "note": "B stacks on top of A"},
                {"action": "Create", "target": "box_c", "duration": 0.8, "note": "C stacks on top of B"},
                {"action": "Wait", "target": "box_c", "duration": 9.0, "note": "narrator: we added A first then B then C — C sits on top"},
                {"action": "Indicate", "target": "box_c", "duration": 1.0, "note": "highlight the top"},
                {"action": "Wait", "target": "box_c", "duration": 8.0, "note": "narrator: only the top element is accessible; A and B are buried underneath"},
                {"action": "Indicate", "target": "box_a", "duration": 1.0, "note": "show A is buried"},
                {"action": "Wait", "target": "box_a", "duration": 2.0, "note": "brief pause"},
                {"action": "FadeOut", "target": "label", "duration": 0.8, "note": "clear"},
                {"action": "FadeOut", "target": "box_c", "duration": 0.5, "note": "clear top first"},
                {"action": "FadeOut", "target": "box_b", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "box_a", "duration": 0.8, "note": "clear bottom"},
            ],
            "max_simultaneous_mobjects": 4,
        },
        {
            "scene_id": 3,
            "goal": "Animate the Push operation: a new element descends from above and lands on the stack top",
            "duration_budget_seconds": 28,
            "mobjects": [
                {"id": "op_label", "type": "Text", "content": "Push", "cell": "top-center"},
                {"id": "stack_base", "type": "VGroup", "content": "two stacked boxes labeled 1 and 2", "cell": "mid-center"},
                {"id": "incoming", "type": "Square", "content": "new box labeled 3 above the stack", "cell": "top-right"},
                {"id": "arrow", "type": "Arrow", "content": "downward arrow pointing from box 3 toward the stack top", "cell": "mid-right"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "op_label", "duration": 1.0, "note": "operation name"},
                {"action": "Create", "target": "stack_base", "duration": 1.5, "note": "existing two-element stack"},
                {"action": "Wait", "target": "stack_base", "duration": 5.0, "note": "narrator: here is our stack with two elements already in it"},
                {"action": "FadeIn", "target": "incoming", "duration": 1.0, "note": "new element appears above"},
                {"action": "FadeIn", "target": "arrow", "duration": 0.8, "note": "arrow shows it is heading to the top"},
                {"action": "Wait", "target": "incoming", "duration": 12.0, "note": "narrator: push places the new element on top — the stack now has three elements"},
                {"action": "Indicate", "target": "incoming", "duration": 1.0, "note": "pulse the new top element"},
                {"action": "Wait", "target": "incoming", "duration": 2.0, "note": "brief pause"},
                {"action": "FadeOut", "target": "arrow", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "op_label", "duration": 0.8, "note": "clear"},
                {"action": "FadeOut", "target": "incoming", "duration": 0.8, "note": "clear"},
                {"action": "FadeOut", "target": "stack_base", "duration": 1.0, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 4,
        },
        {
            "scene_id": 4,
            "goal": "Animate the Pop operation: the top element lifts off and is returned, revealing the element below",
            "duration_budget_seconds": 28,
            "mobjects": [
                {"id": "op_label", "type": "Text", "content": "Pop", "cell": "top-center"},
                {"id": "stack_three", "type": "VGroup", "content": "three stacked boxes labeled 1 2 3 with 3 on top", "cell": "mid-center"},
                {"id": "popped", "type": "Square", "content": "box 3 floating upward away from the stack", "cell": "top-center"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "op_label", "duration": 1.0, "note": "operation name"},
                {"action": "Create", "target": "stack_three", "duration": 1.5, "note": "three-element stack"},
                {"action": "Wait", "target": "stack_three", "duration": 5.0, "note": "narrator: we have three elements — we are going to pop"},
                {"action": "Indicate", "target": "stack_three", "duration": 1.0, "note": "highlight the top"},
                {"action": "Wait", "target": "stack_three", "duration": 3.0, "note": "brief pause before the pop"},
                {"action": "FadeIn", "target": "popped", "duration": 0.8, "note": "top element rises"},
                {"action": "Wait", "target": "popped", "duration": 10.0, "note": "narrator: pop removes the top element and returns its value — the stack now has two elements"},
                {"action": "Indicate", "target": "popped", "duration": 1.0, "note": "the returned value"},
                {"action": "Wait", "target": "popped", "duration": 2.0, "note": "brief pause"},
                {"action": "FadeOut", "target": "popped", "duration": 0.8, "note": "clear"},
                {"action": "FadeOut", "target": "op_label", "duration": 0.8, "note": "clear"},
                {"action": "FadeOut", "target": "stack_three", "duration": 1.0, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 3,
        },
        {
            "scene_id": 5,
            "goal": "Demonstrate LIFO: push A B C then pop returns C B A — the reversal is the core insight",
            "duration_budget_seconds": 26,
            "mobjects": [
                {"id": "push_label", "type": "Text", "content": "Push A, B, C  →  Pop returns C, B, A", "cell": "top-center"},
                {"id": "box_a", "type": "Square", "content": "box labeled A at bottom", "cell": "bot-center"},
                {"id": "box_b", "type": "Square", "content": "box labeled B above A", "cell": "mid-center"},
                {"id": "box_c", "type": "Square", "content": "box labeled C on top", "cell": "mid-center"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "push_label", "duration": 1.0, "note": "caption appears"},
                {"action": "Create", "target": "box_a", "duration": 0.8, "note": "push A"},
                {"action": "Create", "target": "box_b", "duration": 0.8, "note": "push B"},
                {"action": "Create", "target": "box_c", "duration": 0.8, "note": "push C — on top"},
                {"action": "Wait", "target": "box_c", "duration": 5.0, "note": "narrator: we pushed A then B then C"},
                {"action": "FadeOut", "target": "box_c", "duration": 0.8, "note": "pop C — first out"},
                {"action": "Wait", "target": "box_b", "duration": 2.0, "note": "C came off first"},
                {"action": "FadeOut", "target": "box_b", "duration": 0.8, "note": "pop B"},
                {"action": "Wait", "target": "box_a", "duration": 2.0, "note": "B came off second"},
                {"action": "FadeOut", "target": "box_a", "duration": 0.8, "note": "pop A — last out"},
                {"action": "Wait", "target": "push_label", "duration": 8.0, "note": "narrator: last in first out — LIFO — the insertion order is exactly reversed on removal"},
                {"action": "FadeOut", "target": "push_label", "duration": 1.0, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 4,
        },
        {
            "scene_id": 6,
            "goal": "Show the call stack: each function call pushes a frame, each return pops one",
            "duration_budget_seconds": 28,
            "mobjects": [
                {"id": "heading", "type": "Text", "content": "The Call Stack", "cell": "top-center"},
                {"id": "frame_main", "type": "Rectangle", "content": "stack frame labeled main()", "cell": "bot-center"},
                {"id": "frame_foo", "type": "Rectangle", "content": "stack frame labeled foo()", "cell": "mid-center"},
                {"id": "frame_bar", "type": "Rectangle", "content": "stack frame labeled bar()", "cell": "mid-center"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "heading", "duration": 1.0, "note": "heading"},
                {"action": "Create", "target": "frame_main", "duration": 1.0, "note": "main() starts: frame pushed"},
                {"action": "Wait", "target": "frame_main", "duration": 4.0, "note": "narrator: main is the entry point — its frame sits at the bottom"},
                {"action": "Create", "target": "frame_foo", "duration": 1.0, "note": "main calls foo(): frame pushed"},
                {"action": "Wait", "target": "frame_foo", "duration": 4.0, "note": "narrator: every function call pushes a new frame on top"},
                {"action": "Create", "target": "frame_bar", "duration": 1.0, "note": "foo calls bar(): frame pushed"},
                {"action": "Wait", "target": "frame_bar", "duration": 3.0, "note": "three frames deep"},
                {"action": "FadeOut", "target": "frame_bar", "duration": 0.8, "note": "bar() returns — frame popped"},
                {"action": "Wait", "target": "frame_foo", "duration": 3.0, "note": "control returns to foo"},
                {"action": "FadeOut", "target": "frame_foo", "duration": 0.8, "note": "foo() returns — frame popped"},
                {"action": "Wait", "target": "frame_main", "duration": 3.0, "note": "control returns to main"},
                {"action": "FadeOut", "target": "frame_main", "duration": 0.8, "note": "main returns — stack empty"},
                {"action": "FadeOut", "target": "heading", "duration": 1.0, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 4,
        },
        {
            "scene_id": 7,
            "goal": "Stack overflow: unbounded recursion fills the stack until the program crashes",
            "duration_budget_seconds": 26,
            "mobjects": [
                {"id": "heading", "type": "Text", "content": "Stack Overflow", "cell": "top-center"},
                {"id": "frame1", "type": "Rectangle", "content": "recursive frame 1 at bottom", "cell": "bot-center"},
                {"id": "frame2", "type": "Rectangle", "content": "recursive frame 2", "cell": "bot-center"},
                {"id": "frame3", "type": "Rectangle", "content": "recursive frame 3 near top", "cell": "mid-center"},
                {"id": "error_msg", "type": "Text", "content": "StackOverflowError", "cell": "mid-center"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "heading", "duration": 1.0, "note": "heading"},
                {"action": "Create", "target": "frame1", "duration": 0.8, "note": "first recursive call"},
                {"action": "Create", "target": "frame2", "duration": 0.8, "note": "second — recursion continues"},
                {"action": "Create", "target": "frame3", "duration": 0.8, "note": "third — stack keeps growing"},
                {"action": "Wait", "target": "frame3", "duration": 4.0, "note": "narrator: with unbounded recursion frames pile up"},
                {"action": "Indicate", "target": "frame3", "duration": 1.0, "note": "highlight the growing top"},
                {"action": "Wait", "target": "frame3", "duration": 6.0, "note": "narrator: the stack has a finite size — eventually it is full"},
                {"action": "FadeOut", "target": "heading", "duration": 0.8, "note": "clear heading to make room"},
                {"action": "FadeIn", "target": "error_msg", "duration": 1.0, "note": "crash — error appears where heading was"},
                {"action": "Wait", "target": "error_msg", "duration": 5.0, "note": "narrator: the next push has nowhere to go — StackOverflowError"},
                {"action": "FadeOut", "target": "error_msg", "duration": 0.8, "note": "clear"},
                {"action": "FadeOut", "target": "frame3", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "frame2", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "frame1", "duration": 0.5, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 4,
        },
        {
            "scene_id": 8,
            "goal": "Three real-world uses: browser back button, Ctrl+Z undo, and parentheses matching",
            "duration_budget_seconds": 24,
            "mobjects": [
                {"id": "heading", "type": "Text", "content": "Stacks are Everywhere", "cell": "top-center"},
                {"id": "use1", "type": "Text", "content": "Browser back button", "cell": "mid-left"},
                {"id": "use2", "type": "Text", "content": "Ctrl+Z undo", "cell": "mid-center"},
                {"id": "use3", "type": "Text", "content": "Parentheses matching", "cell": "mid-right"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "heading", "duration": 1.0, "note": "heading"},
                {"action": "FadeIn", "target": "use1", "duration": 1.0, "note": "use 1"},
                {"action": "Wait", "target": "use1", "duration": 5.0, "note": "narrator: every page you visit is pushed — Back pops it"},
                {"action": "FadeIn", "target": "use2", "duration": 1.0, "note": "use 2"},
                {"action": "Wait", "target": "use2", "duration": 5.0, "note": "narrator: every action is pushed — Ctrl+Z pops the last one"},
                {"action": "FadeIn", "target": "use3", "duration": 1.0, "note": "use 3"},
                {"action": "Wait", "target": "use3", "duration": 6.0, "note": "narrator: open brackets are pushed — a close bracket pops and checks for a match"},
                {"action": "FadeOut", "target": "use1", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "use2", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "use3", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "heading", "duration": 1.0, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 4,
        },
    ],
}

# Budget totals: 24+28+28+28+26+28+26+24 = 212s  ±15% of 240s target: [204,276] ✓
# Beat sums per scene (verified against ±20% of budget):
#   S1 25.4/24=105.8% ✓  S2 27.0/28=96.4% ✓  S3 27.4/28=97.9% ✓  S4 27.9/28=99.6% ✓
#   S5 24.0/26=92.3% ✓  S6 25.4/28=90.7% ✓  S7 23.5/26=90.4% ✓  S8 22.5/24=93.8% ✓

_SYSTEM_PROMPT = (
    "You are the director of a 3Blue1Brown-style educational video. "
    "Produce a JSON animation plan — nothing else. Output ONLY the JSON object. "
    "No prose, no markdown, no code fences.\n\n"

    "══════════════════════════════════════════\n"
    "3BLUE1BROWN DIRECTING PRINCIPLES\n"
    "══════════════════════════════════════════\n"
    "• Scenes are SHOTS in one continuous video — each flows naturally into the next.\n"
    "• Every scene delivers exactly one insight, statable in one sentence.\n"
    "• Animation beats (FadeIn/Create/Indicate): 0.8–1.5s — snappy visual changes.\n"
    "• Narrator Wait beats: 5–12s — narrator explains while the visual is held static.\n"
    "• Transition Wait beats: 1–3s — brief pause at a visual state change.\n"
    "• The LAST beats of every scene must FadeOut ALL mobjects introduced in that scene.\n"
    "• Scenes 20–35s each, 8–14 beats per scene.\n"
    "• No standalone title-card scenes. Start with content immediately.\n"
    "• Build complexity scene by scene — each scene adds one new idea on top of the last.\n\n"

    "══════════════════════════════════════════\n"
    "HARD RULES\n"
    "══════════════════════════════════════════\n"
    "1. target_duration_seconds defaults to "
    + str(int(DEFAULT_TARGET_DURATION))
    + "s. Hard cap: "
    + str(MAX_TOTAL_DURATION_SECONDS)
    + "s.\n"
    "2. Sum of scene duration_budget_seconds must be within ±15% of target_duration_seconds.\n"
    "3. Each scene's beats[].duration values must sum within ±20% of that scene's budget.\n"
    "4. All cell values must be from: " + str(GRID_CELLS) + "\n"
    "5. Every non-Wait beat's target must be a mobject id defined in that scene.\n"
    "6. At most max_simultaneous_mobjects mobjects on screen at once (track this yourself).\n"
    "7. scene_id starts at 1 and increments by 1 with no gaps.\n"
    "8. Describe mobjects as WHAT to show, not how to code them.\n"
    "9. Before returning: sum all duration_budget_seconds; if off by >15%, redistribute.\n\n"

    "══════════════════════════════════════════\n"
    "SCHEMA\n"
    "══════════════════════════════════════════\n"
    '{\n'
    '  "target_duration_seconds": <float>,\n'
    '  "scenes": [{\n'
    '    "scene_id": <int>,\n'
    '    "goal": "<one sentence — what insight does this scene deliver?>",\n'
    '    "duration_budget_seconds": <float>,\n'
    '    "mobjects": [{"id":"<str>","type":"<str>","content":"<description>","cell":"<grid cell>"}],\n'
    '    "beats": [{"action":"<FadeIn|Create|Write|Indicate|Circumscribe|FadeOut|Wait|…>",\n'
    '               "target":"<mobject id>","duration":<float>,"note":"<narrator note>"}],\n'
    '    "max_simultaneous_mobjects": <int>\n'
    '  }]\n'
    '}\n\n'

    "══════════════════════════════════════════\n"
    "WORKED EXAMPLE (topic: 'how a stack works')\n"
    "Study beat density, narrator Wait lengths, and how beat sums match budgets:\n"
    "══════════════════════════════════════════\n"
    + json.dumps(_WORKED_EXAMPLE, indent=2)
)


def generate(
    topic: str,
    previous_error: str | None = None,
    previous_plan: dict | None = None,
) -> dict:
    """Call GPT-4o to produce a plan dict. On retry, appends error + prior plan."""
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    user_msg = (
        f'Produce the animation plan for this topic: "{topic}"\n\n'
        "Remember 3B1B style: quick animation beats (0.8–1.5s), narrator Wait beats (5–12s), "
        "scenes 20–35s each, every scene flows into the next as one continuous video."
    )

    if previous_error and previous_plan:
        user_msg += (
            "\n\nYour previous plan FAILED validation:\n\n"
            + json.dumps(previous_plan, indent=2)
            + "\n\nValidation error:\n"
            + previous_error
            + "\n\nOutput a fully corrected JSON object from scratch. JSON only."
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
