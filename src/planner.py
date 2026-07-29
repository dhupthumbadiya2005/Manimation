"""Planner agent: converts a topic string into a validated scene JSON array."""
import json
import os

import openai
from dotenv import load_dotenv

from src.plan_schema import DEFAULT_TARGET_DURATION, GRID_CELLS, MAX_TOTAL_DURATION_SECONDS

load_dotenv()

# ---------------------------------------------------------------------------
# Worked example embedded in the system prompt (topic: "how a stack works")
# 8 scenes summing to 240 s. Beat durations in each scene sum within ±20% of
# that scene's duration_budget_seconds. Demonstrates Wait beats for hold time.
# ---------------------------------------------------------------------------
_WORKED_EXAMPLE = {
    "target_duration_seconds": 240,
    "scenes": [
        {
            "scene_id": 1,
            "goal": "Title card introducing the stack data structure",
            "duration_budget_seconds": 22,
            "mobjects": [
                {"id": "title", "type": "Text", "content": "Stack Data Structure", "cell": "top-center"},
                {"id": "subtitle", "type": "Text", "content": "Last In, First Out (LIFO)", "cell": "mid-center"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "title", "duration": 1.5, "note": "fade in title"},
                {"action": "FadeIn", "target": "subtitle", "duration": 1.5, "note": "fade in tagline"},
                {"action": "Wait", "target": "subtitle", "duration": 16.0, "note": "hold for reading"},
                {"action": "FadeOut", "target": "title", "duration": 1.0, "note": "clear"},
                {"action": "FadeOut", "target": "subtitle", "duration": 1.0, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 2,
        },
        {
            "scene_id": 2,
            "goal": "Define LIFO using a visual column of three labeled boxes showing insertion order",
            "duration_budget_seconds": 30,
            "mobjects": [
                {"id": "label", "type": "Text", "content": "LIFO: Last In, First Out", "cell": "top-center"},
                {"id": "box_a", "type": "Square", "content": "box labeled A at the bottom", "cell": "bot-center"},
                {"id": "box_b", "type": "Square", "content": "box labeled B in the middle", "cell": "mid-center"},
                {"id": "box_c", "type": "Square", "content": "box labeled C on top (last added)", "cell": "mid-center"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "label", "duration": 1.0, "note": "show rule"},
                {"action": "Create", "target": "box_a", "duration": 0.8, "note": "first element placed"},
                {"action": "Create", "target": "box_b", "duration": 0.8, "note": "second element"},
                {"action": "Create", "target": "box_c", "duration": 0.8, "note": "third element on top"},
                {"action": "Wait", "target": "box_c", "duration": 22.6, "note": "explain C arrived last and leaves first"},
                {"action": "FadeOut", "target": "label", "duration": 0.8, "note": "clear"},
                {"action": "FadeOut", "target": "box_c", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "box_b", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "box_a", "duration": 0.5, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 4,
        },
        {
            "scene_id": 3,
            "goal": "Animate the push operation: a new element arrives from above and lands on the stack top",
            "duration_budget_seconds": 30,
            "mobjects": [
                {"id": "op_label", "type": "Text", "content": "Push: add to top", "cell": "top-center"},
                {"id": "existing", "type": "VGroup", "content": "two stacked boxes already on the stack", "cell": "mid-center"},
                {"id": "new_box", "type": "Square", "content": "new box labeled 3 descending from above", "cell": "top-right"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "op_label", "duration": 1.0, "note": "show op name"},
                {"action": "Create", "target": "existing", "duration": 1.5, "note": "draw existing stack"},
                {"action": "Wait", "target": "existing", "duration": 4.0, "note": "pause before push"},
                {"action": "FadeIn", "target": "new_box", "duration": 1.5, "note": "new element appears"},
                {"action": "Wait", "target": "new_box", "duration": 18.0, "note": "explain push lands it on top"},
                {"action": "FadeOut", "target": "op_label", "duration": 1.0, "note": "clear"},
                {"action": "FadeOut", "target": "existing", "duration": 1.0, "note": "clear"},
                {"action": "FadeOut", "target": "new_box", "duration": 1.0, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 3,
        },
        {
            "scene_id": 4,
            "goal": "Animate the pop operation: the top element is removed and returned, revealing the element below",
            "duration_budget_seconds": 32,
            "mobjects": [
                {"id": "op_label", "type": "Text", "content": "Pop: remove from top", "cell": "top-center"},
                {"id": "stack_three", "type": "VGroup", "content": "three stacked boxes labeled 1, 2, 3 (3 on top)", "cell": "mid-center"},
                {"id": "popped", "type": "Square", "content": "box 3 moving upward to indicate removal", "cell": "top-center"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "op_label", "duration": 1.0, "note": "show op name"},
                {"action": "Create", "target": "stack_three", "duration": 1.5, "note": "draw full stack"},
                {"action": "Wait", "target": "stack_three", "duration": 4.0, "note": "pause before pop"},
                {"action": "FadeIn", "target": "popped", "duration": 1.5, "note": "top element rises"},
                {"action": "Wait", "target": "popped", "duration": 20.0, "note": "explain pop returns value and stack shrinks"},
                {"action": "FadeOut", "target": "popped", "duration": 1.0, "note": "clear"},
                {"action": "FadeOut", "target": "op_label", "duration": 1.0, "note": "clear"},
                {"action": "FadeOut", "target": "stack_three", "duration": 1.0, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 3,
        },
        {
            "scene_id": 5,
            "goal": "Show the call stack concept: function calls push frames, returns pop them",
            "duration_budget_seconds": 30,
            "mobjects": [
                {"id": "heading", "type": "Text", "content": "The Call Stack", "cell": "top-center"},
                {"id": "frame_main", "type": "Rectangle", "content": "stack frame labeled main()", "cell": "bot-center"},
                {"id": "frame_foo", "type": "Rectangle", "content": "stack frame labeled foo()", "cell": "mid-center"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "heading", "duration": 1.0, "note": "show heading"},
                {"action": "Create", "target": "frame_main", "duration": 1.0, "note": "main() is called first"},
                {"action": "Create", "target": "frame_foo", "duration": 1.0, "note": "foo() is called and pushed"},
                {"action": "Wait", "target": "frame_foo", "duration": 22.0, "note": "explain frames are pushed on call, popped on return"},
                {"action": "FadeOut", "target": "frame_foo", "duration": 1.0, "note": "foo returns"},
                {"action": "FadeOut", "target": "frame_main", "duration": 1.0, "note": "main returns"},
                {"action": "FadeOut", "target": "heading", "duration": 1.0, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 3,
        },
        {
            "scene_id": 6,
            "goal": "Illustrate stack overflow: pushing beyond capacity causes an error",
            "duration_budget_seconds": 28,
            "mobjects": [
                {"id": "heading", "type": "Text", "content": "Stack Overflow", "cell": "top-center"},
                {"id": "full_stack", "type": "VGroup", "content": "column of 5 boxes filling the frame height", "cell": "mid-center"},
                {"id": "overflow_msg", "type": "Text", "content": "Stack Overflow Error!", "cell": "bot-center"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "heading", "duration": 1.0, "note": "show heading"},
                {"action": "Create", "target": "full_stack", "duration": 2.0, "note": "draw a full stack"},
                {"action": "Wait", "target": "full_stack", "duration": 10.0, "note": "explain capacity is exhausted"},
                {"action": "FadeIn", "target": "overflow_msg", "duration": 1.0, "note": "error appears"},
                {"action": "Wait", "target": "overflow_msg", "duration": 10.0, "note": "explain consequence"},
                {"action": "FadeOut", "target": "overflow_msg", "duration": 1.0, "note": "clear"},
                {"action": "FadeOut", "target": "full_stack", "duration": 1.0, "note": "clear"},
                {"action": "FadeOut", "target": "heading", "duration": 1.0, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 3,
        },
        {
            "scene_id": 7,
            "goal": "Show two real-world uses of stacks: browser back button and undo in text editors",
            "duration_budget_seconds": 28,
            "mobjects": [
                {"id": "heading", "type": "Text", "content": "Real-World Uses", "cell": "top-center"},
                {"id": "use1", "type": "Text", "content": "Browser back button — pages are a stack", "cell": "mid-left"},
                {"id": "use2", "type": "Text", "content": "Text editor undo — actions are a stack", "cell": "mid-right"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "heading", "duration": 1.0, "note": "show heading"},
                {"action": "FadeIn", "target": "use1", "duration": 1.0, "note": "browser example"},
                {"action": "Wait", "target": "use1", "duration": 10.0, "note": "explain browser history"},
                {"action": "FadeIn", "target": "use2", "duration": 1.0, "note": "editor example"},
                {"action": "Wait", "target": "use2", "duration": 11.0, "note": "explain undo stack"},
                {"action": "FadeOut", "target": "use1", "duration": 1.0, "note": "clear"},
                {"action": "FadeOut", "target": "use2", "duration": 1.0, "note": "clear"},
                {"action": "FadeOut", "target": "heading", "duration": 1.0, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 3,
        },
        {
            "scene_id": 8,
            "goal": "Summary card listing the three key stack properties: LIFO, O(1) push/pop, fixed or dynamic capacity",
            "duration_budget_seconds": 20,
            "mobjects": [
                {"id": "heading", "type": "Text", "content": "Key Properties", "cell": "top-center"},
                {"id": "prop1", "type": "Text", "content": "LIFO — last element in is first out", "cell": "mid-left"},
                {"id": "prop2", "type": "Text", "content": "Push and Pop are O(1) operations", "cell": "mid-center"},
                {"id": "prop3", "type": "Text", "content": "Used in recursion, parsing, history", "cell": "mid-right"},
            ],
            "beats": [
                {"action": "FadeIn", "target": "heading", "duration": 1.0, "note": "show heading"},
                {"action": "FadeIn", "target": "prop1", "duration": 1.0, "note": "property 1"},
                {"action": "FadeIn", "target": "prop2", "duration": 1.0, "note": "property 2"},
                {"action": "FadeIn", "target": "prop3", "duration": 1.0, "note": "property 3"},
                {"action": "Wait", "target": "prop3", "duration": 11.0, "note": "hold summary"},
                {"action": "FadeOut", "target": "prop1", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "prop2", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "prop3", "duration": 0.5, "note": "clear"},
                {"action": "FadeOut", "target": "heading", "duration": 0.5, "note": "clear"},
            ],
            "max_simultaneous_mobjects": 4,
        },
    ],
}

# Total budget: 22+30+30+32+30+28+28+20 = 220s  (within ±15% of 240: [204, 276])
# Each scene's beat durations sum within ±20% of its duration_budget_seconds.

_SYSTEM_PROMPT = (
    "You are a director for short educational animations in the style of 3Blue1Brown. "
    "Given a topic, you produce a complete animation plan as a JSON object — nothing else. "
    "No prose, no markdown fences, no explanation. Output ONLY the JSON object.\n\n"
    "HARD RULES:\n"
    "1. target_duration_seconds defaults to "
    + str(int(DEFAULT_TARGET_DURATION))
    + "s. Never exceed the hard cap of "
    + str(MAX_TOTAL_DURATION_SECONDS)
    + "s.\n"
    "2. Divide the time budget across as many scenes as the topic naturally needs. "
    "Do not fix the scene count — let it fall out of the pacing. Each scene must cover "
    "exactly one idea, statable in one sentence.\n"
    "3. Each scene is fully self-contained: it starts from a blank frame and ends with "
    "every mobject faded out. Never assume anything is on screen from a previous scene.\n"
    "4. Every scene must include FadeOut beats for ALL mobjects it introduced, as its "
    "final beats.\n"
    "5. Assign each scene a duration_budget_seconds. The sum of all scene budgets must "
    "be within ±15% of target_duration_seconds.\n"
    "6. Each scene's beats[].duration values must sum within ±20% of that scene's "
    "duration_budget_seconds. Use 'Wait' beats (action='Wait', target=any on-screen "
    "mobject id) to fill hold time; they do not change what is on screen.\n"
    "7. At most max_simultaneous_mobjects mobjects may be on screen at any instant. "
    "Default this to 4 unless a scene needs fewer.\n"
    "8. All cell values must come from this exact list: "
    + str(GRID_CELLS)
    + ". Never use raw coordinates.\n"
    "9. Describe mobjects at the level of WHAT to show (e.g. 'row of 8 numbered boxes'), "
    "not HOW to animate it in code. Do not reference Manim class names or animation "
    "techniques — that is the coder's job.\n"
    "10. scene_id must start at 1 and increment by 1 with no gaps.\n"
    "11. Every beat's target must be the id of a mobject defined in that scene's "
    "mobjects list (Wait beats may reference any currently on-screen mobject id).\n"
    "12. Before finalising: sum all duration_budget_seconds, compare against "
    "target_duration_seconds, and adjust scene budgets if the sum is off by more "
    "than 15%.\n\n"
    "SCHEMA:\n"
    "{\n"
    '  "target_duration_seconds": <float>,\n'
    '  "scenes": [\n'
    "    {\n"
    '      "scene_id": <int, starts at 1>,\n'
    '      "goal": "<one sentence>",\n'
    '      "duration_budget_seconds": <float>,\n'
    '      "mobjects": [\n'
    '        {"id": "<str>", "type": "<str>", "content": "<description>", "cell": "<grid cell>"}\n'
    "      ],\n"
    '      "beats": [\n'
    '        {"action": "<FadeIn|Create|Write|FadeOut|Wait|…>", "target": "<mobject id>", '
    '"duration": <float seconds>, "note": "<brief>"}\n'
    "      ],\n"
    '      "max_simultaneous_mobjects": <int>\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "WORKED EXAMPLE (topic: 'how a stack works') — study the pacing and beat structure:\n"
    + json.dumps(_WORKED_EXAMPLE, indent=2)
)


def generate(
    topic: str,
    previous_error: str | None = None,
    previous_plan: dict | None = None,
) -> dict:
    """
    Call GPT-4o to produce a plan dict for the given topic.
    On retry, appends the validation error and the previous plan to the prompt.
    """
    client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    user_msg = f'Produce the animation plan for this topic: "{topic}"'

    if previous_error and previous_plan:
        user_msg += (
            "\n\nYour previous plan FAILED validation. Here it is:\n\n"
            + json.dumps(previous_plan, indent=2)
            + "\n\nValidation error:\n"
            + previous_error
            + "\n\nOutput a fully corrected JSON object from scratch. "
            "Fix every issue mentioned. Do not include any prose — JSON only."
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

    # Strip markdown fences if the model added them
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines)

    return json.loads(raw)
