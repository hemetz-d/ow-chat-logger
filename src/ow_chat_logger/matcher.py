from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class _Node:
    children: dict[str, int] = field(default_factory=dict)
    fail: int = 0
    output: bool = False


class AhoCorasickMatcher:
    """Match many literal substrings in one pass."""

    def __init__(self, patterns: set[str] | list[str] | tuple[str, ...]):
        self._nodes = [_Node()]
        self._build(patterns)

    def _build(self, patterns) -> None:
        for pattern in patterns:
            if not pattern:
                continue

            node_index = 0
            for char in pattern:
                node = self._nodes[node_index]
                node_index = node.children.setdefault(char, len(self._nodes))
                if node_index == len(self._nodes):
                    self._nodes.append(_Node())

            self._nodes[node_index].output = True

        queue: deque[int] = deque()
        for child_index in self._nodes[0].children.values():
            self._nodes[child_index].fail = 0
            queue.append(child_index)

        while queue:
            current_index = queue.popleft()
            current = self._nodes[current_index]

            for char, child_index in current.children.items():
                queue.append(child_index)
                fail_index = current.fail

                while fail_index and char not in self._nodes[fail_index].children:
                    fail_index = self._nodes[fail_index].fail

                next_fail = self._nodes[fail_index].children.get(char, 0)
                self._nodes[child_index].fail = next_fail
                self._nodes[child_index].output = (
                    self._nodes[child_index].output or self._nodes[next_fail].output
                )

    def contains_any(self, text: str) -> bool:
        node_index = 0

        for char in text:
            while node_index and char not in self._nodes[node_index].children:
                node_index = self._nodes[node_index].fail

            node_index = self._nodes[node_index].children.get(char, 0)
            if self._nodes[node_index].output:
                return True

        return False
