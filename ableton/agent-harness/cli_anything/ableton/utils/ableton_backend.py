"""Ableton Live backend — locates the Ableton installation and OSC bridge.

Unlike other CLI-Anything tools, Ableton Live has no headless CLI mode.
The backend provides:
1. Installation detection and path resolution
2. OSC bridge connection for live control of a running instance
3. .als file validation

The .als file manipulation is the primary "backend" — the real software's
format is manipulated directly.
"""

import os
import shutil
import struct
import socket
import time
from typing import Optional


# ── Ableton installation detection ──────────────────────────────────

# Common install paths by platform
_INSTALL_PATHS_WIN = [
    r"C:\ProgramData\Ableton\Live 12 Suite",
    r"C:\ProgramData\Ableton\Live 12 Standard",
    r"C:\ProgramData\Ableton\Live 12 Intro",
    r"C:\ProgramData\Ableton\Live 11 Suite",
    r"C:\ProgramData\Ableton\Live 11 Standard",
    r"C:\Program Files\Ableton\Live 12 Suite",
    r"C:\Program Files\Ableton\Live 11 Suite",
]

_INSTALL_PATHS_MAC = [
    "/Applications/Ableton Live 12 Suite.app",
    "/Applications/Ableton Live 12 Standard.app",
    "/Applications/Ableton Live 12 Intro.app",
    "/Applications/Ableton Live 11 Suite.app",
]


def find_ableton() -> Optional[str]:
    """Find the Ableton Live installation path.

    Returns:
        Path to the Ableton installation directory, or None.
    """
    import platform

    if platform.system() == "Windows":
        for path in _INSTALL_PATHS_WIN:
            if os.path.isdir(path):
                return path
    elif platform.system() == "Darwin":
        for path in _INSTALL_PATHS_MAC:
            if os.path.isdir(path):
                return path
    else:
        # Linux - check common flatpak/snap locations
        home = os.path.expanduser("~")
        for candidate in [
            os.path.join(home, ".wine", "drive_c", "ProgramData", "Ableton"),
            "/opt/ableton",
        ]:
            if os.path.isdir(candidate):
                return candidate

    return None


def find_midi_remote_scripts() -> Optional[str]:
    """Find the MIDI Remote Scripts directory.

    Returns:
        Path to MIDI Remote Scripts, or None.
    """
    ableton = find_ableton()
    if ableton is None:
        return None

    scripts_path = os.path.join(ableton, "Resources", "MIDI Remote Scripts")
    if os.path.isdir(scripts_path):
        return scripts_path

    return None


def find_user_library() -> Optional[str]:
    """Find the Ableton User Library path.

    Returns:
        Path to User Library, or None.
    """
    import platform

    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA", "")
        for ver in ["Live 12", "Live 11"]:
            path = os.path.join(appdata, "Ableton", ver, "User Library")
            if os.path.isdir(path):
                return path
    elif platform.system() == "Darwin":
        home = os.path.expanduser("~")
        for ver in ["Live 12", "Live 11"]:
            path = os.path.join(home, "Music", "Ableton", ver, "User Library")
            if os.path.isdir(path):
                return path

    return None


def get_install_info() -> dict:
    """Get comprehensive Ableton installation information.

    Returns:
        Dict with installation details.
    """
    ableton_path = find_ableton()
    scripts_path = find_midi_remote_scripts()
    user_lib = find_user_library()

    return {
        "installed": ableton_path is not None,
        "install_path": ableton_path,
        "midi_remote_scripts": scripts_path,
        "user_library": user_lib,
        "version": _detect_version(ableton_path) if ableton_path else None,
    }


def _detect_version(install_path: str) -> Optional[str]:
    """Try to detect the Ableton version from the install path."""
    base = os.path.basename(install_path)
    # Parse from directory name like "Live 12 Suite"
    parts = base.split()
    for i, p in enumerate(parts):
        if p.isdigit():
            edition = parts[i + 1] if i + 1 < len(parts) else "Unknown"
            return f"Live {p} {edition}"
    return base


# ── OSC Bridge ──────────────────────────────────────────────────────

class OscBridge:
    """Simple OSC client for sending messages to a running Ableton instance.

    Ableton can receive OSC via MIDI Remote Scripts that listen for OSC,
    or via dedicated OSC bridge software (like the ProducerMind bridge).
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9876):
        self.host = host
        self.port = port
        self._sock: Optional[socket.socket] = None

    @property
    def connected(self) -> bool:
        return self._sock is not None

    def connect(self) -> dict:
        """Connect to the OSC bridge.

        Returns:
            Dict with connection status.
        """
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Test connectivity by sending a ping
            self._sock.settimeout(2.0)
            return {
                "status": "connected",
                "host": self.host,
                "port": self.port,
            }
        except socket.error as e:
            self._sock = None
            return {
                "status": "error",
                "error": str(e),
                "host": self.host,
                "port": self.port,
            }

    def disconnect(self) -> None:
        """Close the OSC connection."""
        if self._sock:
            self._sock.close()
            self._sock = None

    def send(self, address: str, *args) -> dict:
        """Send an OSC message.

        Args:
            address: OSC address pattern (e.g., "/live/play").
            *args: OSC arguments (int, float, string).

        Returns:
            Dict with send result.
        """
        if not self._sock:
            return {"status": "error", "error": "Not connected"}

        try:
            msg = _build_osc_message(address, args)
            self._sock.sendto(msg, (self.host, self.port))
            return {
                "status": "sent",
                "address": address,
                "args": list(args),
            }
        except socket.error as e:
            return {
                "status": "error",
                "error": str(e),
                "address": address,
            }

    def status(self) -> dict:
        """Get current bridge connection status."""
        return {
            "connected": self.connected,
            "host": self.host,
            "port": self.port,
        }


def _build_osc_message(address: str, args: tuple) -> bytes:
    """Build a minimal OSC message.

    OSC message format:
    1. Address pattern (null-terminated, padded to 4-byte boundary)
    2. Type tag string (null-terminated, padded to 4-byte boundary)
    3. Arguments (each padded to 4-byte boundary)
    """
    # Encode address
    msg = _osc_string(address)

    # Build type tag string
    type_tags = ","
    arg_data = b""
    for arg in args:
        if isinstance(arg, int):
            type_tags += "i"
            arg_data += struct.pack(">i", arg)
        elif isinstance(arg, float):
            type_tags += "f"
            arg_data += struct.pack(">f", arg)
        elif isinstance(arg, str):
            type_tags += "s"
            arg_data += _osc_string(arg)
        elif isinstance(arg, bool):
            type_tags += "T" if arg else "F"

    msg += _osc_string(type_tags)
    msg += arg_data

    return msg


def _osc_string(s: str) -> bytes:
    """Encode a string as an OSC string (null-terminated, 4-byte aligned)."""
    encoded = s.encode("ascii") + b"\x00"
    # Pad to 4-byte boundary
    padding = (4 - len(encoded) % 4) % 4
    return encoded + b"\x00" * padding
