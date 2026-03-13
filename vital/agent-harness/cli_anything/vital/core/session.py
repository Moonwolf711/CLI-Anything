"""Session management with undo/redo for Vital CLI.

Maintains state across commands: the currently loaded preset, modification
history, and session persistence to JSON files.
"""

import json
import os
import copy
import time
from typing import Optional


class Session:
    """Stateful session for Vital preset editing with undo/redo."""

    MAX_UNDO = 100

    def __init__(self, session_path: Optional[str] = None):
        """Initialize a new session.

        Args:
            session_path: Optional path to load/save session state.
        """
        self.session_path = session_path
        self.preset: Optional[dict] = None
        self.preset_path: Optional[str] = None
        self.modified: bool = False
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._history: list[dict] = []
        self._created_at: float = time.time()

    @property
    def has_preset(self) -> bool:
        """Whether a preset is currently loaded."""
        return self.preset is not None

    @property
    def preset_name(self) -> str:
        """Name of the currently loaded preset."""
        if self.preset:
            return self.preset.get("preset_name", "Untitled")
        return ""

    def _push_undo(self, description: str):
        """Save current state to undo stack before a change."""
        if self.preset is None:
            return
        state = {
            "preset": copy.deepcopy(self.preset),
            "description": description,
            "timestamp": time.time(),
        }
        self._undo_stack.append(state)
        if len(self._undo_stack) > self.MAX_UNDO:
            self._undo_stack.pop(0)
        # Any new action clears the redo stack
        self._redo_stack.clear()

    def _record_action(self, action: str, details: dict = None):
        """Record an action in the session history."""
        entry = {
            "action": action,
            "timestamp": time.time(),
        }
        if details:
            entry["details"] = details
        self._history.append(entry)

    def load_preset(self, preset: dict, path: Optional[str] = None):
        """Load a preset into the session.

        Args:
            preset: Parsed preset dict.
            path: Optional file path the preset was loaded from.
        """
        self._push_undo("load preset")
        self.preset = copy.deepcopy(preset)
        self.preset_path = path
        self.modified = False
        self._record_action("load", {"path": path, "name": preset.get("preset_name", "")})

    def set_param(self, name: str, value: float, description: str = "") -> bool:
        """Set a parameter with undo support.

        Args:
            name: Parameter name.
            value: New value.
            description: Human-readable description of the change.

        Returns:
            True if successful.
        """
        if not self.has_preset:
            return False

        desc = description or f"set {name} = {value}"
        self._push_undo(desc)

        settings = self.preset.setdefault("settings", {})
        old_value = settings.get(name)
        settings[name] = value
        self.modified = True
        self._record_action("set_param", {"name": name, "old": old_value, "new": value})
        return True

    def set_params_bulk(self, params: dict[str, float], description: str = "") -> int:
        """Set multiple parameters with single undo point.

        Args:
            params: Dict of param_name -> value.
            description: Description of the bulk change.

        Returns:
            Number of parameters set.
        """
        if not self.has_preset:
            return 0

        desc = description or f"set {len(params)} parameters"
        self._push_undo(desc)

        settings = self.preset.setdefault("settings", {})
        count = 0
        for name, value in params.items():
            settings[name] = value
            count += 1

        if count > 0:
            self.modified = True
            self._record_action("set_params_bulk", {"count": count, "params": list(params.keys())})

        return count

    def undo(self) -> tuple[bool, str]:
        """Undo the last action.

        Returns:
            (success, description) tuple.
        """
        if not self._undo_stack:
            return False, "Nothing to undo"

        # Save current state to redo
        if self.preset is not None:
            self._redo_stack.append({
                "preset": copy.deepcopy(self.preset),
                "description": "redo point",
                "timestamp": time.time(),
            })

        state = self._undo_stack.pop()
        self.preset = state["preset"]
        self.modified = True
        desc = state["description"]
        self._record_action("undo", {"description": desc})
        return True, desc

    def redo(self) -> tuple[bool, str]:
        """Redo the last undone action.

        Returns:
            (success, description) tuple.
        """
        if not self._redo_stack:
            return False, "Nothing to redo"

        # Save current to undo
        if self.preset is not None:
            self._undo_stack.append({
                "preset": copy.deepcopy(self.preset),
                "description": "undo point",
                "timestamp": time.time(),
            })

        state = self._redo_stack.pop()
        self.preset = state["preset"]
        self.modified = True
        self._record_action("redo", {"description": state["description"]})
        return True, state["description"]

    def get_history(self, limit: int = 20) -> list[dict]:
        """Get recent session history.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of history entry dicts.
        """
        return self._history[-limit:]

    def status(self) -> dict:
        """Get current session status.

        Returns:
            Dict with session state summary.
        """
        return {
            "has_preset": self.has_preset,
            "preset_name": self.preset_name,
            "preset_path": self.preset_path,
            "modified": self.modified,
            "undo_depth": len(self._undo_stack),
            "redo_depth": len(self._redo_stack),
            "history_length": len(self._history),
            "param_count": len(self.preset.get("settings", {})) if self.preset else 0,
        }

    def save_session(self, path: Optional[str] = None) -> str:
        """Persist session state to a JSON file.

        Args:
            path: Override session file path.

        Returns:
            Path where session was saved.
        """
        save_path = path or self.session_path
        if save_path is None:
            save_path = os.path.join(os.path.expanduser("~"),
                                     ".cli-anything-vital", "session.json")

        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        state = {
            "preset": self.preset,
            "preset_path": self.preset_path,
            "modified": self.modified,
            "history": self._history[-50:],  # Keep last 50 history entries
            "saved_at": time.time(),
        }

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

        return save_path

    def restore_session(self, path: Optional[str] = None) -> bool:
        """Restore session state from a JSON file.

        Args:
            path: Override session file path.

        Returns:
            True if session was restored successfully.
        """
        load_path = path or self.session_path
        if load_path is None:
            load_path = os.path.join(os.path.expanduser("~"),
                                     ".cli-anything-vital", "session.json")

        if not os.path.isfile(load_path):
            return False

        try:
            with open(load_path, "r", encoding="utf-8") as f:
                state = json.load(f)

            self.preset = state.get("preset")
            self.preset_path = state.get("preset_path")
            self.modified = state.get("modified", False)
            self._history = state.get("history", [])
            self._undo_stack.clear()
            self._redo_stack.clear()
            return True
        except (json.JSONDecodeError, OSError):
            return False
