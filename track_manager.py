# track_manager.py — multi-track orchestration with export/load helpers
from __future__ import annotations
from typing import Dict, Any, List, Optional
import re

from engine import DiamondHybrid
from week_manager import WeekManager

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

def _is_uuid(s: str) -> bool:
    return bool(_UUID_RE.match(str(s or "")))

class TrackBundle:
    """
    One logical track: its own engine, week manager, and cadence counters.
    Everything a single Tracker page instance needs to run independently.

    This object is *pure logic* — no Streamlit, no Supabase calls.
    Persistence is done via export_state()/import_state() and handled
    by whatever storage layer you use (e.g. Supabase).
    """
    def __init__(self, unit_value: float = 1.0):
        self.eng = DiamondHybrid(unit_value=unit_value)
        self.week = WeekManager()
        # cadence counters (were in st.session_state before)
        self.sessions_today: int = 0
        self.lines_in_session: int = 0
        self.day_key: Optional[str] = None  # "YYYY-MM-DD"

        self._db_loaded: bool = False

        # Optional: DB primary key for this track row (can be None if not persisted yet)
        self.db_id: Optional[str] = None

    def set_unit_value(self, v: float) -> None:
        try:
            self.eng.set_unit_value(float(v))
        except Exception:
            pass

    # ============================================================
    #  Persistence helpers — used by TrackManager / Supabase layer
    # ============================================================
    def export_state(self) -> Dict[str, Any]:
        """
        Serialize everything needed to restore this track later.

        Shape expected by db.save_track_state/load_track_state and Tracker:

          {
            "db_id": ... (optional),
            "engine": {...},          # engine.export_state()
            "week":   {...},          # week.export_state()
            "sessions_today": int,
            "lines_in_session": int,
            "day_key": "YYYY-MM-DD" | None,
          }
        """
        engine_state: Dict[str, Any] = {}
        if hasattr(self.eng, "export_state"):
            try:
                engine_state = self.eng.export_state()
            except Exception:
                engine_state = {}

        week_state: Dict[str, Any] = {}
        if hasattr(self.week, "export_state"):
            try:
                week_state = self.week.export_state()
            except Exception:
                week_state = {}

        return {
            "db_id": self.db_id,  # optional DB PK if you want to round-trip it
            "engine": engine_state,
            "week": week_state,
            "sessions_today": int(self.sessions_today),
            "lines_in_session": int(self.lines_in_session),
            "day_key": self.day_key,
        }

    def import_state(self, data: Dict[str, Any]) -> None:
        """
        Restore this TrackBundle from a dict shaped like export_state().

        This is what Tracker uses when it calls load_track_state(...) from Supabase
        and then does `bundle.import_state(loaded)`.
        """
        if not isinstance(data, dict):
            return

        # Optional DB primary key (Supabase UUIDs -> keep as string)
        if "db_id" in data:
            try:
                v = data.get("db_id")
                self.db_id = str(v) if v is not None else None
            except Exception:
                self.db_id = None

        # Engine
        eng_state = data.get("engine") or {}
        if isinstance(eng_state, dict):
            try:
                if hasattr(self.eng, "import_state"):
                    self.eng.import_state(eng_state)
                elif hasattr(self.eng, "load_state"):
                    self.eng.load_state(eng_state)
            except Exception as e:
                print(f"[TrackBundle.import_state] engine import suppressed: {e!r}")

        # Week
        week_state = data.get("week") or {}
        if isinstance(week_state, dict):
            try:
                if hasattr(self.week, "import_state"):
                    self.week.import_state(week_state)
                elif hasattr(self.week, "load_state"):
                    self.week.load_state(week_state)
            except Exception as e:
                print(f"[TrackBundle.import_state] week import suppressed: {e!r}")

        # Cadence counters / day key (we still mirror them here even though
        # Tracker's Streamlit session is the main source of truth)
        try:
            self.sessions_today = int(data.get("sessions_today", self.sessions_today) or 0)
        except Exception:
            pass

        try:
            self.lines_in_session = int(data.get("lines_in_session", self.lines_in_session) or 0)
        except Exception:
            pass

        if "day_key" in data:
            try:
                dk = data.get("day_key")
                self.day_key = str(dk) if dk is not None else None
            except Exception:
                pass

    def load_state(self, data: Dict[str, Any]) -> None:
        """
        Legacy-style loader used by TrackManager.load_snapshot() for full manager snapshots.

        Safe to call multiple times; missing keys are ignored.
        """
        if not isinstance(data, dict):
            return

        # Optional DB primary key (Supabase UUIDs -> keep as string)
        if "db_id" in data:
            try:
                v = data.get("db_id")
                self.db_id = str(v) if v is not None else None
            except Exception:
                self.db_id = None

        # Engine + week, using the older load_state contract if present
        eng_state = data.get("engine")
        if isinstance(eng_state, dict):
            if hasattr(self.eng, "load_state"):
                try:
                    self.eng.load_state(eng_state)  # type: ignore[attr-defined]
                except Exception:
                    pass
            elif hasattr(self.eng, "import_state"):
                # Fallback so older snapshots still work after we switch engine to import_state
                try:
                    self.eng.import_state(eng_state)  # type: ignore[attr-defined]
                except Exception:
                    pass

        week_state = data.get("week")
        if isinstance(week_state, dict):
            if hasattr(self.week, "load_state"):
                try:
                    self.week.load_state(week_state)  # type: ignore[attr-defined]
                except Exception:
                    pass
            elif hasattr(self.week, "import_state"):
                try:
                    self.week.import_state(week_state)  # type: ignore[attr-defined]
                except Exception:
                    pass

        # Cadence / day key
        try:
            self.sessions_today = int(data.get("sessions_today", 0) or 0)
        except Exception:
            self.sessions_today = 0

        try:
            self.lines_in_session = int(data.get("lines_in_session", 0) or 0)
        except Exception:
            self.lines_in_session = 0

        try:
            dk = data.get("day_key")
            self.day_key = str(dk) if dk is not None else None
        except Exception:
            self.day_key = None


