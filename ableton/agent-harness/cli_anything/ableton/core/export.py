"""Export operations for Ableton Live projects.

Handles saving .als files and exporting MIDI data.

Note: Ableton Live does not support headless audio rendering.
Audio export must be done within the Ableton GUI. This module
provides .als project export and MIDI file export functionality.
"""

import os
import struct
from typing import Optional

from ..utils import als_xml
from .session import Session
from . import clip as clip_mod


def export_als(
    session: Session,
    output_path: str,
    compress: bool = True,
    overwrite: bool = False,
) -> dict:
    """Export the project as an .als file.

    Args:
        session: The active session.
        output_path: Output file path.
        compress: Whether to gzip-compress (True for .als).
        overwrite: Whether to overwrite existing files.

    Returns:
        Dict with export result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(
            f"File already exists: {output_path} (use --overwrite to replace)"
        )

    saved_path = als_xml.write_als(session.root, output_path, compress=compress)
    file_size = os.path.getsize(saved_path)

    return {
        "status": "exported",
        "format": "als",
        "path": saved_path,
        "file_size": file_size,
        "compressed": compress,
    }


def export_xml(
    session: Session,
    output_path: str,
    overwrite: bool = False,
) -> dict:
    """Export the project as uncompressed XML (for debugging).

    Args:
        session: The active session.
        output_path: Output file path.
        overwrite: Whether to overwrite existing files.

    Returns:
        Dict with export result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(
            f"File already exists: {output_path} (use --overwrite to replace)"
        )

    saved_path = als_xml.write_als(session.root, output_path, compress=False)
    file_size = os.path.getsize(saved_path)

    return {
        "status": "exported",
        "format": "xml",
        "path": saved_path,
        "file_size": file_size,
        "compressed": False,
    }


def export_midi(
    session: Session,
    output_path: str,
    track_index: int,
    slot_index: int,
    overwrite: bool = False,
) -> dict:
    """Export a MIDI clip as a Standard MIDI File (.mid).

    Args:
        session: The active session.
        output_path: Output file path.
        track_index: Track index containing the MIDI clip.
        slot_index: Clip slot index.
        overwrite: Whether to overwrite existing files.

    Returns:
        Dict with export result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(
            f"File already exists: {output_path} (use --overwrite to replace)"
        )

    # Get notes from the clip
    notes = clip_mod.get_clip_notes(session, track_index, slot_index)
    if not notes:
        raise ValueError(
            f"No notes found in clip at track {track_index}, slot {slot_index}"
        )

    # Get tempo for time conversion
    transport = als_xml.get_transport(session.root)
    tempo = float(als_xml.get_value(transport, "Tempo", "120"))

    # Build MIDI file
    midi_data = _build_midi_file(notes, tempo=tempo)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(midi_data)

    file_size = os.path.getsize(output_path)

    return {
        "status": "exported",
        "format": "midi",
        "path": os.path.abspath(output_path),
        "file_size": file_size,
        "note_count": len(notes),
        "tempo": tempo,
    }


# ── MIDI file builder ───────────────────────────────────────────────

# Standard MIDI File (SMF) format 0 builder

TICKS_PER_BEAT = 480  # Standard resolution


def _build_midi_file(notes: list[dict], tempo: float = 120.0) -> bytes:
    """Build a Standard MIDI File (Type 0) from note data.

    Args:
        notes: List of note dicts with pitch, time, duration, velocity.
        tempo: Tempo in BPM.

    Returns:
        MIDI file bytes.
    """
    # Build track data
    track_events = []

    # Tempo event (meta event FF 51 03 at time 0)
    microseconds_per_beat = int(60_000_000 / tempo)
    tempo_bytes = microseconds_per_beat.to_bytes(3, "big")
    track_events.append((0, b"\xff\x51\x03" + tempo_bytes))

    # Convert notes to MIDI events
    midi_events = []
    for note in notes:
        tick_start = int(note["time"] * TICKS_PER_BEAT)
        tick_end = tick_start + int(note["duration"] * TICKS_PER_BEAT)
        velocity = note.get("velocity", 100)
        pitch = note["pitch"]

        # Note On (channel 0)
        midi_events.append((tick_start, bytes([0x90, pitch, velocity])))
        # Note Off (channel 0)
        midi_events.append((tick_end, bytes([0x80, pitch, 0])))

    # Sort by time (stable sort preserves note-off before note-on at same time)
    midi_events.sort(key=lambda e: e[0])

    # Add sorted events
    track_events.extend(midi_events)

    # End of track
    track_events.append((track_events[-1][0] if track_events else 0,
                         b"\xff\x2f\x00"))

    # Sort all events by time
    track_events.sort(key=lambda e: e[0])

    # Convert to delta times
    track_bytes = b""
    prev_tick = 0
    for tick, data in track_events:
        delta = tick - prev_tick
        track_bytes += _write_var_length(delta) + data
        prev_tick = tick

    # MThd header (format 0, 1 track, ticks per beat)
    header = b"MThd"
    header += struct.pack(">I", 6)        # Header length
    header += struct.pack(">HHH", 0, 1, TICKS_PER_BEAT)  # Format, tracks, division

    # MTrk chunk
    track_chunk = b"MTrk"
    track_chunk += struct.pack(">I", len(track_bytes))
    track_chunk += track_bytes

    return header + track_chunk


def _write_var_length(value: int) -> bytes:
    """Encode an integer as a MIDI variable-length quantity."""
    if value < 0:
        raise ValueError(f"Variable length value must be >= 0, got {value}")

    result = []
    result.append(value & 0x7F)
    value >>= 7

    while value > 0:
        result.append((value & 0x7F) | 0x80)
        value >>= 7

    result.reverse()
    return bytes(result)
