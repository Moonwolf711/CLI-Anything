"""Device management operations for Ableton Live projects.

Handles listing, adding, and configuring audio/MIDI devices and their parameters.
"""

from lxml import etree
from typing import Optional

from ..utils import als_xml
from .session import Session


# ── Common Ableton built-in devices ────────────────────────────────

BUILTIN_DEVICES = {
    # Instruments
    "simpler": {"class": "OriginalSimpler", "type": "instrument"},
    "sampler": {"class": "MultiSampler", "type": "instrument"},
    "wavetable": {"class": "Wavetable", "type": "instrument"},
    "operator": {"class": "UltraAnalog", "type": "instrument"},
    "analog": {"class": "Analog", "type": "instrument"},
    "collision": {"class": "Collision", "type": "instrument"},
    "drift": {"class": "Drift", "type": "instrument"},
    "tension": {"class": "StringStudio", "type": "instrument"},
    "electric": {"class": "LoungeLizard", "type": "instrument"},
    "drum-rack": {"class": "DrumGroupDevice", "type": "instrument"},
    "instrument-rack": {"class": "InstrumentGroupDevice", "type": "instrument"},

    # Audio Effects
    "eq-eight": {"class": "Eq8", "type": "audio_effect"},
    "compressor": {"class": "Compressor2", "type": "audio_effect"},
    "reverb": {"class": "Reverb", "type": "audio_effect"},
    "delay": {"class": "Delay", "type": "audio_effect"},
    "chorus": {"class": "Chorus2", "type": "audio_effect"},
    "phaser": {"class": "Phaser", "type": "audio_effect"},
    "flanger": {"class": "Flanger", "type": "audio_effect"},
    "saturator": {"class": "Saturator", "type": "audio_effect"},
    "overdrive": {"class": "Overdrive", "type": "audio_effect"},
    "limiter": {"class": "Limiter", "type": "audio_effect"},
    "gate": {"class": "Gate", "type": "audio_effect"},
    "auto-filter": {"class": "AutoFilter", "type": "audio_effect"},
    "auto-pan": {"class": "AutoPan", "type": "audio_effect"},
    "glue-compressor": {"class": "GlueCompressor", "type": "audio_effect"},
    "utility": {"class": "StereoGain", "type": "audio_effect"},
    "audio-effect-rack": {"class": "AudioEffectGroupDevice", "type": "audio_effect"},

    # MIDI Effects
    "arpeggiator": {"class": "MidiArpeggiator", "type": "midi_effect"},
    "chord": {"class": "MidiChord", "type": "midi_effect"},
    "note-length": {"class": "MidiNoteLength", "type": "midi_effect"},
    "pitch": {"class": "MidiPitcher", "type": "midi_effect"},
    "random": {"class": "MidiRandom", "type": "midi_effect"},
    "scale": {"class": "MidiScale", "type": "midi_effect"},
    "velocity": {"class": "MidiVelocity", "type": "midi_effect"},
}


def list_devices(session: Session, track_index: int) -> list[dict]:
    """List all devices on a track.

    Args:
        session: The active session.
        track_index: Track index.

    Returns:
        List of device info dicts.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    devices_el = _get_devices_container(session, track_index)
    if devices_el is None:
        return []

    result = []
    for idx, dev in enumerate(devices_el):
        result.append(_extract_device_info(dev, idx))

    return result


def add_device(
    session: Session,
    track_index: int,
    device_name: str,
    index: Optional[int] = None,
) -> dict:
    """Add a built-in device to a track.

    Args:
        session: The active session.
        track_index: Track index.
        device_name: Device name (see BUILTIN_DEVICES).
        index: Insert position (appended if None).

    Returns:
        Dict with device info.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    if device_name not in BUILTIN_DEVICES:
        available = ", ".join(sorted(BUILTIN_DEVICES.keys()))
        raise ValueError(
            f"Unknown device: {device_name!r}. Available: {available}"
        )

    session.checkpoint()

    device_info = BUILTIN_DEVICES[device_name]
    devices_el = _get_or_create_devices_container(session, track_index)

    dev_id = als_xml.next_id(session.root)
    dev_el = etree.Element(device_info["class"])
    dev_el.set("Id", str(dev_id))

    als_xml._add_value_element(dev_el, "IsOn", "true")
    als_xml._add_value_element(dev_el, "DeviceName", device_name)

    # Add default parameters container
    etree.SubElement(dev_el, "Parameters")

    if index is not None and 0 <= index < len(devices_el):
        devices_el.insert(index, dev_el)
    else:
        devices_el.append(dev_el)
        index = len(devices_el) - 1

    return {
        "status": "added",
        "track": track_index,
        "index": index,
        "device_id": str(dev_id),
        "device_name": device_name,
        "device_class": device_info["class"],
        "device_type": device_info["type"],
    }


