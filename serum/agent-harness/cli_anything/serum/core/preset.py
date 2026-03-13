"""Preset management -- browse, search, organize, duplicate Serum presets.

Works with both Serum 1 (.fxp) and Serum 2 (.SerumPreset) files.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from pathlib import Path
from typing import Any

from cli_anything.serum.core.fxp import read_fxp, validate_fxp

# ---------------------------------------------------------------------------
# Known preset locations (Windows paths)
# ---------------------------------------------------------------------------

SERUM1_PRESET_DIRS: list[Path] = [
    Path.home() / "Documents" / "Xfer" / "Serum Presets" / "Presets",
    Path("D:/OneDrive/Documents/Xfer/Serum Presets/Presets"),
]

SERUM2_PRESET_DIRS: list[Path] = [
    Path.home() / "Documents" / "Xfer" / "Serum 2 Presets" / "Presets",
    Path("D:/OneDrive/Documents/Xfer/Serum 2 Presets/Presets"),
]

WAVETABLE_DIRS: list[Path] = [
    Path.home() / "Documents" / "Xfer" / "Serum Presets" / "Tables",
    Path("D:/OneDrive/Documents/Xfer/Serum Presets/Tables"),
    Path.home() / "Documents" / "Xfer" / "Serum 2 Presets" / "Tables",
]


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def find_preset_dirs() -> list[dict[str, Any]]:
    """Find all available Serum preset directories.

    Returns a list of dicts with: path, exists, version (1 or 2), preset_count.
    """
    result = []
    for d in SERUM1_PRESET_DIRS:
        info: dict[str, Any] = {
            "path": str(d),
            "exists": d.is_dir(),
            "version": 1,
            "preset_count": 0,
        }
        if d.is_dir():
            info["preset_count"] = sum(1 for _ in d.rglob("*.fxp"))
        result.append(info)

    for d in SERUM2_PRESET_DIRS:
        info = {
            "path": str(d),
            "exists": d.is_dir(),
            "version": 2,
            "preset_count": 0,
        }
        if d.is_dir():
            info["preset_count"] = sum(1 for _ in d.rglob("*.SerumPreset"))
        result.append(info)

    return result


def scan_presets(
    root: str | Path | None = None,
    pattern: str = "*.fxp",
    recursive: bool = True,
) -> list[dict[str, Any]]:
    """Scan a directory for preset files.

    Args:
        root: Directory to scan. If None, scans all known preset dirs.
        pattern: Glob pattern (default "*.fxp").
        recursive: Whether to search subdirectories.

    Returns:
        List of dicts with: path, name, folder, size, modified.
    """
    results: list[dict[str, Any]] = []

    if root is not None:
        roots = [Path(root)]
    else:
        if pattern == "*.fxp":
            roots = [d for d in SERUM1_PRESET_DIRS if d.is_dir()]
        elif pattern == "*.SerumPreset":
            roots = [d for d in SERUM2_PRESET_DIRS if d.is_dir()]
        else:
            roots = [d for d in SERUM1_PRESET_DIRS + SERUM2_PRESET_DIRS if d.is_dir()]

    for r in roots:
        r = Path(r)
        if not r.is_dir():
            continue
        glob_func = r.rglob if recursive else r.glob
        for p in sorted(glob_func(pattern)):
            try:
                stat = p.stat()
                results.append({
                    "path": str(p),
                    "name": p.stem,
                    "folder": str(p.parent.relative_to(r)) if _is_relative(p, r) else str(p.parent),
                    "extension": p.suffix,
                    "size": stat.st_size,
                    "modified": time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)
                    ),
                })
            except OSError:
                continue

    return results


def search_presets(
    query: str,
    root: str | Path | None = None,
    pattern: str = "*.fxp",
) -> list[dict[str, Any]]:
    """Search presets by name substring (case-insensitive).

    Args:
        query: Search string to match against preset names.
        root: Directory to search. If None, searches all known dirs.
        pattern: Glob pattern.

    Returns:
        List of matching preset info dicts.
    """
    all_presets = scan_presets(root=root, pattern=pattern, recursive=True)
    query_lower = query.lower()
    return [p for p in all_presets if query_lower in p["name"].lower()]


def preset_info(path: str | Path) -> dict[str, Any]:
    """Get detailed info about a single preset file.

    For .fxp files, parses the binary header and extracts parameters.
    For .SerumPreset files, returns file metadata only (parsing requires
    optional deps cbor2/zstandard).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Preset not found: {path}")

    stat = path.stat()
    info: dict[str, Any] = {
        "path": str(path),
        "name": path.stem,
        "extension": path.suffix,
        "size": stat.st_size,
        "modified": time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)
        ),
    }

    if path.suffix.lower() == ".fxp":
        try:
            fxp = read_fxp(path)
            info["format"] = "Serum 1 FXP"
            info["program_name"] = fxp["name"]
            info["fx_id"] = fxp["fx_id"]
            info["version"] = fxp["version"]
            info["compressed_size"] = fxp["compressed_size"]
            info["raw_size"] = fxp["raw_size"]
            info["param_count"] = fxp["param_count"]
            # Extract key musical params
            params = fxp["params"]
            info["summary"] = _summarize_fxp_params(params)
        except (ValueError, OSError) as exc:
            info["format"] = "Serum 1 FXP (parse error)"
            info["error"] = str(exc)

    elif path.suffix.lower() == ".serumpreset":
        info["format"] = "Serum 2 SerumPreset"
        # Check magic bytes
        try:
            with open(path, "rb") as f:
                magic = f.read(9)
            if magic == b"XferJson\x00":
                info["magic_valid"] = True
            else:
                info["magic_valid"] = False
                info["magic_bytes"] = magic.hex()
        except OSError as exc:
            info["error"] = str(exc)
    else:
        info["format"] = "Unknown"

    return info


