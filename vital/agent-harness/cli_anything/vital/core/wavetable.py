"""Vital wavetable management.

Handles wavetable operations: listing available wavetables, setting
wavetable frames, and working with wavetable data within presets.

Vital wavetables are 256 frames of 2048 samples each. They can be
stored as base64-encoded data within the preset JSON under the
"wavetables" key, or loaded from .vitaltable files.
"""

import base64
import json
import math
import os
import struct
from typing import Optional


# Vital wavetable constants
WAVETABLE_FRAMES = 257  # 0..256
WAVETABLE_SAMPLES_PER_FRAME = 2048


def list_wavetables(preset: dict) -> list[dict]:
    """List all wavetables in the preset.

    Vital presets can contain wavetable data for osc_1, osc_2, osc_3
    under the "wavetables" key.

    Args:
        preset: Loaded Vital preset dict.

    Returns:
        List of wavetable info dicts.
    """
    wavetables = preset.get("wavetables", [])
    results = []

    for i, wt in enumerate(wavetables):
        osc_name = f"osc_{i + 1}"
        info = {
            "index": i,
            "oscillator": osc_name,
            "name": wt.get("name", f"Wavetable {i + 1}"),
            "full_normalize": wt.get("full_normalize", True),
            "remove_all_dc": wt.get("remove_all_dc", False),
        }

        # Count groups/keyframes
        groups = wt.get("groups", [])
        info["groups"] = len(groups)

        total_components = 0
        for g in groups:
            components = g.get("components", [])
            total_components += len(components)
        info["components"] = total_components

        results.append(info)

    return results


def get_wavetable_frame(preset: dict, osc_index: int) -> int:
    """Get the current wavetable frame position for an oscillator.

    Args:
        preset: Loaded Vital preset dict.
        osc_index: Oscillator number (1, 2, or 3).

    Returns:
        Current frame position (0-256).
    """
    settings = preset.get("settings", {})
    return int(settings.get(f"osc_{osc_index}_wave_frame", 0))


def set_wavetable_frame(preset: dict, osc_index: int, frame: int) -> tuple[bool, str]:
    """Set the wavetable frame position for an oscillator.

    Args:
        preset: Preset dict to modify (in-place).
        osc_index: Oscillator number (1, 2, or 3).
        frame: Frame position (0-256).

    Returns:
        (success, error_message) tuple.
    """
    if osc_index < 1 or osc_index > 3:
        return False, f"Invalid oscillator index: {osc_index} (must be 1-3)"
    if frame < 0 or frame > 256:
        return False, f"Frame must be 0-256, got {frame}"

    settings = preset.setdefault("settings", {})
    settings[f"osc_{osc_index}_wave_frame"] = float(frame)
    return True, ""


def create_basic_wavetable(waveform: str = "saw") -> dict:
    """Create a basic wavetable with a standard waveform.

    Vital stores wavetable data as groups of components. This creates
    a simple single-group wavetable with the specified waveform type.

    Args:
        waveform: Waveform type ("sine", "saw", "square", "triangle").

    Returns:
        Wavetable dict ready to insert into a preset.
    """
    valid_waveforms = {"sine", "saw", "square", "triangle"}
    if waveform not in valid_waveforms:
        raise ValueError(f"Unknown waveform: {waveform}. Valid: {', '.join(valid_waveforms)}")

    # Generate waveform data
    samples = WAVETABLE_SAMPLES_PER_FRAME
    data = []
    for i in range(samples):
        t = i / samples
        if waveform == "sine":
            data.append(math.sin(2 * math.pi * t))
        elif waveform == "saw":
            data.append(2.0 * t - 1.0)
        elif waveform == "square":
            data.append(1.0 if t < 0.5 else -1.0)
        elif waveform == "triangle":
            data.append(4.0 * abs(t - 0.5) - 1.0)

    # Encode as Vital wavetable component
    wt = {
        "name": waveform.capitalize(),
        "full_normalize": True,
        "remove_all_dc": False,
        "groups": [
            {
                "components": [
                    {
                        "type": "Wave Source",
                        "interpolation": "None",
                        "interpolation_style": 0,
                        "name": waveform,
                    }
                ]
            }
        ],
    }

    return wt


def set_wavetable(preset: dict, osc_index: int, wavetable: dict) -> tuple[bool, str]:
    """Set the wavetable data for an oscillator.

    Args:
        preset: Preset dict to modify (in-place).
        osc_index: Oscillator number (1, 2, or 3).
        wavetable: Wavetable dict.

    Returns:
        (success, error_message) tuple.
    """
    if osc_index < 1 or osc_index > 3:
        return False, f"Invalid oscillator index: {osc_index} (must be 1-3)"

    wavetables = preset.setdefault("wavetables", [])

    # Extend the list if needed
    while len(wavetables) < osc_index:
        wavetables.append(create_basic_wavetable("saw"))

    wavetables[osc_index - 1] = wavetable
    return True, ""


def list_wavetable_files(directory: str) -> list[dict]:
    """List .vitaltable files in a directory.

    Args:
        directory: Directory to search.

    Returns:
        List of dicts with path and name for each wavetable file.
    """
    if not os.path.isdir(directory):
        return []

    results = []
    for root, dirs, files in os.walk(directory):
        for f in sorted(files):
            if f.endswith(".vitaltable"):
                fpath = os.path.join(root, f)
                name = os.path.splitext(f)[0]
                results.append({
                    "path": os.path.abspath(fpath),
                    "name": name,
                    "size": os.path.getsize(fpath),
                })

    return results


def load_wavetable_file(path: str) -> dict:
    """Load a wavetable from a .vitaltable file.

    Args:
        path: Path to the .vitaltable file.

    Returns:
        Wavetable dict.

    Raises:
        FileNotFoundError: If file does not exist.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Wavetable file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_wavetable_file(wavetable: dict, path: str) -> str:
    """Save a wavetable to a .vitaltable file.

    Args:
        wavetable: Wavetable dict.
        path: Output file path.

    Returns:
        Absolute path where file was saved.
    """
    if not path.endswith(".vitaltable"):
        path += ".vitaltable"

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(wavetable, f, indent=2)

    return os.path.abspath(path)
