"""Serum CLI - Session management with undo/redo.

Maintains working state (loaded preset, parameter modifications)
with a snapshot-based undo/redo stack.
"""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class Session:
    """Manages preset editing state with undo/redo history."""

    MAX_UNDO = 50

    def __init__(self) -> None:
        self.preset: dict[str, Any] | None = None
        self.preset_path: str | None = None
        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []
        self._modified: bool = False

    def has_preset(self) -> bool:
        """Check if a preset is currently loaded."""
        return self.preset is not None

    def get_preset(self) -> dict[str, Any]:
        """Get the current preset, raising if none loaded."""
        if self.preset is None:
            raise RuntimeError(
                "No preset loaded. Use 'preset open <path>' or "
                "'preset create <path>' first."
            )
        return self.preset

    def set_preset(
        self, preset: dict[str, Any], path: str | None = None
    ) -> None:
        """Set the current preset, clearing history."""
        self.preset = preset
        self.preset_path = path
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._modified = False

    @property
    def modified(self) -> bool:
        return self._modified

    def snapshot(self, description: str = "") -> None:
        """Save current state to undo stack before a mutation."""
        if self.preset is None:
            return
        state = {
            "preset": copy.deepcopy(self.preset),
            "description": description,
            "timestamp": datetime.now().isoformat(),
        }
        self._undo_stack.append(state)
        if len(self._undo_stack) > self.MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._modified = True

    def undo(self) -> str:
        """Undo the last operation. Returns description of undone action."""
        if not self._undo_stack:
            raise RuntimeError("Nothing to undo.")
        if self.preset is None:
            raise RuntimeError("No preset loaded.")

        self._redo_stack.append({
            "preset": copy.deepcopy(self.preset),
            "description": "redo point",
            "timestamp": datetime.now().isoformat(),
        })

        state = self._undo_stack.pop()
        self.preset = state["preset"]
        self._modified = True
        return state.get("description", "")

    def redo(self) -> str:
        """Redo the last undone operation."""
        if not self._redo_stack:
            raise RuntimeError("Nothing to redo.")
        if self.preset is None:
            raise RuntimeError("No preset loaded.")

        self._undo_stack.append({
            "preset": copy.deepcopy(self.preset),
            "description": "undo point",
            "timestamp": datetime.now().isoformat(),
        })

        state = self._redo_stack.pop()
        self.preset = state["preset"]
        self._modified = True
        return state.get("description", "")

    def status(self) -> dict[str, Any]:
        """Get session status."""
        return {
            "has_preset": self.preset is not None,
            "preset_path": self.preset_path,
            "preset_name": (
                self.preset.get("name", "untitled") if self.preset else None
            ),
            "modified": self._modified,
            "undo_count": len(self._undo_stack),
            "redo_count": len(self._redo_stack),
        }

    def save_session(self, path: str | None = None) -> str:
        """Save the session state (preset + metadata) to a JSON file.

        This is not the same as saving the .fxp -- this saves the session
        workspace so it can be resumed later.
        """
        if self.preset is None:
            raise RuntimeError("No preset to save.")

        save_path = path or self.preset_path
        if not save_path:
            raise ValueError("No save path specified.")

        # If the path ends in .fxp, save as session JSON alongside it
        if save_path.endswith(".fxp"):
            save_path = save_path.rsplit(".", 1)[0] + ".session.json"

        session_data = {
            "preset": self.preset,
            "preset_path": self.preset_path,
            "modified": self._modified,
            "saved_at": datetime.now().isoformat(),
            "undo_count": len(self._undo_stack),
        }

        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, default=str)

        return save_path

    def load_session(self, path: str) -> None:
        """Load a previously saved session from JSON."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.preset = data.get("preset")
        self.preset_path = data.get("preset_path")
        self._modified = False
        self._undo_stack.clear()
        self._redo_stack.clear()

    def list_history(self) -> list[dict[str, str]]:
        """List undo history entries."""
        result = []
        for i, state in enumerate(reversed(self._undo_stack)):
            result.append({
                "index": i,
                "description": state.get("description", ""),
                "timestamp": state.get("timestamp", ""),
            })
        return result