class TrackManager:
    """
    Holds multiple TrackBundle objects and the 'active' one the UI is bound to.

    This layer is still in-memory only — BUT:
      • export_snapshot() gives you a JSON-serializable view of all tracks
      • load_snapshot() rebuilds everything from that view

    The Supabase layer will sit *outside* this class and:
      • Map user_id ↔ track_id ↔ DB rows
      • Store/retrieve engine/weekly state JSON into the right tables
    """
    def __init__(self, unit_value: float = 1.0):
        self._unit_value = float(unit_value)
        self._tracks: Dict[str, TrackBundle] = {}
        self._active_id: Optional[str] = None

    # ---- CRUD ----
    def ensure(self, track_id: str) -> TrackBundle:
        track_id = str(track_id)

        # HARD GUARD: TrackManager runtime must be UUID track ids only
        if not _is_uuid(track_id):
            raise ValueError(f"TrackManager.ensure() requires UUID track_id, got: {track_id!r}")

        if track_id not in self._tracks:
            self._tracks[track_id] = TrackBundle(unit_value=self._unit_value)
            if self._active_id is None:
                self._active_id = track_id

        return self._tracks[track_id]

    def add(self, track_id: str) -> TrackBundle:
        return self.ensure(track_id)

    def remove(self, track_id: str) -> None:
        if track_id in self._tracks:
            del self._tracks[track_id]
            if self._active_id == track_id:
                self._active_id = self.all_ids()[0] if self._tracks else None

    def all_ids(self) -> List[str]:
        return list(self._tracks.keys())

    # ---- Active binding ----
    @property
    def active_id(self) -> Optional[str]:
        return self._active_id

    def set_active(self, track_id: str) -> None:
        track_id = str(track_id)

        # Don’t auto-create invalid IDs
        if not _is_uuid(track_id):
            raise ValueError(f"TrackManager.set_active() requires UUID track_id, got: {track_id!r}")

        if track_id not in self._tracks:
            self.ensure(track_id)

        self._active_id = track_id

    def get_active(self) -> TrackBundle:
        # If we already have a valid active id, use it
        if self._active_id and self._active_id in self._tracks:
            return self._tracks[self._active_id]

        # If no active id, but we have tracks, pick the first one deterministically
        if self._tracks:
            first_id = next(iter(self._tracks.keys()))
            self._active_id = first_id
            return self._tracks[first_id]

        # No tracks exist in memory — TrackManager must be seeded with a real DB UUID
        raise RuntimeError("TrackManager has no tracks. Seed it with a DB track id before calling get_active().")

    # ---- Unit handling ----
    def set_unit_value(self, v: float, for_all_tracks: bool = False) -> None:
        self._unit_value = float(v)
        if for_all_tracks:
            for b in self._tracks.values():
                b.set_unit_value(self._unit_value)
        else:
            # only active track by default
            if self._active_id and self._active_id in self._tracks:
                self._tracks[self._active_id].set_unit_value(self._unit_value)

    def get_unit_value(self) -> float:
        return self._unit_value

    # ============================================================
    #  Snapshot helpers — used by Supabase layer
    # ============================================================
    def export_snapshot(self) -> Dict[str, Any]:
        """
        Export a full snapshot of TrackManager:

          {
            "unit_value": 1.0,
            "active_id": "<uuid>",
            "tracks": {
               ""<uuid>"": { ... TrackBundle.export_state() ... },
               "Track 2": { ... },
               ...
            }
          }

        How you store it is up to you:
          • You may split tracks across rows in the `tracks` table
          • Or store this whole blob in one JSON column per user (admin tools, etc.)
        """
        return {
            "unit_value": float(self._unit_value),
            "active_id": self._active_id,
            "tracks": {
                tid: bundle.export_state()
                for tid, bundle in self._tracks.items()
            },
        }

    def load_snapshot(self, snap: Dict[str, Any]) -> None:
        """
        Rebuild TrackManager from a snapshot produced by export_snapshot().

        This does *not* talk to Supabase — pass in the already-fetched dict
        (e.g., decoded from JSON in a DB column).
        """
        if not isinstance(snap, dict):
            return

        # unit value
        try:
            self._unit_value = float(snap.get("unit_value", self._unit_value))
        except Exception:
            pass

        # tracks
        raw_tracks = snap.get("tracks") or {}
        self._tracks = {}
        if isinstance(raw_tracks, dict):
            for tid, tdata in raw_tracks.items():
                try:
                    bundle = TrackBundle(unit_value=self._unit_value)
                    if isinstance(tdata, dict):
                        bundle.load_state(tdata)
                    self._tracks[str(tid)] = bundle
                except Exception:
                    # skip any corrupt track instead of killing the whole load
                    continue

        # active id
        active = snap.get("active_id")
        active = str(active) if active is not None else None

        if active and active in self._tracks and _is_uuid(active):
            self._active_id = active
        else:
            # Prefer the first UUID track id if any exist
            uuid_ids = [tid for tid in self.all_ids() if _is_uuid(tid)]
            self._active_id = uuid_ids[0] if uuid_ids else None
