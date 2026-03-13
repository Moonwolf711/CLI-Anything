"""Clip management operations for Ableton Live projects.

Handles creating, editing, and querying MIDI and audio clips.
"""

from lxml import etree
from typing import Optional

from ..utils import als_xml
from .session import Session


def list_clips(session: Session, track_index: Optional[int] = None) -> list[dict]:
    """List all clips in the project, optionally filtered by track.

    Args:
        session: The active session.
        track_index: If specified, only list clips from this track.

    Returns:
        List of clip info dicts.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    tracks = als_xml.get_tracks_container(session.root)
    result = []

    for t_idx, track in enumerate(tracks):
        if track_index is not None and t_idx != track_index:
            continue

        # Get track name
        track_name = _get_track_name(track)

        dc = track.find("DeviceChain")
        if dc is None:
            continue

        main_seq = dc.find("MainSequencer")
        if main_seq is None:
            continue

        clip_slot_list = main_seq.find("ClipSlotList")
        if clip_slot_list is None:
            continue

        for slot_idx, cs in enumerate(clip_slot_list):
            clip_info = _extract_clip_from_slot(cs, t_idx, track_name, slot_idx)
            if clip_info is not None:
                result.append(clip_info)

    return result


def create_midi_clip(
    session: Session,
    track_index: int,
    slot_index: int,
    name: str = "MIDI Clip",
    length: float = 4.0,
    color: int = 0,
) -> dict:
    """Create a new empty MIDI clip in a clip slot.

    Args:
        session: The active session.
        track_index: Track index.
        slot_index: Clip slot (scene) index.
        name: Clip name.
        length: Clip length in beats.
        color: Clip color index.

    Returns:
        Dict with clip info.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    tracks = als_xml.get_tracks_container(session.root)
    track_list = list(tracks)

    if track_index < 0 or track_index >= len(track_list):
        raise IndexError(f"Track index {track_index} out of range")

    track_el = track_list[track_index]
    if track_el.tag != "MidiTrack":
        raise ValueError(
            f"Track {track_index} is a {track_el.tag}, not a MidiTrack. "
            "MIDI clips can only be created on MIDI tracks."
        )

    session.checkpoint()

    # Navigate to clip slot
    dc = track_el.find("DeviceChain")
    if dc is None:
        dc = etree.SubElement(track_el, "DeviceChain")

    main_seq = dc.find("MainSequencer")
    if main_seq is None:
        main_seq = etree.SubElement(dc, "MainSequencer")

    clip_slot_list = main_seq.find("ClipSlotList")
    if clip_slot_list is None:
        clip_slot_list = etree.SubElement(main_seq, "ClipSlotList")

    # Ensure we have enough clip slots
    slots = list(clip_slot_list)
    while len(slots) <= slot_index:
        cs = etree.SubElement(clip_slot_list, "ClipSlot")
        cs.set("Id", str(len(slots)))
        etree.SubElement(cs, "ClipSlot")
        slots = list(clip_slot_list)

    slot = slots[slot_index]
    inner = slot.find("ClipSlot")
    if inner is None:
        inner = etree.SubElement(slot, "ClipSlot")

    # Create the MIDI clip
    clip_id = als_xml.next_id(session.root)
    clip = etree.SubElement(inner, "Value")
    midi_clip = etree.SubElement(clip, "MidiClip")
    midi_clip.set("Id", str(clip_id))
    midi_clip.set("Time", "0")

    als_xml._add_value_element(midi_clip, "Name", name)
    als_xml._add_value_element(midi_clip, "Color", str(color))

    # Loop settings
    loop = etree.SubElement(midi_clip, "Loop")
    als_xml._add_value_element(loop, "LoopStart", "0")
    als_xml._add_value_element(loop, "LoopEnd", str(length))
    als_xml._add_value_element(loop, "StartRelative", "0")
    als_xml._add_value_element(loop, "LoopOn", "true")

    # Empty notes container
    notes = etree.SubElement(midi_clip, "Notes")
    etree.SubElement(notes, "KeyTracks")

    return {
        "status": "created",
        "clip_id": str(clip_id),
        "track": track_index,
        "slot": slot_index,
        "name": name,
        "length": length,
        "type": "midi",
    }


