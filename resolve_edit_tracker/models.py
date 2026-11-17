"""Data model. JSON field names match the macOS app so sessions.json is interchangeable."""

from .i18n import tr
import uuid
import math
from dataclasses import dataclass, field, fields, asdict
from typing import Optional

from .util import to_iso, from_iso

PAGES = ["media", "cut", "edit", "fusion", "color", "fairlight", "deliver", "photo"]
PAGE_NAMES = {
    "media": "Media", "cut": "Cut", "edit": "Edit", "fusion": "Fusion",
    "color": "Color", "fairlight": "Fairlight", "deliver": "Deliver", "photo": "Photo",
}


def page_display(raw):
    return PAGE_NAMES.get(raw, (raw or "").capitalize())


@dataclass
class ResolveStatus:
    running: bool = False
    api_ok: bool = False
    reason: Optional[str] = None
    page: Optional[str] = None
    project: Optional[str] = None
    timeline: Optional[str] = None
    timecode: Optional[str] = None
    rendering: bool = False
    busy: bool = False          # project loaded but Resolve is on a dialog / background task
    transient_error: Optional[str] = None
    resolve_version: Optional[str] = None

    @classmethod
    def from_dict(cls, d):
        return cls(
            running=bool(d.get("running", False)),
            api_ok=bool(d.get("apiOk", False)),
            reason=d.get("reason"),
            page=d.get("page"),
            project=d.get("project"),
            timeline=d.get("timeline"),
            timecode=d.get("timecode"),
            rendering=bool(d.get("rendering", False)),
            busy=bool(d.get("busy", False)),
            transient_error=d.get("transientError"),
            resolve_version=d.get("resolveVersion"),
        )

    @property
    def in_project(self):
        return self.has_project and self.page_enum is not None and not self.busy

    @property
    def has_project(self):
        return self.running and self.api_ok and bool(self.project)

    @property
    def page_enum(self):
        return self.page if self.page in PAGES else None


OFFLINE = ResolveStatus()


@dataclass(frozen=True)
class ConnectionState:
    kind: str                       # connected | resolveNotRunning | apiUnavailable | probeUnavailable
    reason: Optional[str] = None

    @property
    def is_healthy(self):
        return self.kind == "connected"

    @property
    def short_label(self):
        return {
            "connected": tr("Connected"),
            "resolveNotRunning": tr("Resolve not running"),
            "apiUnavailable": tr("Can't reach Resolve scripting"),
            "probeUnavailable": tr("Tracker helper unavailable"),
        }[self.kind]

    @property
    def detail(self):
        if self.kind in ("apiUnavailable", "probeUnavailable"):
            return self.reason
        return None


CONNECTED = ConnectionState("connected")
RESOLVE_NOT_RUNNING = ConnectionState("resolveNotRunning")


def api_unavailable(reason):
    return ConnectionState("apiUnavailable", reason)


def probe_unavailable(reason):
    return ConnectionState("probeUnavailable", reason)


@dataclass
class Session:
    project: str
    start: float                     # epoch seconds
    end: float
    duration_sec: float
    rate: float
    currency: str
    note: str = ""
    page_seconds: dict = field(default_factory=dict)
    timeline_seconds: dict = field(default_factory=dict)
    manual: bool = False
    id: str = field(default_factory=lambda: str(uuid.uuid4()).upper())

    def validate(self):
        for value in (self.start,self.end,self.duration_sec,self.rate,*self.page_seconds.values(),*self.timeline_seconds.values()):
            if not isinstance(value,(int,float)) or not math.isfinite(value): raise ValueError('Session contains a non-finite value')
        if self.duration_sec<0 or self.rate<0 or any(v<0 for v in (*self.page_seconds.values(),*self.timeline_seconds.values())):
            raise ValueError('Session contains negative time or rate')
        if not self.id or not isinstance(self.project,str) or not isinstance(self.currency,str) or not isinstance(self.note,str):
            raise ValueError('Session metadata is invalid')
        return self

    @property
    def earnings(self):
        return self.duration_sec / 3600.0 * self.rate

    def to_json(self):
        return {
            "id": self.id,
            "project": self.project,
            "start": to_iso(self.start),
            "end": to_iso(self.end),
            "durationSec": self.duration_sec,
            "rate": self.rate,
            "currency": self.currency,
            "note": self.note,
            "pageSeconds": self.page_seconds,
            "timelineSeconds": self.timeline_seconds,
            "manual": self.manual,
        }

    @classmethod
    def from_json(cls, d):
        start = from_iso(d["start"])
        try:
            end = from_iso(d["end"]) if d.get("end") else start
        except ValueError:
            end = start
        return cls(
            id=str(d.get("id") or uuid.uuid4()).upper(),
            project=d.get("project") or "Untitled",
            start=start,
            end=end,
            duration_sec=float(d.get("durationSec") or 0),
            rate=float(d.get("rate") or 0),
            currency=d.get("currency") or "€",
            note=d.get("note") or "",
            page_seconds={str(k): float(v) for k, v in (d.get("pageSeconds") or {}).items()},
            timeline_seconds={str(k): float(v) for k, v in (d.get("timelineSeconds") or {}).items()},
            manual=bool(d.get("manual", False)),
        ).validate()


