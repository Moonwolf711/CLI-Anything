"""Project management operations for Ableton .als files.

Handles creating, opening, inspecting, and saving Ableton Live projects.
"""

import os
from typing import Optional

from ..utils import als_xml
from .session import Session


def new_project(session: Session) -> dict:
    """Create a new blank Ableton Live project.

    Args:
        session: The active session.

    Returns:
        Dict with project info.
    """
    session.new_project()
    return session.project_info()


def open_project(session: Session, path: str) -> dict:
    """Open an existing .als project file.

    Args:
        session: The active session.
        path: Path to the .als file.

    Returns:
        Dict with project info.
    """
    return session.open_project(path)


def save_project(session: Session, path: Optional[str] = None) -> dict:
    """Save the current project.

    Args:
        session: The active session.
        path: Output path (None = save to original location).

    Returns:
        Dict with save result.
    """
    saved_path = session.save(path)
    return {
        "status": "saved",
        "path": saved_path,
    }


def project_info(session: Session) -> dict:
    """Get detailed information about the open project.

    Args:
        session: The active session.

    Returns:
        Dict with comprehensive project info.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    info = session.project_info()

    # Add additional details
    root = session.root
    ls = als_xml.get_live_set(root)
    tracks_el = als_xml.get_tracks_container(root)

    # Build track listing
    track_list = []
    for idx, track in enumerate(tracks_el):
        track_info = _extract_track_info(track, idx)
        track_list.append(track_info)

    info["track_list"] = track_list

    return info


def list_tracks(session: Session) -> list[dict]:
    """List all tracks in the project.

    Args:
        session: The active session.

    Returns:
        List of track info dicts.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    tracks_el = als_xml.get_tracks_container(session.root)
    result = []
    for idx, track in enumerate(tracks_el):
        result.append(_extract_track_info(track, idx))
    return result


def _extract_track_info(track_el, index: int) -> dict:
    """Extract info from a track XML element.

    Args:
        track_el: The track XML element.
        index: Track index.

    Returns:
        Dict with track information.
    """
    tag = track_el.tag  # MidiTrack, AudioTrack, ReturnTrack, GroupTrack
    track_type = tag.replace("Track", "").lower()
    if track_type == "midi":
        track_type = "midi"
    elif track_type == "audio":
        track_type = "audio"
    elif track_type == "return":
        track_type = "return"
    elif track_type == "group":
        track_type = "group"

    track_id = track_el.get("Id", str(index))

    # Get name — Ableton stores it under Name/EffectiveName or Name/UserName
    name = "Untitled"
    name_el = track_el.find("Name")
    if name_el is not None:
        eff = name_el.find("EffectiveName")
        user = name_el.find("UserName")
        if user is not None and user.get("Value", ""):
            name = user.get("Value", name)
        elif eff is not None and eff.get("Value", ""):
            name = eff.get("Value", name)

    # Mixer values
    volume = "1.0"
    pan = "0.0"
    mute = False
    solo = False

    dc = track_el.find("DeviceChain")
    if dc is not None:
        mixer = dc.find("Mixer")
        if mixer is not None:
            volume = als_xml.get_value(mixer, "Volume", "1.0")
            pan = als_xml.get_value(mixer, "Pan", "0.0")
            speaker_el = mixer.find("Speaker")
            if speaker_el is not None:
                mute_val = als_xml.get_value(mixer, "Speaker", "true")
                mute = mute_val == "false"  # Speaker off = muted
            solo_el = mixer.find("SoloSink")
            if solo_el is not None:
                solo = als_xml.get_value(mixer, "SoloSink", "false") == "true"

    # Count clips
    clip_count = 0
    if dc is not None:
        main_seq = dc.find("MainSequencer")
        if main_seq is not None:
            clip_slots = main_seq.find("ClipSlotList")
            if clip_slots is not None:
                for cs in clip_slots:
                    inner = cs.find("ClipSlot")
                    if inner is not None:
                        # Check if there's actual clip content
                        if inner.find("Value") is not None:
                            clip_count += 1
                        elif len(inner) > 0:
                            clip_count += 1

    # Count devices
    device_count = 0
    if dc is not None:
        devices = dc.find("DeviceChain")
        if devices is not None:
            devs = devices.find("Devices")
            if devs is not None:
                device_count = len(devs)

    return {
        "index": index,
        "id": track_id,
        "type": track_type,
        "name": name,
        "volume": volume,
        "pan": pan,
        "muted": mute,
        "solo": solo,
        "clips": clip_count,
        "devices": device_count,
    }
