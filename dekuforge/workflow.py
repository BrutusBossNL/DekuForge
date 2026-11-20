"""Validated build requests and honest stage-level time estimates."""

from dataclasses import dataclass
import math
import json
from pathlib import Path
import time

from .core import ROOT


def validate_source(value):
    if not value:
        raise ValueError("source_missing")
    source = Path(value).expanduser().resolve()
    if not source.is_file():
        raise ValueError("invalid_source")
    with source.open("rb") as stream:
        if stream.read(4) != b"NUP\x01":
            raise ValueError("invalid_source")
    return source


def validate_destination(value, current_installation=""):
    if not value:
        raise ValueError("invalid_destination")
    original = Path(value).expanduser().absolute()
    destination = original.resolve()
    if destination != original or destination == ROOT or destination.is_relative_to(ROOT / "engine"):
        raise ValueError("invalid_destination")
    if current_installation:
        protected = Path(current_installation).resolve().parent
        rebuild = False
        if destination == protected and destination.is_relative_to(ROOT/'build'):
            from . import COMPONENTS
            marker = destination/'.dekuforge-open-output.json'
            if (COMPONENTS['engine'].get('backend') == 'independent' and marker.is_file()
                    and marker.resolve() == marker and marker.stat().st_size <= 16384
                    and (destination/'.dekuforge-owned').is_file()):
                from .open_engine import manifest
                try:
                    record = json.loads(marker.read_text(encoding='utf-8'))
                    rebuild = record.get('provider_revision') == manifest('hookshot')['revision']
                except (OSError, ValueError, AttributeError):
                    pass
        if not rebuild and (destination == protected or destination.is_relative_to(protected) or protected.is_relative_to(destination)):
            raise ValueError("invalid_destination")
    if destination.exists():
        if not destination.is_dir():
            raise ValueError("invalid_destination")
        if any(destination.iterdir()) and not (destination / ".dekuforge-owned").is_file():
            raise ValueError("invalid_destination")
        for directory in (destination, *destination.parents):
            if directory.is_symlink() or getattr(directory, "is_junction", lambda: False)():
                raise ValueError("invalid_destination")
    return destination


@dataclass(frozen=True)
class BuildRequest:
    source: Path
    destination: Path

    @classmethod
    def create(cls, source, destination, current_installation=""):
        return cls(validate_source(source), validate_destination(destination, current_installation))


@dataclass
class Progress:
    started: float = 0
    phase_started: float = 0
    phase: str = "checking"
    done: float = 0
    total: float = 0
    active: bool = False
    ended: float = 0
    overall: float = 0          # how far the whole build is, as the provider reports it (0..1)
    eta: float | None = None    # the provider's measured time left for its current long step, in seconds
    eta_at: float = 0           # when that estimate was received

    def begin(self, now=None):
        self.started = self.phase_started = time.monotonic() if now is None else now
        self.phase = "checking"
        self.done = self.total = self.ended = self.overall = self.eta_at = 0
        self.eta = None
        self.active = True

    def update(self, event, now=None):
        if not isinstance(event, dict):
            return
        now = time.monotonic() if now is None else now
        if "overall" in event or "eta" in event:
            # Standalone events from the provider's own progress and estimate lines: they belong to no single stage
            # and must not reset the stage's done/total.
            overall, eta = event.get("overall"), event.get("eta")
            if isinstance(overall, (int, float)) and math.isfinite(overall) and 0 <= overall <= 1:
                self.overall = max(self.overall, overall)
            if isinstance(eta, (int, float)) and math.isfinite(eta) and 0 <= eta <= 7 * 86400:
                self.eta, self.eta_at = eta, now
            return
        phase = event.get("phase", event.get("stage", self.phase))
        if phase != self.phase:
            self.phase, self.phase_started = phase, now
            self.done = self.total = 0
        done, total = event.get("done", event.get("files", 0)), event.get("total", 0)
        if isinstance(done, (int, float)) and isinstance(total, (int, float)):
            if math.isfinite(done) and math.isfinite(total) and 0 <= done <= total:
                self.done, self.total = done, total

    def finish(self, now=None):
        self.ended = time.monotonic() if now is None else now
        self.active = False

    def elapsed(self, now=None):
        if not self.started and not self.active and not self.ended:
            return 0
        end = (time.monotonic() if now is None else now) if self.active else self.ended
        return max(0, end - self.started)

    def fraction(self):
        """How far the build is for the progress bar: the provider's whole-build fraction, else the current stage's."""
        if self.overall:
            return self.overall
        return self.done / self.total if self.total and self.done else 0

    def remaining(self, now=None):
        # This estimates only a measured step. Unknown work is never presented
        # as a made-up overall build duration: the provider's own estimate of
        # its long compile step counts down between its updates, and a stage
        # that reports done/total is extrapolated from its own pace.
        if not self.active:
            return None
        now = time.monotonic() if now is None else now
        if self.eta is not None:
            left = self.eta - (now - self.eta_at)
            if left > 0:
                return left
        if not self.total or not self.done:
            return None
        age = now - self.phase_started
        if age < 2:
            return None
        return max(0, age * (self.total - self.done) / self.done)


def duration(seconds):
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"
