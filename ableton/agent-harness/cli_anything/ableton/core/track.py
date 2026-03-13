"""Track management operations for Ableton Live projects.

Handles adding, removing, renaming, and configuring tracks.
"""

from lxml import etree
from typing import Optional

from ..utils import als_xml
from .session import Session


# ── Track creation ──────────────────────────────────────────────────

def add_track(
    session: Session,
    track_type: str = "midi",
    name: Optional[str] = None,
    index: Optional[int] = None,
) -> dict:
    """Add a new track to the project.

    Args:
        session: The active session.
        track_type: One of "midi", "audio", "return", "group".
        name: Track name (auto-generated if None).
        index: Insert position (appended if None).

    Returns:
        Dict with new track info.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()

    tracks = als_xml.get_tracks_container(session.root)
    scenes = als_xml.get_scenes_container(session.root)
    scene_count = len(scenes.findall("Scene"))
    track_id = als_xml.next_id(session.root)

    # Map type to tag
    tag_map = {
        "midi": "MidiTrack",
        "audio": "AudioTrack",
        "return": "ReturnTrack",
        "group": "GroupTrack",
    }
    if track_type not in tag_map:
        raise ValueError(
            f"Unknown track type: {track_type!r}. "
            f"Available: {', '.join(tag_map.keys())}"
        )

    # Auto-generate name
    if name is None:
        existing_count = len(tracks.findall(tag_map[track_type]))
        type_label = track_type.capitalize()
        name = f"{existing_count + 1}-{type_label}"

    track_el = _create_track_element(
        tag=tag_map[track_type],
        track_id=track_id,
        name=name,
        scene_count=scene_count,
    )

    # Insert at position or append
    if index is not None and 0 <= index < len(tracks):
        tracks.insert(index, track_el)
    else:
        tracks.append(track_el)
        index = len(tracks) - 1

    return {
        "status": "created",
        "index": index,
        "id": str(track_id),
        "type": track_type,
        "name": name,
    }


def remove_track(session: Session, index: int) -> dict:
    """Remove a track by index.

    Args:
        session: The active session.
        index: Track index to remove.

    Returns:
        Dict with removal result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    tracks = als_xml.get_tracks_container(session.root)
    track_list = list(tracks)

    if index < 0 or index >= len(track_list):
        raise IndexError(
            f"Track index {index} out of range (0-{len(track_list) - 1})"
        )

    session.checkpoint()

    removed = track_list[index]
    name_el = removed.find("Name")
    name = "Unknown"
    if name_el is not None:
        user = name_el.find("UserName")
        eff = name_el.find("EffectiveName")
        if user is not None and user.get("Value"):
            name = user.get("Value")
        elif eff is not None and eff.get("Value"):
            name = eff.get("Value")

    tracks.remove(removed)

    return {
        "status": "removed",
        "index": index,
        "name": name,
        "type": removed.tag.replace("Track", "").lower(),
    }


