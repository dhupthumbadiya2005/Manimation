"""
techniques: graph, tree_layout, bfs, algorithm_trace, node_highlight, caption_update
domain: computer_science, algorithms
summary: Breadth-first search on a tree: nodes light up level by level while a queue caption updates.
"""
from collections import deque

from manim import *
from manim_kit import *


class GraphBFS(ThemedVoiceoverScene):
    def construct(self):
        vertices = list(range(1, 8))
        edges = [(1, 2), (1, 3), (2, 4), (2, 5), (3, 6), (3, 7)]
        # Explicit positions keep small trees ordered left-to-right
        # (networkx's "tree" layout may mirror children).
        layout = {1: [0, 1.5, 0], 2: [-2, 0, 0], 3: [2, 0, 0],
                  4: [-3, -1.5, 0], 5: [-1, -1.5, 0], 6: [1, -1.5, 0], 7: [3, -1.5, 0]}
        g = Graph(
            vertices, edges, labels=True, label_fill_color=T.background, layout=layout,
            vertex_config={"radius": 0.3, "fill_color": T.text},
            edge_config={"stroke_color": T.muted, "stroke_width": 3},
        )
        place_in_zone(g, "CENTER")
        title = title_card("Breadth-first search")
        queue_text = caption("queue: [1]")

        with self.voiceover(text="Breadth-first search explores a graph one level at a time.") as tracker:
            self.play(Write(title), Create(g))
            self.play(FadeIn(queue_text))

        adjacency = {v: [b for a, b in edges if a == v] for v in vertices}
        queue, visited = deque([1]), {1}
        with self.voiceover(text="We take the front of the queue, visit it, and add its children to the back.") as tracker:
            while queue:
                v = queue.popleft()
                self.play(g.vertices[v].animate.set_fill(T.highlight, family=False), run_time=0.4)
                for child in adjacency[v]:
                    if child not in visited:
                        visited.add(child)
                        queue.append(child)
                        self.play(g.edges[(v, child)].animate.set_color(T.highlight), run_time=0.25)
                new_caption = caption(f"queue: {list(queue)}")
                self.play(
                    g.vertices[v].animate.set_fill(T.secondary, family=False),
                    Transform(queue_text, new_caption),
                    run_time=0.4,
                )