def set_clip_notes(
    session: Session,
    track_index: int,
    slot_index: int,
    notes: list[dict],
) -> dict:
    """Set MIDI notes in a clip.

    Args:
        session: The active session.
        track_index: Track index.
        slot_index: Clip slot index.
        notes: List of note dicts, each with:
            - pitch: MIDI note number (0-127)
            - time: Start time in beats
            - duration: Duration in beats
            - velocity: Velocity (0-127)

    Returns:
        Dict with result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    midi_clip = _get_midi_clip(session, track_index, slot_index)
    if midi_clip is None:
        raise ValueError(
            f"No MIDI clip at track {track_index}, slot {slot_index}"
        )

    session.checkpoint()

    # Validate notes
    for i, note in enumerate(notes):
        _validate_note(note, i)

    # Clear existing notes
    notes_el = midi_clip.find("Notes")
    if notes_el is None:
        notes_el = etree.SubElement(midi_clip, "Notes")
    key_tracks_el = notes_el.find("KeyTracks")
    if key_tracks_el is not None:
        notes_el.remove(key_tracks_el)
    key_tracks_el = etree.SubElement(notes_el, "KeyTracks")

    # Group notes by pitch
    by_pitch: dict[int, list[dict]] = {}
    for note in notes:
        pitch = note["pitch"]
        by_pitch.setdefault(pitch, []).append(note)

    # Create KeyTrack elements
    for pitch in sorted(by_pitch.keys()):
        kt = etree.SubElement(key_tracks_el, "KeyTrack")
        kt.set("Id", str(pitch))

        midi_key = etree.SubElement(kt, "MidiKey")
        midi_key.set("Value", str(pitch))

        note_events = etree.SubElement(kt, "Notes")
        for note in by_pitch[pitch]:
            event = etree.SubElement(note_events, "MidiNoteEvent")
            event.set("Time", str(note["time"]))
            event.set("Duration", str(note["duration"]))
            event.set("Velocity", str(note.get("velocity", 100)))
            event.set("VelocityDeviation", "0")
            event.set("OffVelocity", "64")
            event.set("Probability", "1")
            event.set("IsEnabled", "true")

    return {
        "status": "set",
        "track": track_index,
        "slot": slot_index,
        "note_count": len(notes),
    }


def get_clip_notes(
    session: Session,
    track_index: int,
    slot_index: int,
) -> list[dict]:
    """Get all MIDI notes from a clip.

    Args:
        session: The active session.
        track_index: Track index.
        slot_index: Clip slot index.

    Returns:
        List of note dicts.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    midi_clip = _get_midi_clip(session, track_index, slot_index)
    if midi_clip is None:
        raise ValueError(
            f"No MIDI clip at track {track_index}, slot {slot_index}"
        )

    result = []
    notes_el = midi_clip.find("Notes")
    if notes_el is None:
        return result

    key_tracks = notes_el.find("KeyTracks")
    if key_tracks is None:
        return result

    for kt in key_tracks:
        midi_key = kt.find("MidiKey")
        pitch = int(midi_key.get("Value", "60")) if midi_key is not None else 60

        note_events = kt.find("Notes")
        if note_events is None:
            continue

        for event in note_events:
            if event.tag == "MidiNoteEvent":
                result.append({
                    "pitch": pitch,
                    "time": float(event.get("Time", "0")),
                    "duration": float(event.get("Duration", "0.25")),
                    "velocity": int(event.get("Velocity", "100")),
                })

    # Sort by time, then pitch
    result.sort(key=lambda n: (n["time"], n["pitch"]))
    return result