def remove_device(session: Session, track_index: int, device_index: int) -> dict:
    """Remove a device from a track.

    Args:
        session: The active session.
        track_index: Track index.
        device_index: Device index within the track.

    Returns:
        Dict with removal result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    devices_el = _get_devices_container(session, track_index)
    if devices_el is None:
        raise ValueError(f"Track {track_index} has no devices")

    dev_list = list(devices_el)
    if device_index < 0 or device_index >= len(dev_list):
        raise IndexError(
            f"Device index {device_index} out of range (0-{len(dev_list) - 1})"
        )

    session.checkpoint()

    removed = dev_list[device_index]
    name = als_xml.get_value(removed, "DeviceName", removed.tag)
    devices_el.remove(removed)

    return {
        "status": "removed",
        "track": track_index,
        "device_index": device_index,
        "device_name": name,
    }


def set_device_parameter(
    session: Session,
    track_index: int,
    device_index: int,
    param_name: str,
    value: str,
) -> dict:
    """Set a device parameter value.

    Args:
        session: The active session.
        track_index: Track index.
        device_index: Device index within the track.
        param_name: Parameter name.
        value: Parameter value as string.

    Returns:
        Dict with result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    devices_el = _get_devices_container(session, track_index)
    if devices_el is None:
        raise ValueError(f"Track {track_index} has no devices")

    dev_list = list(devices_el)
    if device_index < 0 or device_index >= len(dev_list):
        raise IndexError(
            f"Device index {device_index} out of range (0-{len(dev_list) - 1})"
        )

    session.checkpoint()

    dev_el = dev_list[device_index]

    # Try to find the parameter by name
    param_el = dev_el.find(param_name)
    if param_el is not None:
        # Direct element
        manual = param_el.find("Manual")
        if manual is not None:
            manual.set("Value", value)
        else:
            param_el.set("Value", value)
    else:
        # Create a new parameter element
        param_el = etree.SubElement(dev_el, param_name)
        manual = etree.SubElement(param_el, "Manual")
        manual.set("Value", value)

    return {
        "status": "set",
        "track": track_index,
        "device_index": device_index,
        "parameter": param_name,
        "value": value,
    }


def toggle_device(
    session: Session,
    track_index: int,
    device_index: int,
    enabled: Optional[bool] = None,
) -> dict:
    """Toggle a device on/off.

    Args:
        session: The active session.
        track_index: Track index.
        device_index: Device index.
        enabled: If specified, set to this value. If None, toggle.

    Returns:
        Dict with result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    devices_el = _get_devices_container(session, track_index)
    if devices_el is None:
        raise ValueError(f"Track {track_index} has no devices")

    dev_list = list(devices_el)
    if device_index < 0 or device_index >= len(dev_list):
        raise IndexError(
            f"Device index {device_index} out of range (0-{len(dev_list) - 1})"
        )

    session.checkpoint()

    dev_el = dev_list[device_index]
    current = als_xml.get_value(dev_el, "IsOn", "true")

    if enabled is None:
        new_val = "false" if current == "true" else "true"
    else:
        new_val = "true" if enabled else "false"

    als_xml.set_value(dev_el, "IsOn", new_val)

    return {
        "status": "toggled",
        "track": track_index,
        "device_index": device_index,
        "enabled": new_val == "true",
    }


def list_available_devices() -> list[dict]:
    """List all available built-in devices.

    Returns:
        List of device dicts with name, class, and type.
    """
    return [
        {"name": name, "class": info["class"], "type": info["type"]}
        for name, info in sorted(BUILTIN_DEVICES.items())
    ]


# ── Helpers ─────────────────────────────────────────────────────────

def _get_devices_container(session: Session, track_index: int):
    """Get the <Devices> element for a track, or None."""
    tracks = als_xml.get_tracks_container(session.root)
    track_list = list(tracks)

    if track_index < 0 or track_index >= len(track_list):
        raise IndexError(
            f"Track index {track_index} out of range (0-{len(track_list) - 1})"
        )

    track_el = track_list[track_index]
    dc = track_el.find("DeviceChain")
    if dc is None:
        return None

    inner_dc = dc.find("DeviceChain")
    if inner_dc is None:
        return None

    return inner_dc.find("Devices")


def _get_or_create_devices_container(session: Session, track_index: int):
    """Get or create the <Devices> element for a track."""
    tracks = als_xml.get_tracks_container(session.root)
    track_list = list(tracks)

    if track_index < 0 or track_index >= len(track_list):
        raise IndexError(
            f"Track index {track_index} out of range (0-{len(track_list) - 1})"
        )

    track_el = track_list[track_index]
    dc = track_el.find("DeviceChain")
    if dc is None:
        dc = etree.SubElement(track_el, "DeviceChain")

    inner_dc = dc.find("DeviceChain")
    if inner_dc is None:
        inner_dc = etree.SubElement(dc, "DeviceChain")

    devices = inner_dc.find("Devices")
    if devices is None:
        devices = etree.SubElement(inner_dc, "Devices")

    return devices


def _extract_device_info(dev_el, index: int) -> dict:
    """Extract info from a device XML element."""
    dev_class = dev_el.tag
    dev_id = dev_el.get("Id", "?")
    name = als_xml.get_value(dev_el, "DeviceName", dev_class)
    is_on = als_xml.get_value(dev_el, "IsOn", "true") == "true"

    # Collect parameters
    params = []
    for child in dev_el:
        manual = child.find("Manual")
        if manual is not None:
            params.append({
                "name": child.tag,
                "value": manual.get("Value", "?"),
            })

    return {
        "index": index,
        "id": dev_id,
        "class": dev_class,
        "name": name,
        "enabled": is_on,
        "parameters": params,
    }