@dataclass
class Settings:
    rate: float = 25.0
    currency: str = "€"
    projectRates: dict = field(default_factory=dict)
    currencyMode: str = "manual"
    currencyProfiles: dict = field(default_factory=dict)
    idleMinutes: int = 5                      # 0 = off
    pauseDuringRenders: bool = True           # keep tracking while Resolve renders
    trackOnlyWhenFrontmost: bool = True
    playSoundOnStart: bool = True
    toastOnIdleResume: bool = False
    soundName: str = "Windows Notify System Generic"
    menuBarShowTime: bool = True              # show elapsed time in the tray tooltip
    launchAtLogin: bool = False
    animations: bool = True
    language: str = "en"
    invoiceLanguage: str = "en"
    theme: str = "Steel"                    # dashboard color scheme
    pythonPath: str = ""                      # optional python.exe for the Resolve helper

    def rate_for(self, project):
        return self.projectRates.get(project, self.rate)

    def to_json(self):
        return asdict(self)

    @classmethod
    def from_json(cls, d):
        base = cls()
        if not isinstance(d, dict):
            from .currencies import default_currency
            base.currencyMode = "auto"
            base.currency = default_currency(base.language)
            return base
        for f in fields(cls):
            if f.name in d and d[f.name] is not None:
                want = type(getattr(base, f.name))
                val = d[f.name]
                try:
                    if f.name == "currencyProfiles":
                        from .currencies import clean_profiles
                        val = clean_profiles(val)
                    elif want is bool:
                        val = bool(val)
                    elif want is int:
                        val = int(val)
                    elif want is float:
                        val = float(val)
                    elif want is dict:
                        val = {str(k): float(v) for k, v in dict(val).items()}
                    else:
                        val = str(val)
                    setattr(base, f.name, val)
                except (TypeError, ValueError, OverflowError):
                    pass
        from .themes import normalize
        base.theme = normalize(base.theme)
        from .i18n import normalize_language
        base.language = normalize_language(base.language)
        base.invoiceLanguage = normalize_language(base.invoiceLanguage)
        base.currencyMode = base.currencyMode if base.currencyMode in ("auto", "manual") else "manual"
        if not base.currency.strip(): base.currency = "€"
        base.idleMinutes = max(0,min(240,base.idleMinutes))
        if not math.isfinite(base.rate) or base.rate < 0: base.rate = cls().rate
        base.projectRates = {k:v for k,v in base.projectRates.items() if math.isfinite(v) and v>=0}
        base.launchAtLogin = False
        return base


NOT_IN_PROJECT = "notInProject"
TRACKING = "tracking"
IDLE_PAUSED = "idlePaused"
MANUALLY_PAUSED = "manuallyPaused"


@dataclass
class Stats:
    project: Optional[str] = None
    today_sec: float = 0.0
    week_sec: float = 0.0
    project_total_sec: float = 0.0
    project_earnings: float = 0.0
    project_money: dict = field(default_factory=dict)
    breakdown: list = field(default_factory=list)   # [(page, seconds)] sorted desc