def quantize_clip(
    session: Session,
    track_index: int,
    slot_index: int,
    grid: float = 0.25,
    strength: float = 1.0,
) -> dict:
    """Quantize MIDI notes in a clip to a grid.

    Args:
        session: The active session.
        track_index: Track index.
        slot_index: Clip slot index.
        grid: Grid size in beats (0.25 = 16th note, 0.5 = 8th, 1.0 = quarter).
        strength: Quantize strength (0.0 = none, 1.0 = full).

    Returns:
        Dict with result.
    """
    if not 0.0 <= strength <= 1.0:
        raise ValueError(f"Strength must be 0.0-1.0, got {strength}")
    if grid <= 0:
        raise ValueError(f"Grid must be positive, got {grid}")

    notes = get_clip_notes(session, track_index, slot_index)
    if not notes:
        return {
            "status": "quantized",
            "track": track_index,
            "slot": slot_index,
            "notes_affected": 0,
        }

    session.checkpoint()

    # Quantize each note's start time
    quantized = []
    affected = 0
    for note in notes:
        original_time = note["time"]
        nearest_grid = round(original_time / grid) * grid
        new_time = original_time + (nearest_grid - original_time) * strength

        if abs(new_time - original_time) > 0.001:
            affected += 1

        quantized.append({
            "pitch": note["pitch"],
            "time": round(new_time, 6),
            "duration": note["duration"],
            "velocity": note["velocity"],
        })

    # Write back
    # Undo the checkpoint we just made since set_clip_notes will make another
    session.undo()
    set_clip_notes(session, track_index, slot_index, quantized)

    return {
        "status": "quantized",
        "track": track_index,
        "slot": slot_index,
        "notes_affected": affected,
        "total_notes": len(notes),
        "grid": grid,
        "strength": strength,
    }


def duplicate_clip(
    session: Session,
    track_index: int,
    src_slot: int,
    dst_slot: int,
) -> dict:
    """Duplicate a clip from one slot to another.

    Args:
        session: The active session.
        track_index: Track index.
        src_slot: Source clip slot index.
        dst_slot: Destination clip slot index.

    Returns:
        Dict with result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    import copy

    tracks = als_xml.get_tracks_container(session.root)
    track_list = list(tracks)

    if track_index < 0 or track_index >= len(track_list):
        raise IndexError(f"Track index {track_index} out of range")

    track_el = track_list[track_index]
    dc = track_el.find("DeviceChain")
    if dc is None:
        raise ValueError(f"Track {track_index} has no device chain")

    main_seq = dc.find("MainSequencer")
    if main_seq is None:
        raise ValueError(f"Track {track_index} has no main sequencer")

    slot_list = main_seq.find("ClipSlotList")
    if slot_list is None:
        raise ValueError(f"Track {track_index} has no clip slots")

    slots = list(slot_list)
    if src_slot < 0 or src_slot >= len(slots):
        raise IndexError(f"Source slot {src_slot} out of range")

    # Ensure destination slot exists
    while len(slots) <= dst_slot:
        cs = etree.SubElement(slot_list, "ClipSlot")
        cs.set("Id", str(len(slots)))
        etree.SubElement(cs, "ClipSlot")
        slots = list(slot_list)

    session.checkpoint()

    # Deep copy source slot content
    src = slots[src_slot]
    dst = slots[dst_slot]

    # Clear destination
    inner_dst = dst.find("ClipSlot")
    if inner_dst is None:
        inner_dst = etree.SubElement(dst, "ClipSlot")
    for child in list(inner_dst):
        inner_dst.remove(child)

    # Copy source content
    inner_src = src.find("ClipSlot")
    if inner_src is not None:
        for child in inner_src:
            inner_dst.append(copy.deepcopy(child))

    return {
        "status": "duplicated",
        "track": track_index,
        "source_slot": src_slot,
        "destination_slot": dst_slot,
    }


# ── Helpers ─────────────────────────────────────────────────────────

def _get_track_name(track_el) -> str:
    """Get a track's display name."""
    name_el = track_el.find("Name")
    if name_el is None:
        return "Untitled"
    user = name_el.find("UserName")
    eff = name_el.find("EffectiveName")
    if user is not None and user.get("Value", ""):
        return user.get("Value")
    if eff is not None and eff.get("Value", ""):
        return eff.get("Value")
    return "Untitled"