def duplicate_preset(
    source: str | Path,
    dest: str | Path | None = None,
    new_name: str | None = None,
) -> str:
    """Duplicate a preset file.

    Args:
        source: Source preset path.
        dest: Destination path. If None, creates a copy in the same dir.
        new_name: New preset name (stem only). Auto-appended to same dir if
                  dest is None.

    Returns:
        Path to the new file.
    """
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")

    if dest is None:
        stem = new_name or f"{source.stem} - Copy"
        dest = source.parent / f"{stem}{source.suffix}"
    else:
        dest = Path(dest)

    # Avoid overwriting
    if dest.exists():
        counter = 2
        base = dest.stem
        while dest.exists():
            dest = dest.parent / f"{base} ({counter}){dest.suffix}"
            counter += 1

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(dest))
    return str(dest)


def find_duplicates(
    root: str | Path | None = None,
    pattern: str = "*.fxp",
) -> list[list[dict[str, Any]]]:
    """Find duplicate presets by file content hash.

    Returns a list of groups, where each group is a list of
    dicts with: path, name, size, hash.
    """
    presets = scan_presets(root=root, pattern=pattern, recursive=True)

    hash_map: dict[str, list[dict[str, Any]]] = {}
    for p in presets:
        try:
            fpath = Path(p["path"])
            content = fpath.read_bytes()
            h = hashlib.md5(content).hexdigest()
            entry = {
                "path": p["path"],
                "name": p["name"],
                "size": p["size"],
                "hash": h,
            }
            hash_map.setdefault(h, []).append(entry)
        except OSError:
            continue

    return [group for group in hash_map.values() if len(group) > 1]


def organize_by_category(
    root: str | Path,
    dest: str | Path,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """Organize presets into category folders based on name prefixes.

    Common Serum naming: "BA - name" (Bass), "LD - name" (Lead), etc.

    Args:
        root: Source directory.
        dest: Destination root directory.
        dry_run: If True, just report what would happen.

    Returns:
        List of action dicts: source, dest, category.
    """
    CATEGORY_PREFIXES = {
        "BA": "Bass",
        "BS": "Bass",
        "LD": "Lead",
        "PD": "Pad",
        "PL": "Pluck",
        "SY": "Synth",
        "FX": "Effects",
        "SFX": "Effects",
        "ARP": "Arp",
        "SEQ": "Sequence",
        "KEY": "Keys",
        "KY": "Keys",
        "AT": "Atmosphere",
        "CH": "Chord",
        "DRM": "Drums",
        "DR": "Drums",
        "GT": "Growl",
        "GR": "Growl",
        "ML": "Melody",
        "SUB": "Sub",
        "VOX": "Vocal",
        "VO": "Vocal",
    }

    actions: list[dict[str, Any]] = []
    root = Path(root)
    dest = Path(dest)

    for p in sorted(root.rglob("*.fxp")):
        name = p.stem
        category = "Uncategorized"

        # Try to match prefix (e.g., "BA - Heavy Sub" -> "Bass")
        for prefix, cat in sorted(CATEGORY_PREFIXES.items(), key=lambda x: -len(x[0])):
            if name.upper().startswith(prefix + " ") or name.upper().startswith(prefix + "-"):
                category = cat
                break

        target = dest / category / p.name
        actions.append({
            "source": str(p),
            "dest": str(target),
            "category": category,
            "name": name,
        })

        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(p), str(target))

    return actions


# ---------------------------------------------------------------------------
# Wavetable operations
# ---------------------------------------------------------------------------

def scan_wavetables(root: str | Path | None = None) -> list[dict[str, Any]]:
    """Scan for wavetable .wav files.

    Returns list of dicts: path, name, folder, size, modified.
    """
    results: list[dict[str, Any]] = []

    if root is not None:
        roots = [Path(root)]
    else:
        roots = [d for d in WAVETABLE_DIRS if d.is_dir()]

    for r in roots:
        if not r.is_dir():
            continue
        for p in sorted(r.rglob("*.wav")):
            try:
                stat = p.stat()
                results.append({
                    "path": str(p),
                    "name": p.stem,
                    "folder": str(p.parent.relative_to(r)) if _is_relative(p, r) else str(p.parent),
                    "size": stat.st_size,
                    "modified": time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)
                    ),
                })
            except OSError:
                continue

    return results


