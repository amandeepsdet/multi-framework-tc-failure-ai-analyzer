"""Minimal, dependency-free DOM parsing for locator healing.

Uses only the standard-library :mod:`html.parser` so the SDK stays offline and
framework-agnostic. Produces a flat list of :class:`Element` descriptors that
the healing engine reasons over — no browser or heavy HTML library required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

_INTERACTIVE = {"a", "button", "input", "select", "textarea", "option", "label"}
_TEST_ID_ATTRS = ("data-testid", "data-test-id", "data-test", "data-cy", "data-qa")


@dataclass
class Element:
    """A single parsed DOM element with the attributes healing cares about."""

    tag: str = ""
    attrs: dict[str, str] = field(default_factory=dict)
    text: str = ""

    def attr(self, name: str) -> str:
        return self.attrs.get(name, "")

    def test_id(self) -> tuple[str, str] | None:
        for name in _TEST_ID_ATTRS:
            if self.attrs.get(name):
                return name, self.attrs[name]
        return None

    def classes(self) -> list[str]:
        return [c for c in self.attr("class").split() if c]

    def is_interactive(self) -> bool:
        return self.tag in _INTERACTIVE or bool(self.attr("role"))


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[Element] = []
        self._stack: list[Element] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        el = Element(tag=tag, attrs={k: (v or "") for k, v in attrs})
        self.elements.append(el)
        self._stack.append(el)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append(Element(tag=tag, attrs={k: (v or "") for k, v in attrs}))

    def handle_endtag(self, tag: str) -> None:
        if self._stack and self._stack[-1].tag == tag:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text and self._stack:
            self._stack[-1].text = (self._stack[-1].text + " " + text).strip()


def parse_dom(html: str) -> list[Element]:
    """Parse an HTML snapshot into a flat list of :class:`Element`.

    Never raises on malformed markup — returns whatever was parsed so far.
    """
    if not html or not html.strip():
        return []
    parser = _Collector()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - tolerate corrupted/partial DOM
        pass
    return parser.elements