def rename_track(session: Session, index: int, name: str) -> dict:
    """Rename a track.

    Args:
        session: The active session.
        index: Track index.
        name: New track name.

    Returns:
        Dict with rename result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    track_el = _get_track_by_index(session, index)
    session.checkpoint()

    name_el = track_el.find("Name")
    if name_el is None:
        name_el = etree.SubElement(track_el, "Name")

    user_name = name_el.find("UserName")
    if user_name is None:
        user_name = etree.SubElement(name_el, "UserName")
    user_name.set("Value", name)

    eff_name = name_el.find("EffectiveName")
    if eff_name is None:
        eff_name = etree.SubElement(name_el, "EffectiveName")
    eff_name.set("Value", name)

    return {
        "status": "renamed",
        "index": index,
        "name": name,
    }


# ── Mixer controls ─────────────────────────────────────────────────

def set_volume(session: Session, index: int, volume: float) -> dict:
    """Set track volume.

    Args:
        session: The active session.
        index: Track index.
        volume: Volume level (0.0 to 1.0, where 0.85 ~ 0dB).

    Returns:
        Dict with result.
    """
    if not 0.0 <= volume <= 1.0:
        raise ValueError(f"Volume must be 0.0-1.0, got {volume}")

    track_el = _get_track_by_index(session, index)
    session.checkpoint()

    mixer = _get_or_create_mixer(track_el)
    als_xml.set_value(mixer, "Volume", str(volume))

    return {"status": "set", "index": index, "volume": volume}


def set_pan(session: Session, index: int, pan: float) -> dict:
    """Set track panning.

    Args:
        session: The active session.
        index: Track index.
        pan: Pan position (-1.0 = left, 0.0 = center, 1.0 = right).

    Returns:
        Dict with result.
    """
    if not -1.0 <= pan <= 1.0:
        raise ValueError(f"Pan must be -1.0 to 1.0, got {pan}")

    track_el = _get_track_by_index(session, index)
    session.checkpoint()

    mixer = _get_or_create_mixer(track_el)
    als_xml.set_value(mixer, "Pan", str(pan))

    return {"status": "set", "index": index, "pan": pan}


def set_mute(session: Session, index: int, muted: bool) -> dict:
    """Set track mute state.

    Args:
        session: The active session.
        index: Track index.
        muted: True to mute, False to unmute.

    Returns:
        Dict with result.
    """
    track_el = _get_track_by_index(session, index)
    session.checkpoint()

    mixer = _get_or_create_mixer(track_el)
    # In Ableton's XML, Speaker=true means active (not muted)
    als_xml.set_value(mixer, "Speaker", "false" if muted else "true")

    return {"status": "set", "index": index, "muted": muted}


def set_solo(session: Session, index: int, solo: bool) -> dict:
    """Set track solo state.

    Args:
        session: The active session.
        index: Track index.
        solo: True to solo, False to unsolo.

    Returns:
        Dict with result.
    """
    track_el = _get_track_by_index(session, index)
    session.checkpoint()

    mixer = _get_or_create_mixer(track_el)
    als_xml.set_value(mixer, "SoloSink", "true" if solo else "false")

    return {"status": "set", "index": index, "solo": solo}


def set_arm(session: Session, index: int, armed: bool) -> dict:
    """Set track arm (record-enable) state.

    Args:
        session: The active session.
        index: Track index.
        armed: True to arm, False to disarm.

    Returns:
        Dict with result.
    """
    track_el = _get_track_by_index(session, index)

    if track_el.tag not in ("MidiTrack", "AudioTrack"):
        raise ValueError(
            f"Cannot arm a {track_el.tag} — only MIDI and Audio tracks can be armed"
        )

    session.checkpoint()

    # Arm state is on the track, not the mixer
    als_xml.set_value(track_el, "TrackArm", "true" if armed else "false")

    return {"status": "set", "index": index, "armed": armed}


# ── Helpers ─────────────────────────────────────────────────────────

def _get_track_by_index(session: Session, index: int):
    """Get a track element by index."""
    if not session.is_open:
        raise RuntimeError("No project is open")

    tracks = als_xml.get_tracks_container(session.root)
    track_list = list(tracks)

    if index < 0 or index >= len(track_list):
        raise IndexError(
            f"Track index {index} out of range (0-{len(track_list) - 1})"
        )

    return track_list[index]


def _get_or_create_mixer(track_el) -> etree._Element:
    """Get or create the Mixer element within a track's DeviceChain."""
    dc = track_el.find("DeviceChain")
    if dc is None:
        dc = etree.SubElement(track_el, "DeviceChain")

    mixer = dc.find("Mixer")
    if mixer is None:
        mixer = etree.SubElement(dc, "Mixer")
        # Create default mixer values
        als_xml._add_automatable_value(mixer, "Volume", "0.85")
        als_xml._add_automatable_value(mixer, "Pan", "0.0")
        als_xml._add_value_element(mixer, "Speaker", "true")
        als_xml._add_value_element(mixer, "SoloSink", "false")

    return mixer


def _create_track_element(
    tag: str,
    track_id: int,
    name: str,
    scene_count: int = 1,
) -> etree._Element:
    """Create a new track XML element.

    Args:
        tag: XML tag (MidiTrack, AudioTrack, etc.)
        track_id: Unique track ID.
        name: Track name.
        scene_count: Number of clip slots to create.

    Returns:
        The new track element.
    """
    track = etree.Element(tag)
    track.set("Id", str(track_id))

    # Name
    name_el = etree.SubElement(track, "Name")
    als_xml._add_value_element(name_el, "EffectiveName", name)
    als_xml._add_value_element(name_el, "UserName", name)

    # Color
    als_xml._add_value_element(track, "Color", "0")

    # TrackArm (for MIDI and Audio tracks)
    if tag in ("MidiTrack", "AudioTrack"):
        als_xml._add_value_element(track, "TrackArm", "false")

    # DeviceChain with Mixer and empty clip slots
    dc = etree.SubElement(track, "DeviceChain")

    # Mixer
    mixer = etree.SubElement(dc, "Mixer")
    als_xml._add_automatable_value(mixer, "Volume", "0.85")
    als_xml._add_automatable_value(mixer, "Pan", "0.0")
    als_xml._add_value_element(mixer, "Speaker", "true")
    als_xml._add_value_element(mixer, "SoloSink", "false")

    # Sends (empty)
    etree.SubElement(mixer, "Sends")

    # MainSequencer with clip slots
    main_seq = etree.SubElement(dc, "MainSequencer")
    clip_slot_list = etree.SubElement(main_seq, "ClipSlotList")

    for i in range(scene_count):
        cs = etree.SubElement(clip_slot_list, "ClipSlot")
        cs.set("Id", str(i))
        inner = etree.SubElement(cs, "ClipSlot")
        # Empty clip slot (no Value child means empty)

    # Inner DeviceChain (for devices)
    inner_dc = etree.SubElement(dc, "DeviceChain")
    etree.SubElement(inner_dc, "Devices")

    return track