def wavetable_info(path: str | Path) -> dict[str, Any]:
    """Get info about a wavetable .wav file.

    Reads the WAV header to extract sample rate, bit depth, channels,
    and calculates the number of wavetable frames (each frame = 2048 samples).
    """
    import struct as st

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Wavetable not found: {path}")

    info: dict[str, Any] = {
        "path": str(path),
        "name": path.stem,
        "size": path.stat().st_size,
    }

    try:
        with open(path, "rb") as f:
            # RIFF header
            riff = f.read(4)
            if riff != b"RIFF":
                info["error"] = "Not a valid WAV file (no RIFF header)"
                return info

            file_size = st.unpack("<I", f.read(4))[0]
            wave = f.read(4)
            if wave != b"WAVE":
                info["error"] = "Not a valid WAV file (no WAVE marker)"
                return info

            # Find fmt chunk
            while True:
                chunk_id = f.read(4)
                if len(chunk_id) < 4:
                    break
                chunk_size = st.unpack("<I", f.read(4))[0]
                if chunk_id == b"fmt ":
                    fmt_data = f.read(chunk_size)
                    audio_fmt = st.unpack_from("<H", fmt_data, 0)[0]
                    channels = st.unpack_from("<H", fmt_data, 2)[0]
                    sample_rate = st.unpack_from("<I", fmt_data, 4)[0]
                    bits_per_sample = st.unpack_from("<H", fmt_data, 14)[0]
                    info["audio_format"] = audio_fmt
                    info["channels"] = channels
                    info["sample_rate"] = sample_rate
                    info["bits_per_sample"] = bits_per_sample
                elif chunk_id == b"data":
                    data_size = chunk_size
                    info["data_size"] = data_size
                    bytes_per_sample = info.get("bits_per_sample", 16) // 8
                    total_samples = data_size // (bytes_per_sample * info.get("channels", 1))
                    info["total_samples"] = total_samples
                    # Serum wavetables: 2048 samples per frame
                    info["frame_size"] = 2048
                    info["num_frames"] = total_samples // 2048
                    info["duration_sec"] = round(
                        total_samples / info.get("sample_rate", 44100), 4
                    )
                    break
                else:
                    f.seek(chunk_size, 1)

    except (OSError, st.error) as exc:
        info["error"] = str(exc)

    return info


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_relative(child: Path, parent: Path) -> bool:
    """Check if child is relative to parent without raising."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _summarize_fxp_params(params: list[float]) -> dict[str, Any]:
    """Extract a human-readable summary from FXP parameter values.

    Uses current virtual indices from PARAM_MAP / PARAM_NAME_TO_INDEX.
    """
    from cli_anything.serum.core.fxp import PARAM_NAME_TO_INDEX

    def _v(name: str) -> float:
        idx = PARAM_NAME_TO_INDEX.get(name)
        if idx is not None and idx < len(params):
            return params[idx]
        return 0.0

    summary: dict[str, Any] = {}

    # Oscillator A
    summary["osc_a"] = {
        "enabled": _v("osc_a_enable") > 0.5,
        "volume": round(_v("osc_a_volume"), 3),
        "wave_pos": round(_v("osc_a_wave_pos"), 3),
    }

    # Oscillator B
    summary["osc_b"] = {
        "enabled": _v("osc_b_enable") > 0.5,
        "volume": round(_v("osc_b_volume"), 3),
    }

    # Filter 1
    summary["filter"] = {
        "enabled": _v("filter1_enable") > 0.5,
        "cutoff": round(_v("filter1_cutoff"), 3),
        "resonance": round(_v("filter1_resonance"), 3),
    }

    # Envelope 1
    summary["env1"] = {
        "attack": round(_v("env1_attack"), 3),
        "decay": round(_v("env1_decay"), 3),
        "sustain": round(_v("env1_sustain"), 3),
        "release": round(_v("env1_release"), 3),
    }

    # Master
    summary["master"] = {
        "volume": round(_v("master_volume"), 3),
    }

    # Effects (list enabled ones)
    effects = []
    fx_checks = [
        ("fx_hyper_enable", "Hyper/Dimension"),
        ("fx_dist_enable", "Distortion"),
        ("fx_flanger_enable", "Flanger"),
        ("fx_phaser_enable", "Phaser"),
        ("fx_chorus_enable", "Chorus"),
        ("fx_delay_enable", "Delay"),
        ("fx_comp_enable", "Compressor"),
        ("fx_multicomp_enable", "Multiband Comp"),
        ("fx_eq_enable", "EQ"),
        ("fx_reverb_enable", "Reverb"),
    ]
    for param_name, label in fx_checks:
        if _v(param_name) > 0.5:
            effects.append(label)
    summary["active_effects"] = effects

    return summary
