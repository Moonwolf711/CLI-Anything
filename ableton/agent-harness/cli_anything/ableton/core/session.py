"""Stateful session management for the Ableton CLI.

A session tracks the currently open project, undo history, and working state.
Sessions persist to disk as JSON so they survive process restarts.
"""

import json
import os
import copy
import time
from pathlib import Path
from typing import Optional
from lxml import etree

from ..utils import als_xml


SESSION_DIR = Path.home() / ".cli-anything-ableton" / "sessions"
MAX_UNDO_DEPTH = 50


class Session:
    """Represents a stateful CLI editing session."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or f"session_{int(time.time())}"
        self.project_path: Optional[str] = None
        self.root: Optional[etree._Element] = None
        self._undo_stack: list[bytes] = []
        self._redo_stack: list[bytes] = []
        self._modified = False
        self._metadata: dict = {}

    @property
    def is_open(self) -> bool:
        return self.root is not None

    @property
    def is_modified(self) -> bool:
        return self._modified

    def _snapshot(self) -> bytes:
        """Capture current state for undo."""
        if self.root is None:
            return b""
        return als_xml.serialize_xml(self.root)

    def _push_undo(self) -> None:
        """Save current state to undo stack before a mutation."""
        snap = self._snapshot()
        if snap:
            self._undo_stack.append(snap)
            if len(self._undo_stack) > MAX_UNDO_DEPTH:
                self._undo_stack.pop(0)
            self._redo_stack.clear()

    def checkpoint(self) -> None:
        """Create a checkpoint before performing a mutation.

        Call this before any operation that changes the project.
        """
        self._push_undo()
        self._modified = True

    def undo(self) -> bool:
        """Undo the last operation. Returns True if successful."""
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._snapshot())
        prev = self._undo_stack.pop()
        self.root = als_xml.deserialize_xml(prev)
        self._modified = bool(self._undo_stack)
        return True

    def redo(self) -> bool:
        """Redo the last undone operation. Returns True if successful."""
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._snapshot())
        next_state = self._redo_stack.pop()
        self.root = als_xml.deserialize_xml(next_state)
        self._modified = True
        return True

    def new_project(self) -> None:
        """Create a new blank project in this session."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.root = als_xml.new_ableton_root()
        self.project_path = None
        self._modified = False

    def open_project(self, path: str) -> dict:
        """Open an existing .als project file.

        Args:
            path: Path to the .als file.

        Returns:
            Dict with project info.
        """
        self.root = als_xml.read_als(path)
        self.project_path = os.path.abspath(path)
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._modified = False

        return self.project_info()

    def save(self, path: Optional[str] = None) -> str:
        """Save the current project.

        Args:
            path: Output path. If None, saves to the original location.

        Returns:
            The absolute path of the saved file.

        Raises:
            RuntimeError: If no project is open or no path specified.
        """
        if self.root is None:
            raise RuntimeError("No project is open")

        save_path = path or self.project_path
        if save_path is None:
            raise RuntimeError("No save path specified (new project, use save-as)")

        result = als_xml.write_als(self.root, save_path)
        self.project_path = result
        self._modified = False
        return result

    def project_info(self) -> dict:
        """Get information about the currently open project.

        Returns:
            Dict with project metadata.
        """
        if self.root is None:
            return {"open": False}

        ls = als_xml.get_live_set(self.root)
        transport = als_xml.get_transport(self.root)
        tracks = als_xml.get_tracks_container(self.root)
        scenes = als_xml.get_scenes_container(self.root)

        # Count track types
        midi_count = len(tracks.findall("MidiTrack"))
        audio_count = len(tracks.findall("AudioTrack"))
        return_count = len(tracks.findall("ReturnTrack"))
        group_count = len(tracks.findall("GroupTrack"))
        total_tracks = midi_count + audio_count + return_count + group_count

        return {
            "open": True,
            "path": self.project_path,
            "modified": self._modified,
            "version": {
                "major": self.root.get("MajorVersion", "?"),
                "minor": self.root.get("MinorVersion", "?"),
                "creator": self.root.get("Creator", "?"),
            },
            "transport": {
                "tempo": als_xml.get_value(transport, "Tempo", "120"),
                "time_signature": (
                    f"{als_xml.get_value(transport, 'TimeSignatureNumerator', '4')}"
                    f"/{als_xml.get_value(transport, 'TimeSignatureDenominator', '4')}"
                ),
                "loop_on": als_xml.get_value(transport, "LoopOn", "false"),
            },
            "tracks": {
                "total": total_tracks,
                "midi": midi_count,
                "audio": audio_count,
                "return": return_count,
                "group": group_count,
            },
            "scenes": len(scenes.findall("Scene")),
            "undo_depth": len(self._undo_stack),
            "redo_depth": len(self._redo_stack),
        }

    def session_info(self) -> dict:
        """Get session status information."""
        return {
            "session_id": self.session_id,
            "project_open": self.is_open,
            "project_path": self.project_path,
            "modified": self._modified,
            "undo_depth": len(self._undo_stack),
            "redo_depth": len(self._redo_stack),
        }

    def persist(self) -> str:
        """Save session metadata to disk for later restoration.

        Returns:
            Path to the session file.
        """
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        session_file = SESSION_DIR / f"{self.session_id}.json"

        data = {
            "session_id": self.session_id,
            "project_path": self.project_path,
            "modified": self._modified,
            "timestamp": time.time(),
        }

        with open(session_file, "w") as f:
            json.dump(data, f, indent=2)

        return str(session_file)

    @classmethod
    def restore(cls, session_id: str) -> "Session":
        """Restore a session from disk.

        Args:
            session_id: The session ID to restore.

        Returns:
            A restored Session instance.
        """
        session_file = SESSION_DIR / f"{session_id}.json"
        if not session_file.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        with open(session_file) as f:
            data = json.load(f)

        session = cls(session_id=data["session_id"])
        if data.get("project_path") and os.path.exists(data["project_path"]):
            session.open_project(data["project_path"])

        return session
