"""Vital preset management.

Handles creating, loading, saving, listing, searching, and exporting
Vital preset files (.vital). Presets are JSON files with a top-level
structure of: preset_name, author, comments, preset_style, settings.
"""

import json
import os
import copy
import glob
from typing import Optional

from cli_anything.vital.core.parameters import (
    PARAM_REGISTRY, get_param, validate_param_value,
)


# ── Default preset template ──────────────────────────────────────────

def _build_default_settings() -> dict:
    """Build a default settings dict with all parameters at defaults."""
    settings = {}
    for name, pdef in PARAM_REGISTRY.items():
        # Skip modulation slots by default (only include first few)
        if name.startswith("modulation_") and not name.startswith("modulation_1_"):
            continue
        settings[name] = pdef.default_val
    return settings


DEFAULT_SETTINGS = _build_default_settings()


def create_preset(name: str = "Init", author: str = "",
                  comments: str = "", style: str = "") -> dict:
    """Create a new default Vital preset.

    Args:
        name: Preset name.
        author: Author name.
        comments: Preset comments/notes.
        style: Preset style/category tag.

    Returns:
        Complete preset dict ready to save as .vital JSON.
    """
    preset = {
        "preset_name": name,
        "author": author,
        "comments": comments,
        "preset_style": style,
        "settings": copy.deepcopy(DEFAULT_SETTINGS),
    }
    # Enable osc_1 by default, disable others
    preset["settings"]["osc_1_on"] = 1.0
    preset["settings"]["osc_2_on"] = 0.0
    preset["settings"]["osc_3_on"] = 0.0
    return preset


