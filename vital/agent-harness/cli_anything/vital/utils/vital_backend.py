"""Vital backend: locate and interact with the Vital synthesizer.

Vital is a wavetable synth. Unlike DAWs or editors, it does not have
a headless CLI rendering mode. The "backend" for this CLI is the Vital
data layer: config files, preset files, wavetable files, and the
installed plugin (VST3/CLAP).

This module provides:
- Finding Vital installation (VST3, CLAP, standalone)
- Locating user data directory
- Reading/writing Vital config
- Validating preset files by checking JSON structure
"""

import json
import os
import platform
import shutil
from typing import Optional


def _platform_vital_paths() -> dict:
    """Get platform-specific Vital paths."""
    system = platform.system()

    if system == "Windows":
        appdata = os.environ.get("APPDATA", os.path.expanduser("~/AppData/Roaming"))
        return {
            "config_dir": os.path.join(appdata, "vital"),
            "vst3_paths": [
                os.path.join(os.environ.get("COMMONPROGRAMFILES", "C:\\Program Files\\Common Files"),
                             "VST3", "Vital.vst3"),
            ],
            "clap_paths": [
                os.path.join(os.environ.get("COMMONPROGRAMFILES", "C:\\Program Files\\Common Files"),
                             "CLAP", "Vital.clap"),
            ],
            "standalone_names": ["Vital.exe"],
        }
    elif system == "Darwin":
        home = os.path.expanduser("~")
        return {
            "config_dir": os.path.join(home, "Library", "Application Support", "vital"),
            "vst3_paths": [
                os.path.join(home, "Library", "Audio", "Plug-Ins", "VST3", "Vital.vst3"),
                "/Library/Audio/Plug-Ins/VST3/Vital.vst3",
            ],
            "clap_paths": [
                os.path.join(home, "Library", "Audio", "Plug-Ins", "CLAP", "Vital.clap"),
            ],
            "standalone_names": ["Vital"],
        }
    else:  # Linux
        home = os.path.expanduser("~")
        return {
            "config_dir": os.path.join(home, ".local", "share", "vital"),
            "vst3_paths": [
                os.path.join(home, ".vst3", "Vital.vst3"),
                "/usr/lib/vst3/Vital.vst3",
                "/usr/local/lib/vst3/Vital.vst3",
            ],
            "clap_paths": [
                os.path.join(home, ".clap", "Vital.clap"),
                "/usr/lib/clap/Vital.clap",
            ],
            "standalone_names": ["vital", "Vital"],
        }


def find_vital() -> dict:
    """Find Vital installation on this system.

    Returns:
        Dict with found paths and installation status.

    Raises:
        RuntimeError: If Vital is not found at all.
    """
    paths = _platform_vital_paths()
    result = {
        "installed": False,
        "config_dir": paths["config_dir"],
        "config_exists": os.path.isdir(paths["config_dir"]),
        "vst3": None,
        "clap": None,
        "standalone": None,
    }

    # Check VST3
    for vst_path in paths["vst3_paths"]:
        if os.path.exists(vst_path):
            result["vst3"] = vst_path
            result["installed"] = True
            break

    # Check CLAP
    for clap_path in paths["clap_paths"]:
        if os.path.exists(clap_path):
            result["clap"] = clap_path
            result["installed"] = True
            break

    # Check standalone
    for name in paths["standalone_names"]:
        exe = shutil.which(name)
        if exe:
            result["standalone"] = exe
            result["installed"] = True
            break

    if not result["installed"] and not result["config_exists"]:
        raise RuntimeError(
            "Vital is not installed. Install it from:\n"
            "  https://vital.audio/\n"
            "  - Download the installer for your platform\n"
            "  - Or build from source: https://github.com/mtytel/vital"
        )

    return result


def get_config_dir() -> str:
    """Get the Vital config directory path."""
    paths = _platform_vital_paths()
    return paths["config_dir"]


def get_data_dir() -> Optional[str]:
    """Get the Vital user data directory (presets, wavetables, etc.).

    Reads from Vital.config to find the configured data directory.

    Returns:
        Path to data directory, or None if not configured.
    """
    config_path = os.path.join(get_config_dir(), "Vital.config")
    if not os.path.isfile(config_path):
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("data_directory")
    except (json.JSONDecodeError, OSError):
        return None


def get_presets_dir() -> Optional[str]:
    """Get the default presets directory.

    Returns:
        Path to presets directory, or None if not found.
    """
    data_dir = get_data_dir()
    if data_dir and os.path.isdir(data_dir):
        return data_dir

    # Fallback: check config dir for presets
    config_dir = get_config_dir()
    presets_dir = os.path.join(config_dir, "presets")
    if os.path.isdir(presets_dir):
        return presets_dir

    return data_dir  # Return configured dir even if it doesn't exist yet


def read_config() -> dict:
    """Read the Vital.config file.

    Returns:
        Config dict, or empty dict if not found.
    """
    config_path = os.path.join(get_config_dir(), "Vital.config")
    if not os.path.isfile(config_path):
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def read_favorites() -> dict:
    """Read the Vital.favorites file.

    Returns:
        Favorites dict, or empty dict if not found.
    """
    fav_path = os.path.join(get_config_dir(), "Vital.favorites")
    if not os.path.isfile(fav_path):
        return {}

    try:
        with open(fav_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def read_library() -> dict:
    """Read the Vital.library file.

    Returns:
        Library dict with author_cache, date_cache, style_cache.
    """
    lib_path = os.path.join(get_config_dir(), "Vital.library")
    if not os.path.isfile(lib_path):
        return {}

    try:
        with open(lib_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def validate_preset_file(path: str) -> tuple[bool, str]:
    """Validate that a file is a valid Vital preset.

    Args:
        path: Path to the file.

    Returns:
        (is_valid, error_message) tuple.
    """
    if not os.path.isfile(path):
        return False, f"File not found: {path}"

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except OSError as e:
        return False, f"Cannot read file: {e}"

    if not isinstance(data, dict):
        return False, "Top-level element is not a JSON object"

    if "settings" not in data:
        return False, "Missing 'settings' key"

    settings = data["settings"]
    if not isinstance(settings, dict):
        return False, "'settings' is not a JSON object"

    # Check for some expected keys
    expected = ["volume", "polyphony"]
    for key in expected:
        if key not in settings:
            return False, f"Missing expected setting: {key}"

    return True, ""


def get_install_info() -> dict:
    """Get comprehensive Vital installation information.

    Returns:
        Dict with all installation details.
    """
    try:
        vital = find_vital()
    except RuntimeError:
        vital = {
            "installed": False,
            "config_dir": get_config_dir(),
            "config_exists": os.path.isdir(get_config_dir()),
            "vst3": None,
            "clap": None,
            "standalone": None,
        }

    config = read_config()
    library = read_library()

    result = {
        "installed": vital["installed"],
        "vst3": vital.get("vst3"),
        "clap": vital.get("clap"),
        "standalone": vital.get("standalone"),
        "config_dir": vital["config_dir"],
        "data_dir": get_data_dir(),
        "presets_dir": get_presets_dir(),
        "version": config.get("synth_version", "unknown"),
        "author": config.get("author", ""),
        "library_presets": len(library.get("author_cache", {})),
    }

    return result
