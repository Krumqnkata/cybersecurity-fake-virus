"""Small, platform-neutral reliability primitives for Cyber Classroom.

This module deliberately contains no Tk or Win32 calls so the controller rules can
be regression-tested without opening windows on the test machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import queue
import threading
import time
from typing import Any, Callable, Iterable


ABSOLUTE_MAX_TABS = 8
ABSOLUTE_MAX_EFFECTS = 8


@dataclass(frozen=True)
class ResourceProfile:
    name: str
    max_tabs: int
    max_effects: int
    visual_fps: int
    image_size: tuple[int, int]

    def __post_init__(self) -> None:
        if not 1 <= self.max_tabs <= ABSOLUTE_MAX_TABS:
            raise ValueError("invalid tab budget")
        if not 1 <= self.max_effects <= ABSOLUTE_MAX_EFFECTS:
            raise ValueError("invalid effect-window budget")


PROFILES = {
    "Училищен безопасен": ResourceProfile(
        "Училищен безопасен", 4, 6, 8, (960, 540)
    ),
    "Балансиран": ResourceProfile("Балансиран", 6, 8, 12, (1280, 720)),
}


@dataclass
class ScenarioState:
    """Shared fictional state plus generation guards for delayed callbacks."""

    generation: int = 0
    chapter_generation: int = 0
    chapter_index: int = 0
    installer_stage: str = "welcome"
    scanner_stage: str = "idle"
    scanner_paused: bool = False
    terminal_stage: str = "idle"
    locked_count: int = 0
    browser_actions: int = 0
    scanner_results: tuple[str, ...] = (
        "Adware.PopUps (учебен запис)",
        "Trojan.FakeInstaller (учебен запис)",
        "Suspicious.UpdateHelper (учебен запис)",
    )

    def new_session(self) -> int:
        self.generation += 1
        self.chapter_generation += 1
        self.chapter_index = 0
        self.installer_stage = "welcome"
        self.scanner_stage = "idle"
        self.scanner_paused = False
        self.terminal_stage = "idle"
        self.locked_count = 0
        self.browser_actions = 0
        return self.generation

    def invalidate(self) -> None:
        self.generation += 1
        self.chapter_generation += 1

    def new_chapter(self, index: int) -> tuple[int, int]:
        self.chapter_index = max(0, index)
        self.chapter_generation += 1
        return self.generation, self.chapter_generation

    def accepts(self, generation: int, chapter_generation: int | None = None) -> bool:
        return generation == self.generation and (
            chapter_generation is None or chapter_generation == self.chapter_generation
        )


class BoundedEventBus:
    """Priority events plus bounded/coalesced ordinary controller events.

    Producers never block. Emergency events use the separate low-volume priority
    path; visual updates can be replaced by a newer update with the same key.
    """

    def __init__(self, maxsize: int = 64) -> None:
        self.normal: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=maxsize)
        self.priority: queue.SimpleQueue[tuple[str, Any]] = queue.SimpleQueue()
        self._coalesced: dict[str, tuple[str, Any]] = {}
        self._lock = threading.Lock()
        self.dropped = 0

    def post(
        self,
        action: str,
        payload: Any = None,
        *,
        priority: bool = False,
        coalesce: str | None = None,
    ) -> bool:
        event = (action, payload)
        if priority:
            self.priority.put(event)
            return True
        if coalesce is not None:
            with self._lock:
                self._coalesced[coalesce] = event
            return True
        try:
            self.normal.put_nowait(event)
            return True
        except queue.Full:
            self.dropped += 1
            return False

    # Queue-compatible adapter for older call sites and small test fakes.
    def put(self, event: tuple[str, Any]) -> None:
        action, payload = event
        self.post(action, payload, priority=action in {"quit", "hotkeys_error"})

    def get_nowait(self) -> tuple[str, Any]:
        try:
            return self.priority.get_nowait()
        except queue.Empty:
            pass
        with self._lock:
            if self._coalesced:
                _, event = self._coalesced.popitem()
                return event
        return self.normal.get_nowait()

    def drain(self, limit: int = 12) -> list[tuple[str, Any]]:
        result: list[tuple[str, Any]] = []
        # Priority traffic is deliberately tiny and must not sit behind render work.
        while True:
            try:
                result.append(self.priority.get_nowait())
            except queue.Empty:
                break
        remaining = max(0, limit - len(result))
        if remaining:
            with self._lock:
                coalesced = list(self._coalesced.values())[:remaining]
                for key in list(self._coalesced)[: len(coalesced)]:
                    self._coalesced.pop(key, None)
            result.extend(coalesced)
            remaining = max(0, limit - len(result))
        for _ in range(remaining):
            try:
                result.append(self.normal.get_nowait())
            except queue.Empty:
                break
        return result

    def clear_normal(self) -> None:
        with self._lock:
            self._coalesced.clear()
        while True:
            try:
                self.normal.get_nowait()
            except queue.Empty:
                return

    def clear_all(self) -> None:
        self.clear_normal()
        while True:
            try:
                self.priority.get_nowait()
            except queue.Empty:
                return


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self._last: dict[str, float] = {}

    def allow(self, key: str, interval: float, now: float | None = None) -> bool:
        current = self.clock() if now is None else now
        previous = self._last.get(key)
        if previous is not None and current - previous < interval:
            return False
        self._last[key] = current
        return True

    def reset(self, *keys: str) -> None:
        if keys:
            for key in keys:
                self._last.pop(key, None)
        else:
            self._last.clear()


class PauseClock:
    """A deterministic pause-aware clock suitable for fake-clock tests."""

    def __init__(self, source: Callable[[], float] = time.monotonic) -> None:
        self.source = source
        self.value = 0.0
        self.paused = True
        self._last = source()

    def reset(self, paused: bool = False) -> None:
        self.value = 0.0
        self.paused = paused
        self._last = self.source()

    def set_paused(self, paused: bool) -> None:
        self.update()
        self.paused = paused
        self._last = self.source()

    def update(self, rate: float = 1.0) -> float:
        now = self.source()
        delta = max(0.0, now - self._last)
        self._last = now
        if not self.paused:
            self.value += delta * rate
        return self.value


def retained_chapter_index(clock_value: float, chapters: Iterable[tuple[float, str]]) -> int:
    index = 0
    for candidate, (start, _) in enumerate(chapters):
        if start > clock_value:
            break
        index = candidate
    return index