def load_preset(path: str) -> dict:
    """Load a Vital preset from a .vital JSON file.

    Args:
        path: Path to the .vital file.

    Returns:
        Parsed preset dict.

    Raises:
        FileNotFoundError: If file does not exist.
        json.JSONDecodeError: If file is not valid JSON.
        ValueError: If file is missing required keys.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Preset file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        preset = json.load(f)

    # Validate structure
    if "settings" not in preset:
        raise ValueError(f"Invalid Vital preset (missing 'settings' key): {path}")

    # Ensure top-level keys exist
    preset.setdefault("preset_name", os.path.splitext(os.path.basename(path))[0])
    preset.setdefault("author", "")
    preset.setdefault("comments", "")
    preset.setdefault("preset_style", "")

    return preset


def save_preset(preset: dict, path: str, overwrite: bool = False) -> dict:
    """Save a Vital preset to a .vital JSON file.

    Args:
        preset: Preset dict to save.
        path: Output file path.
        overwrite: Allow overwriting existing files.

    Returns:
        Result dict with file info.

    Raises:
        FileExistsError: If file exists and overwrite is False.
        ValueError: If preset is missing required keys.
    """
    if not overwrite and os.path.exists(path):
        raise FileExistsError(f"File already exists: {path} (use --overwrite)")

    if "settings" not in preset:
        raise ValueError("Preset must contain a 'settings' key")

    # Ensure .vital extension
    if not path.endswith(".vital"):
        path += ".vital"

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(preset, f, indent=2)

    file_size = os.path.getsize(path)
    return {
        "path": os.path.abspath(path),
        "file_size": file_size,
        "preset_name": preset.get("preset_name", ""),
        "author": preset.get("author", ""),
        "param_count": len(preset["settings"]),
    }


def preset_info(preset: dict) -> dict:
    """Get summary info about a preset.

    Args:
        preset: Loaded preset dict.

    Returns:
        Dict with preset metadata and summary stats.
    """
    settings = preset.get("settings", {})

    # Count active components
    active_oscs = sum(1 for i in range(1, 4) if settings.get(f"osc_{i}_on", 0) > 0)
    active_filters = sum(1 for i in range(1, 3) if settings.get(f"filter_{i}_on", 0) > 0)
    filter_fx_on = settings.get("filter_fx_on", 0) > 0

    effects_status = {}
    for fx in ["chorus", "compressor", "delay", "distortion", "eq", "flanger", "phaser", "reverb"]:
        effects_status[fx] = settings.get(f"{fx}_on", 0) > 0

    active_effects = sum(1 for v in effects_status.values() if v)

    # Count non-zero modulations
    mod_count = 0
    for i in range(1, 65):
        if settings.get(f"modulation_{i}_amount", 0) != 0:
            mod_count += 1

    return {
        "preset_name": preset.get("preset_name", ""),
        "author": preset.get("author", ""),
        "comments": preset.get("comments", ""),
        "preset_style": preset.get("preset_style", ""),
        "param_count": len(settings),
        "active_oscillators": active_oscs,
        "active_filters": active_filters,
        "filter_fx_on": filter_fx_on,
        "effects": effects_status,
        "active_effects": active_effects,
        "modulation_count": mod_count,
        "polyphony": int(settings.get("polyphony", 8)),
        "volume": settings.get("volume", 0.7),
        "bpm": settings.get("beats_per_minute", 120.0),
        "sub_on": settings.get("sub_on", 0) > 0,
        "sample_on": settings.get("sample_on", 0) > 0,
    }


def get_param_value(preset: dict, param_name: str) -> tuple[bool, any, str]:
    """Get a parameter value from a preset.

    Args:
        preset: Loaded preset dict.
        param_name: Parameter name.

    Returns:
        (found, value, error_message) tuple.
    """
    settings = preset.get("settings", {})
    if param_name in settings:
        return True, settings[param_name], ""

    # Check if it's a known parameter with a default
    pdef = get_param(param_name)
    if pdef is not None:
        return True, pdef.default_val, ""

    return False, None, f"Unknown parameter: {param_name}"


def set_param_value(preset: dict, param_name: str, value: float,
                    validate: bool = True) -> tuple[bool, str]:
    """Set a parameter value in a preset.

    Args:
        preset: Preset dict to modify (in-place).
        param_name: Parameter name.
        value: New value.
        validate: Whether to validate against parameter ranges.

    Returns:
        (success, error_message) tuple.
    """
    if validate:
        valid, msg = validate_param_value(param_name, value)
        if not valid:
            return False, msg

    settings = preset.setdefault("settings", {})
    old_value = settings.get(param_name)
    settings[param_name] = value
    return True, ""


def set_params_bulk(preset: dict, params: dict[str, float],
                    validate: bool = True) -> tuple[int, list[str]]:
    """Set multiple parameters at once.

    Args:
        preset: Preset dict to modify (in-place).
        params: Dict of param_name -> value.
        validate: Whether to validate.

    Returns:
        (success_count, error_messages) tuple.
    """
    success = 0
    errors = []
    for name, value in params.items():
        ok, msg = set_param_value(preset, name, value, validate)
        if ok:
            success += 1
        else:
            errors.append(msg)
    return success, errors


def list_presets(directory: str, recursive: bool = True) -> list[dict]:
    """List all .vital preset files in a directory.

    Args:
        directory: Directory to search.
        recursive: Whether to search recursively.

    Returns:
        List of dicts with path, name, author, style for each preset.
    """
    if not os.path.isdir(directory):
        return []

    pattern = os.path.join(directory, "**", "*.vital") if recursive else os.path.join(directory, "*.vital")
    files = glob.glob(pattern, recursive=recursive)

    results = []
    for fpath in sorted(files):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            results.append({
                "path": os.path.abspath(fpath),
                "preset_name": data.get("preset_name", os.path.splitext(os.path.basename(fpath))[0]),
                "author": data.get("author", ""),
                "preset_style": data.get("preset_style", ""),
                "param_count": len(data.get("settings", {})),
            })
        except (json.JSONDecodeError, OSError):
            results.append({
                "path": os.path.abspath(fpath),
                "preset_name": os.path.splitext(os.path.basename(fpath))[0],
                "author": "",
                "preset_style": "",
                "param_count": 0,
                "error": "Failed to parse",
            })

    return results


def search_presets(directory: str, query: str, recursive: bool = True) -> list[dict]:
    """Search presets by name, author, or style.

    Args:
        directory: Directory to search in.
        query: Search string (case-insensitive).
        recursive: Whether to search recursively.

    Returns:
        List of matching preset info dicts.
    """
    q = query.lower()
    all_presets = list_presets(directory, recursive)
    return [
        p for p in all_presets
        if q in p.get("preset_name", "").lower()
        or q in p.get("author", "").lower()
        or q in p.get("preset_style", "").lower()
    ]


def compare_presets(preset_a: dict, preset_b: dict) -> dict:
    """Compare two presets and return differences.

    Args:
        preset_a: First preset.
        preset_b: Second preset.

    Returns:
        Dict with metadata_diffs and settings_diffs.
    """
    meta_diffs = {}
    for key in ["preset_name", "author", "comments", "preset_style"]:
        va = preset_a.get(key, "")
        vb = preset_b.get(key, "")
        if va != vb:
            meta_diffs[key] = {"a": va, "b": vb}

    settings_a = preset_a.get("settings", {})
    settings_b = preset_b.get("settings", {})
    all_keys = sorted(set(settings_a.keys()) | set(settings_b.keys()))

    settings_diffs = {}
    for key in all_keys:
        va = settings_a.get(key)
        vb = settings_b.get(key)
        if va != vb:
            settings_diffs[key] = {"a": va, "b": vb}

    return {
        "metadata_diffs": meta_diffs,
        "settings_diffs": settings_diffs,
        "total_diffs": len(meta_diffs) + len(settings_diffs),
    }


def merge_presets(base: dict, overlay: dict, keys: Optional[list[str]] = None) -> dict:
    """Merge overlay settings into base preset.

    Args:
        base: Base preset (not modified).
        overlay: Overlay preset whose settings take precedence.
        keys: If provided, only merge these specific settings keys.

    Returns:
        New merged preset dict.
    """
    result = copy.deepcopy(base)
    overlay_settings = overlay.get("settings", {})

    if keys:
        for k in keys:
            if k in overlay_settings:
                result["settings"][k] = overlay_settings[k]
    else:
        result["settings"].update(overlay_settings)

    return result
