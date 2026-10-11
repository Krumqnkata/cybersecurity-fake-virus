"""Small, platform-neutral reliability primitives for Cyber Classroom.

This module deliberately contains no Tk or Win32 calls so the controller rules can
be regression-tested without opening windows on the test machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
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


class ScenarioEvent(str, Enum):
    """Semantic incident events shared by every visual surface."""

    DOWNLOAD_REQUESTED = "download_requested"
    DOWNLOAD_COMPLETED = "download_completed"
    STUDENT_DECISION = "student_decision"
    TEACHER_ACCEPTED = "teacher_accepted"
    TEACHER_COMPROMISED = "teacher_compromised"
    UAC_APPROVED = "uac_approved"
    UAC_DECLINED = "uac_declined"
    INSTALL_STARTED = "install_started"
    INSTALL_CANCELLED = "install_cancelled"
    INSTALL_COMPLETED = "install_completed"
    HELPER_STARTED = "helper_started"
    HELPER_STOPPED = "helper_stopped"
    FIREWALL_BLOCKED = "firewall_blocked"
    FIREWALL_ALLOWED = "firewall_allowed"
    ALERT_RAISED = "alert_raised"
    SCAN_STARTED = "scan_started"
    SCAN_PAUSED = "scan_paused"
    SCAN_CANCELLED = "scan_cancelled"
    SCAN_COMPLETED = "scan_completed"
    FILES_LOCKED = "files_locked"
    QUARANTINE_STARTED = "quarantine_started"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"


@dataclass(frozen=True)
class StoryBeat:
    """One deterministic, named point in a presentation preset."""

    beat_id: str
    at: int
    scene: str
    chapter: int


@dataclass(frozen=True)
class StoryPreset:
    """A complete story graph; presets differ in content, not only playback rate."""

    label: str
    duration: int
    beats: tuple[StoryBeat, ...]
    chapters: tuple[tuple[int, str], ...]

    def __post_init__(self) -> None:
        if self.duration <= 0 or not self.beats:
            raise ValueError("story preset must contain timed beats")
        times = [beat.at for beat in self.beats]
        identifiers = [beat.beat_id for beat in self.beats]
        if times != sorted(times) or len(set(identifiers)) != len(identifiers):
            raise ValueError("story beats must be ordered and uniquely named")
        if self.beats[-1].scene != "finish" or self.beats[-1].at != self.duration:
            raise ValueError("story preset must finish at its declared duration")
        if not self.chapters or self.chapters[0][0] != 0:
            raise ValueError("story chapters must start at zero")


def _beat(beat_id: str, at: int, scene: str, chapter: int) -> StoryBeat:
    return StoryBeat(beat_id, at, scene, chapter)


STORY_PRESETS = {
    "10 минути": StoryPreset(
        "10 минути", 600,
        (
            _beat("site", 0, "browser", 0),
            _beat("download", 50, "download", 0),
            _beat("uac", 80, "uac", 1),
            _beat("installer", 105, "installer", 1),
            _beat("helper", 180, "helper", 2),
            _beat("notification", 215, "notification", 2),
            _beat("tabs", 240, "tabs", 2),
            _beat("taskmanager", 280, "taskmanager", 3),
            _beat("warning", 320, "warning", 3),
            _beat("scanner", 350, "scanner", 3),
            _beat("explorer", 420, "explorer", 4),
            _beat("locking", 455, "files_chapter", 4),
            _beat("ransom", 500, "ransom", 5),
            _beat("recovery", 540, "recovery", 6),
            _beat("debrief", 570, "debrief", 7),
            _beat("finish", 600, "finish", 7),
        ),
        ((0, "Minecraft модът CaveDepths"), (80, "Подвеждащото стартиране"),
         (180, "Нежеланият помощен процес"), (320, "Откриване и проверка"),
         (420, "Въздействие върху учебните файлове"), (500, "Ransomware натиск"),
         (540, "Ограничаване и възстановяване"), (570, "Какво научихме")),
    ),
    "15 минути": StoryPreset(
        "15 минути", 900,
        (
            _beat("site", 0, "browser", 0),
            _beat("download", 70, "download", 0),
            _beat("uac", 100, "uac", 1),
            _beat("installer", 130, "installer", 1),
            _beat("helper", 225, "helper", 2),
            _beat("notification", 255, "notification", 2),
            _beat("tabs", 290, "tabs", 2),
            _beat("firewall", 330, "firewall", 2),
            _beat("taskmanager", 370, "taskmanager", 3),
            _beat("updater", 415, "updater", 3),
            _beat("error", 465, "error", 3),
            _beat("warning", 500, "warning", 4),
            _beat("scanner", 535, "scanner", 4),
            _beat("history", 610, "protection_history", 4),
            _beat("response", 655, "terminal_chapter", 5),
            _beat("explorer", 710, "explorer", 6),
            _beat("locking", 745, "files_chapter", 6),
            _beat("ransom", 785, "ransom", 7),
            _beat("recovery", 835, "recovery", 8),
            _beat("debrief", 875, "debrief", 9),
            _beat("finish", 900, "finish", 9),
        ),
        ((0, "Minecraft модът CaveDepths"), (100, "Подвеждащото стартиране"),
         (225, "Нежеланият помощен процес"), (370, "Видими симптоми"),
         (500, "Откриване и проверка"), (655, "Разследване"),
         (710, "Въздействие върху учебните файлове"), (785, "Ransomware натиск"),
         (835, "Ограничаване и възстановяване"), (875, "Какво научихме")),
    ),
    "20 минути": StoryPreset(
        "20 минути", 1200,
        (
            _beat("site", 0, "browser", 0),
            _beat("download", 90, "download", 0),
            _beat("uac", 125, "uac", 1),
            _beat("installer", 160, "installer", 1),
            _beat("helper", 280, "helper", 2),
            _beat("notification", 320, "notification", 2),
            _beat("tabs", 360, "tabs", 2),
            _beat("firewall", 410, "firewall", 2),
            _beat("taskmanager", 460, "taskmanager", 3),
            _beat("updater", 520, "updater", 3),
            _beat("error", 575, "error", 3),
            _beat("warning", 625, "warning", 4),
            _beat("scanner", 670, "scanner", 4),
            _beat("properties", 750, "properties", 5),
            _beat("history", 805, "protection_history", 5),
            _beat("network", 850, "network_activity", 5),
            _beat("response", 900, "terminal_chapter", 5),
            _beat("explorer", 965, "explorer", 6),
            _beat("locking", 1005, "files_chapter", 6),
            _beat("ransom", 1050, "ransom", 7),
            _beat("recovery", 1110, "recovery", 8),
            _beat("debrief", 1170, "debrief", 9),
            _beat("finish", 1200, "finish", 9),
        ),
        ((0, "Minecraft модът CaveDepths"), (125, "Подвеждащото стартиране"),
         (280, "Нежеланият помощен процес"), (460, "Видими симптоми"),
         (625, "Откриване и проверка"), (750, "Разширено разследване"),
         (965, "Въздействие върху учебните файлове"), (1050, "Ransomware натиск"),
         (1110, "Ограничаване и възстановяване"), (1170, "Какво научихме")),
    ),
}

DEFAULT_STORY_LABEL = "15 минути"


@dataclass
class ScenarioState:
    """Shared fictional state plus generation guards for delayed callbacks."""

    generation: int = 0
    chapter_generation: int = 0
    chapter_index: int = 0
    phase: str = "idle"
    download_stage: str = "idle"
    installer_stage: str = "welcome"
    helper_state: str = "absent"
    firewall_state: str = "unknown"
    scanner_stage: str = "idle"
    scanner_paused: bool = False
    terminal_stage: str = "idle"
    detection_state: str = "clear"
    quarantine_state: str = "idle"
    recovery_stage: str = "idle"
    locked_count: int = 0
    browser_actions: int = 0
    tray_visible: bool = False
    branch_pending: bool = False
    branch_checkpoint: str = ""
    student_choice: str = ""
    handled_events: set[str] = field(default_factory=set)
    action_history: list[str] = field(default_factory=list)
    scanner_results: tuple[str, ...] = (
        "PUA:Win32/BlockForgeOffer",
        "Trojan:Win32/CaveDepthsLoader",
        "Behavior:Win32/ModUpdateHelper",
    )

    def new_session(self) -> int:
        self.generation += 1
        self.chapter_generation += 1
        self.chapter_index = 0
        self.phase = "discovery"
        self.download_stage = "idle"
        self.installer_stage = "welcome"
        self.helper_state = "absent"
        self.firewall_state = "unknown"
        self.scanner_stage = "idle"
        self.scanner_paused = False
        self.terminal_stage = "idle"
        self.detection_state = "clear"
        self.quarantine_state = "idle"
        self.recovery_stage = "idle"
        self.locked_count = 0
        self.browser_actions = 0
        self.tray_visible = False
        self.branch_pending = False
        self.branch_checkpoint = ""
        self.student_choice = ""
        self.handled_events.clear()
        self.action_history.clear()
        return self.generation

    def invalidate(self) -> None:
        self.generation += 1
        self.chapter_generation += 1

    def new_chapter(self, index: int) -> tuple[int, int]:
        self.chapter_index = max(0, index)
        self.chapter_generation += 1
        return self.generation, self.chapter_generation

    def rebuild_for_story(
        self,
        completed_scenes: Iterable[str],
        chapter_index: int,
        *,
        locked_count: int = 0,
    ) -> int:
        """Rebuild causal state before replaying or skipping to a chapter.

        Only semantic facts from beats *before* the target are projected.  This
        invalidates every delayed callback from the old chapter and makes a
        replay deterministic without asking visual scenes to invent state.
        Filesystem work remains the controller's responsibility; ``locked_count``
        is the verified count observed in the owned teaching folder.
        """
        scenes = set(completed_scenes)
        generation = self.new_session()
        self.chapter_index = max(0, chapter_index)

        def apply(event: ScenarioEvent, key: str, **payload: Any) -> None:
            self.apply_event(
                event,
                {"idempotency_key": f"rebuild:{key}", **payload},
                generation=generation,
            )

        if "download" in scenes:
            apply(ScenarioEvent.DOWNLOAD_REQUESTED, "download-requested")
            apply(ScenarioEvent.DOWNLOAD_COMPLETED, "download-completed")
        if "uac" in scenes:
            apply(ScenarioEvent.UAC_APPROVED, "uac-approved")
        if "installer" in scenes:
            apply(ScenarioEvent.INSTALL_STARTED, "install-started")
            apply(ScenarioEvent.INSTALL_COMPLETED, "install-completed")
        if "helper" in scenes:
            apply(ScenarioEvent.HELPER_STARTED, "helper-started")
        if "firewall" in scenes:
            apply(ScenarioEvent.FIREWALL_ALLOWED, "firewall-allowed")
        if "warning" in scenes:
            apply(ScenarioEvent.ALERT_RAISED, "alert-raised")
        if "scanner" in scenes:
            apply(ScenarioEvent.SCAN_STARTED, "scan-started")
            apply(ScenarioEvent.SCAN_COMPLETED, "scan-completed")
        if "terminal_chapter" in scenes:
            self.terminal_stage = "completed"
        if "files_chapter" in scenes:
            apply(ScenarioEvent.FILES_LOCKED, "files-locked", count=locked_count)
        if "recovery" in scenes:
            apply(ScenarioEvent.QUARANTINE_STARTED, "quarantine-started")
            apply(ScenarioEvent.RECOVERY_STARTED, "recovery-started")
            apply(ScenarioEvent.FILES_LOCKED, "files-restored", count=locked_count)
            apply(ScenarioEvent.RECOVERY_COMPLETED, "recovery-completed")
        return generation

    def accepts(self, generation: int, chapter_generation: int | None = None) -> bool:
        return generation == self.generation and (
            chapter_generation is None or chapter_generation == self.chapter_generation
        )

    def apply_event(
        self,
        event: ScenarioEvent | str,
        payload: dict[str, Any] | None = None,
        *,
        generation: int | None = None,
        chapter_generation: int | None = None,
    ) -> bool:
        """Apply one idempotent semantic transition.

        Visual callbacks may arrive after a scene has closed.  Passing their
        captured generation values makes such callbacks harmless.
        """
        if generation is not None and not self.accepts(generation, chapter_generation):
            return False
        try:
            kind = event if isinstance(event, ScenarioEvent) else ScenarioEvent(event)
        except ValueError:
            return False
        data = payload or {}
        repeatable = {ScenarioEvent.FILES_LOCKED, ScenarioEvent.SCAN_PAUSED}
        key = str(data.get("idempotency_key") or kind.value)
        if kind not in repeatable and key in self.handled_events:
            return False

        changed = True
        if kind is ScenarioEvent.DOWNLOAD_REQUESTED:
            self.phase, self.download_stage = "delivery", "requested"
        elif kind is ScenarioEvent.DOWNLOAD_COMPLETED:
            self.download_stage = "completed"
        elif kind is ScenarioEvent.STUDENT_DECISION:
            self.branch_checkpoint = str(data.get("checkpoint", "decision"))
            self.student_choice = str(data.get("choice", ""))
            self.branch_pending = True
        elif kind is ScenarioEvent.TEACHER_ACCEPTED:
            self.branch_pending = False
            if self.student_choice in {"no", "cancel", "block", "stop"}:
                self.phase = "contained"
        elif kind is ScenarioEvent.TEACHER_COMPROMISED:
            self.branch_pending = False
            self.phase = str(data.get("phase", "execution"))
        elif kind is ScenarioEvent.UAC_APPROVED:
            self.phase, self.installer_stage = "execution", "welcome"
        elif kind is ScenarioEvent.UAC_DECLINED:
            self.phase = "decision"
        elif kind is ScenarioEvent.INSTALL_STARTED:
            self.installer_stage = "installing"
        elif kind is ScenarioEvent.INSTALL_CANCELLED:
            self.installer_stage = "cancelled"
        elif kind is ScenarioEvent.INSTALL_COMPLETED:
            self.phase, self.installer_stage = "foothold", "completed"
            self.helper_state, self.tray_visible = "running", True
        elif kind is ScenarioEvent.HELPER_STARTED:
            self.phase, self.helper_state, self.tray_visible = "foothold", "running", True
        elif kind is ScenarioEvent.HELPER_STOPPED:
            self.helper_state, self.tray_visible = "stopped", False
        elif kind is ScenarioEvent.FIREWALL_BLOCKED:
            self.firewall_state = "blocked"
        elif kind is ScenarioEvent.FIREWALL_ALLOWED:
            self.firewall_state = "allowed"
        elif kind is ScenarioEvent.ALERT_RAISED:
            self.phase, self.detection_state = "detection", "alerted"
        elif kind is ScenarioEvent.SCAN_STARTED:
            self.scanner_stage, self.scanner_paused = "scanning", False
        elif kind is ScenarioEvent.SCAN_PAUSED:
            paused = bool(data.get("paused", True))
            changed = paused != self.scanner_paused
            self.scanner_paused = paused
        elif kind is ScenarioEvent.SCAN_CANCELLED:
            self.scanner_stage = "cancelled"
        elif kind is ScenarioEvent.SCAN_COMPLETED:
            self.scanner_stage, self.detection_state = "completed", "detected"
        elif kind is ScenarioEvent.FILES_LOCKED:
            count = max(0, min(8, int(data.get("count", self.locked_count))))
            changed = count != self.locked_count
            self.locked_count = count
            if count:
                self.phase = "impact"
        elif kind is ScenarioEvent.QUARANTINE_STARTED:
            self.phase, self.quarantine_state = "containment", "running"
        elif kind is ScenarioEvent.RECOVERY_STARTED:
            self.recovery_stage = "restoring"
        elif kind is ScenarioEvent.RECOVERY_COMPLETED:
            self.phase, self.quarantine_state = "recovered", "completed"
            self.recovery_stage, self.helper_state = "completed", "quarantined"
            self.tray_visible = False
        else:
            changed = False

        if not changed:
            return False
        if kind not in repeatable:
            self.handled_events.add(key)
        self.action_history.append(kind.value)
        return True


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