def _get_midi_clip(session: Session, track_index: int, slot_index: int):
    """Navigate to a MIDI clip element, or return None."""
    tracks = als_xml.get_tracks_container(session.root)
    track_list = list(tracks)

    if track_index < 0 or track_index >= len(track_list):
        raise IndexError(f"Track index {track_index} out of range")

    track_el = track_list[track_index]
    dc = track_el.find("DeviceChain")
    if dc is None:
        return None

    main_seq = dc.find("MainSequencer")
    if main_seq is None:
        return None

    slot_list = main_seq.find("ClipSlotList")
    if slot_list is None:
        return None

    slots = list(slot_list)
    if slot_index < 0 or slot_index >= len(slots):
        return None

    slot = slots[slot_index]
    inner = slot.find("ClipSlot")
    if inner is None:
        return None

    value = inner.find("Value")
    if value is None:
        return None

    return value.find("MidiClip")


def _extract_clip_from_slot(slot_el, track_idx, track_name, slot_idx) -> Optional[dict]:
    """Extract clip info from a clip slot element.

    Returns None if the slot is empty.
    """
    inner = slot_el.find("ClipSlot")
    if inner is None:
        return None

    value = inner.find("Value")
    if value is None:
        return None

    # Check for MIDI or Audio clip
    midi_clip = value.find("MidiClip")
    audio_clip = value.find("AudioClip")

    clip_el = midi_clip if midi_clip is not None else audio_clip
    if clip_el is None:
        return None

    clip_type = "midi" if midi_clip is not None else "audio"
    name = als_xml.get_value(clip_el, "Name", "Untitled")
    color = als_xml.get_value(clip_el, "Color", "0")
    clip_id = clip_el.get("Id", "?")

    # Loop info
    length = 4.0
    loop_el = clip_el.find("Loop")
    if loop_el is not None:
        loop_start = float(als_xml.get_value(loop_el, "LoopStart", "0"))
        loop_end = float(als_xml.get_value(loop_el, "LoopEnd", "4"))
        length = loop_end - loop_start

    # Note count for MIDI clips
    note_count = 0
    if midi_clip is not None:
        notes_el = midi_clip.find("Notes")
        if notes_el is not None:
            key_tracks = notes_el.find("KeyTracks")
            if key_tracks is not None:
                for kt in key_tracks:
                    note_events = kt.find("Notes")
                    if note_events is not None:
                        note_count += len(note_events)

    return {
        "track_index": track_idx,
        "track_name": track_name,
        "slot_index": slot_idx,
        "clip_id": clip_id,
        "type": clip_type,
        "name": name,
        "color": int(color),
        "length_beats": length,
        "note_count": note_count if clip_type == "midi" else None,
    }


def _validate_note(note: dict, index: int) -> None:
    """Validate a note dict."""
    required = ["pitch", "time", "duration"]
    for key in required:
        if key not in note:
            raise ValueError(f"Note {index} missing required field: {key}")

    pitch = note["pitch"]
    if not isinstance(pitch, int) or pitch < 0 or pitch > 127:
        raise ValueError(f"Note {index}: pitch must be 0-127, got {pitch}")

    time = note["time"]
    if not isinstance(time, (int, float)) or time < 0:
        raise ValueError(f"Note {index}: time must be >= 0, got {time}")

    duration = note["duration"]
    if not isinstance(duration, (int, float)) or duration <= 0:
        raise ValueError(f"Note {index}: duration must be > 0, got {duration}")

    velocity = note.get("velocity", 100)
    if not isinstance(velocity, int) or velocity < 0 or velocity > 127:
        raise ValueError(
            f"Note {index}: velocity must be 0-127, got {velocity}"
        )
