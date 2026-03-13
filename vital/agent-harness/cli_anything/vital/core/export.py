"""Vital preset export and format conversion.

Handles exporting presets to various formats:
- .vital (native JSON format)
- .json (raw JSON dump)
- .fxp (VST preset format - basic wrapper)
- Parameter summary (text/markdown)

Since Vital is a synthesizer (not a DAW), the "rendering" concept
from HARNESS.md maps to: generating valid preset files that Vital
can load. The "real software" is Vital itself loading the preset.
"""

import json
import os
import copy
from typing import Optional

from cli_anything.vital.core.preset import save_preset


def export_preset(preset: dict, output_path: str,
                  fmt: str = "vital", overwrite: bool = False) -> dict:
    """Export a preset to the specified format.

    Args:
        preset: Preset dict to export.
        output_path: Output file path.
        fmt: Export format ("vital", "json", "summary").
        overwrite: Allow overwriting existing files.

    Returns:
        Result dict with output info.

    Raises:
        FileExistsError: If file exists and overwrite is False.
        ValueError: If format is unknown.
    """
    if not overwrite and os.path.exists(output_path):
        raise FileExistsError(f"File already exists: {output_path}")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    if fmt == "vital":
        result = save_preset(preset, output_path, overwrite=overwrite)
        result["format"] = "vital"
        return result

    elif fmt == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2)
        size = os.path.getsize(output_path)
        return {
            "path": os.path.abspath(output_path),
            "format": "json",
            "file_size": size,
        }

    elif fmt == "summary":
        text = _generate_summary(preset)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        size = os.path.getsize(output_path)
        return {
            "path": os.path.abspath(output_path),
            "format": "summary",
            "file_size": size,
        }

    else:
        raise ValueError(f"Unknown export format: {fmt}. Valid: vital, json, summary")


def export_settings_only(preset: dict, output_path: str,
                         overwrite: bool = False) -> dict:
    """Export only the settings dict (no metadata, wavetables, etc.).

    Useful for comparing parameter values or importing into other tools.

    Args:
        preset: Preset dict.
        output_path: Output file path.
        overwrite: Allow overwriting.

    Returns:
        Result dict.
    """
    if not overwrite and os.path.exists(output_path):
        raise FileExistsError(f"File already exists: {output_path}")

    settings = preset.get("settings", {})
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, sort_keys=True)

    size = os.path.getsize(output_path)
    return {
        "path": os.path.abspath(output_path),
        "format": "json_settings",
        "file_size": size,
        "param_count": len(settings),
    }


def _generate_summary(preset: dict) -> str:
    """Generate a human-readable text summary of a preset."""
    lines = []
    lines.append(f"Vital Preset Summary")
    lines.append(f"{'=' * 50}")
    lines.append(f"Name:    {preset.get('preset_name', 'Untitled')}")
    lines.append(f"Author:  {preset.get('author', '')}")
    lines.append(f"Style:   {preset.get('preset_style', '')}")
    lines.append(f"Notes:   {preset.get('comments', '')}")
    lines.append("")

    settings = preset.get("settings", {})

    # Global
    lines.append("Global")
    lines.append("-" * 30)
    lines.append(f"  Volume:     {settings.get('volume', 0.7)}")
    lines.append(f"  BPM:        {settings.get('beats_per_minute', 120)}")
    lines.append(f"  Polyphony:  {int(settings.get('polyphony', 8))}")
    lines.append(f"  Velocity:   {settings.get('velocity_track', 0.5)}")
    lines.append("")

    # Oscillators
    for i in range(1, 4):
        on = settings.get(f"osc_{i}_on", 0) > 0
        lines.append(f"Oscillator {i}: {'ON' if on else 'OFF'}")
        if on:
            lines.append(f"  Level:      {settings.get(f'osc_{i}_level', 0.7)}")
            lines.append(f"  Transpose:  {int(settings.get(f'osc_{i}_transpose', 0))}")
            lines.append(f"  Tune:       {settings.get(f'osc_{i}_tune', 0)}")
            lines.append(f"  Pan:        {settings.get(f'osc_{i}_pan', 0)}")
            lines.append(f"  Unison:     {int(settings.get(f'osc_{i}_unison_voices', 1))}")
            lines.append(f"  Detune:     {settings.get(f'osc_{i}_unison_detune', 2.2)}")
            lines.append(f"  Wave Frame: {int(settings.get(f'osc_{i}_wave_frame', 0))}")
        lines.append("")

    # Filters
    for i in range(1, 3):
        on = settings.get(f"filter_{i}_on", 0) > 0
        lines.append(f"Filter {i}: {'ON' if on else 'OFF'}")
        if on:
            lines.append(f"  Cutoff:     {settings.get(f'filter_{i}_cutoff', 60)}")
            lines.append(f"  Resonance:  {settings.get(f'filter_{i}_resonance', 0.2)}")
            lines.append(f"  Drive:      {settings.get(f'filter_{i}_drive', 0)}")
            lines.append(f"  Model:      {int(settings.get(f'filter_{i}_model', 0))}")
        lines.append("")

    # Envelopes
    for i in range(1, 7):
        a = settings.get(f"env_{i}_attack", 0.01)
        d = settings.get(f"env_{i}_decay", 0.5)
        s = settings.get(f"env_{i}_sustain", 0.7)
        r = settings.get(f"env_{i}_release", 0.3)
        lines.append(f"Envelope {i}: A={a} D={d} S={s} R={r}")

    lines.append("")

    # Effects
    lines.append("Effects")
    lines.append("-" * 30)
    for fx in ["chorus", "compressor", "delay", "distortion", "eq", "flanger", "phaser", "reverb"]:
        on = settings.get(f"{fx}_on", 0) > 0
        lines.append(f"  {fx.capitalize():12s} {'ON' if on else 'OFF'}")

    lines.append("")

    # Modulations
    modulations = preset.get("modulations", [])
    if modulations:
        lines.append(f"Modulations ({len(modulations)})")
        lines.append("-" * 30)
        for i, mod in enumerate(modulations):
            amt = settings.get(f"modulation_{i+1}_amount", 0)
            lines.append(f"  {i+1}. {mod.get('source', '?')} -> {mod.get('destination', '?')} ({amt})")

    return "\n".join(lines)
