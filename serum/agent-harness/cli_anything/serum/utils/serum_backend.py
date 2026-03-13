"""Serum backend discovery and validation.

Since Serum is a proprietary VST plugin (not a CLI tool), this module
handles finding the installed plugin files and validating the preset
directory structure. There is no headless rendering -- all operations
are file-based (preset parsing, wavetable management).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Known installation paths
# ---------------------------------------------------------------------------

SERUM1_VST3_PATHS = [
    Path("C:/Program Files/Common Files/VST3/Serum.vst3"),
    Path("C:/Program Files/Common Files/VST3/Serum_x64.dll"),
]

SERUM2_VST3_PATHS = [
    Path("C:/Program Files/Common Files/VST3/Serum2.vst3"),
]

SERUM1_PRESET_ROOT = Path.home() / "Documents" / "Xfer" / "Serum Presets"
SERUM2_PRESET_ROOT = Path.home() / "Documents" / "Xfer" / "Serum 2 Presets"
SERUM1_ONEDRIVE_ROOT = Path("D:/OneDrive/Documents/Xfer/Serum Presets")
SERUM2_ONEDRIVE_ROOT = Path("D:/OneDrive/Documents/Xfer/Serum 2 Presets")


def find_serum_installation() -> dict[str, Any]:
    """Detect Serum installation status.

    Returns a dict with:
        serum1_installed: bool
        serum2_installed: bool
        serum1_vst3_path: str or None
        serum2_vst3_path: str or None
        serum1_preset_dirs: list of existing preset directories
        serum2_preset_dirs: list of existing preset directories
        wavetable_dirs: list of existing wavetable directories
    """
    info: dict[str, Any] = {
        "serum1_installed": False,
        "serum2_installed": False,
        "serum1_vst3_path": None,
        "serum2_vst3_path": None,
        "serum1_preset_dirs": [],
        "serum2_preset_dirs": [],
        "wavetable_dirs": [],
    }

    # Check Serum 1 VST
    for p in SERUM1_VST3_PATHS:
        if p.exists():
            info["serum1_installed"] = True
            info["serum1_vst3_path"] = str(p)
            break

    # Check Serum 2 VST
    for p in SERUM2_VST3_PATHS:
        if p.exists():
            info["serum2_installed"] = True
            info["serum2_vst3_path"] = str(p)
            break

    # Check preset directories
    serum1_dirs = [
        SERUM1_PRESET_ROOT / "Presets",
        SERUM1_ONEDRIVE_ROOT / "Presets",
    ]
    for d in serum1_dirs:
        if d.is_dir():
            info["serum1_preset_dirs"].append(str(d))

    serum2_dirs = [
        SERUM2_PRESET_ROOT / "Presets",
        SERUM2_ONEDRIVE_ROOT / "Presets",
    ]
    for d in serum2_dirs:
        if d.is_dir():
            info["serum2_preset_dirs"].append(str(d))

    # Wavetable directories
    wt_dirs = [
        SERUM1_PRESET_ROOT / "Tables",
        SERUM1_ONEDRIVE_ROOT / "Tables",
        SERUM2_PRESET_ROOT / "Tables",
        SERUM2_ONEDRIVE_ROOT / "Tables",
    ]
    for d in wt_dirs:
        if d.is_dir():
            info["wavetable_dirs"].append(str(d))

    return info


def require_serum() -> dict[str, Any]:
    """Check that Serum is installed, raising if not.

    Returns installation info on success.

    Raises:
        RuntimeError: If neither Serum 1 nor Serum 2 is detected.
    """
    info = find_serum_installation()
    if not info["serum1_installed"] and not info["serum2_installed"]:
        raise RuntimeError(
            "Serum is not installed. Install Xfer Records Serum from:\n"
            "  https://xferrecords.com/products/serum\n\n"
            "Expected VST3 locations:\n"
            "  C:\\Program Files\\Common Files\\VST3\\Serum.vst3\n"
            "  C:\\Program Files\\Common Files\\VST3\\Serum2.vst3\n\n"
            "Note: This CLI operates on preset files, not the plugin directly.\n"
            "It works even without the plugin installed if preset files exist."
        )
    return info


def get_default_preset_dir(version: int = 1) -> Path:
    """Get the best available preset directory.

    Args:
        version: Serum version (1 or 2).

    Returns:
        Path to the preset directory.

    Raises:
        FileNotFoundError: If no preset directory exists.
    """
    if version == 1:
        candidates = [
            SERUM1_ONEDRIVE_ROOT / "Presets",
            SERUM1_PRESET_ROOT / "Presets",
        ]
    else:
        candidates = [
            SERUM2_ONEDRIVE_ROOT / "Presets",
            SERUM2_PRESET_ROOT / "Presets",
        ]

    for d in candidates:
        if d.is_dir():
            return d

    raise FileNotFoundError(
        f"No Serum {version} preset directory found. "
        "Check that Serum is installed and presets exist."
    )


def get_default_wavetable_dir() -> Path:
    """Get the best available wavetable directory."""
    candidates = [
        SERUM1_PRESET_ROOT / "Tables",
        SERUM1_ONEDRIVE_ROOT / "Tables",
        SERUM2_PRESET_ROOT / "Tables",
    ]
    for d in candidates:
        if d.is_dir():
            return d

    raise FileNotFoundError(
        "No wavetable directory found. "
        "Check that Serum is installed."
    )
