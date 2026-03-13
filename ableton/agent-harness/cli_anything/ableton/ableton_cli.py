#!/usr/bin/env python3
"""Ableton Live CLI Harness — full Click CLI with interactive REPL.

Manipulates .als project files (gzipped XML) directly. Supports
creating, editing, and inspecting Ableton Live projects from the
command line without requiring a running Ableton instance.

Usage:
    cli-anything-ableton                              # Enter REPL
    cli-anything-ableton project info my.als          # One-shot command
    cli-anything-ableton --json track list            # JSON output
    cli-anything-ableton --project my.als track add midi
"""

import json
import os
import sys
import shlex
from typing import Optional

import click

from cli_anything.ableton.core.session import Session
from cli_anything.ableton.core import project as proj_mod
from cli_anything.ableton.core import track as track_mod
from cli_anything.ableton.core import clip as clip_mod
from cli_anything.ableton.core import device as device_mod
from cli_anything.ableton.core import scene as scene_mod
from cli_anything.ableton.core import transport as transport_mod
from cli_anything.ableton.core import export as export_mod
from cli_anything.ableton.utils import als_xml
from cli_anything.ableton.utils.ableton_backend import OscBridge, get_install_info


# ── Global state ────────────────────────────────────────────────────

_session: Optional[Session] = None
_json_output: bool = False
_repl_mode: bool = False
_auto_save: bool = False
_osc_bridge: Optional[OscBridge] = None


def get_session() -> Session:
    """Get or create the global session."""
    global _session
    if _session is None:
        _session = Session()
    return _session


def output(data, message: str = ""):
    """Output result data: JSON mode or human-readable."""
    if _json_output:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if message:
            click.echo(message)
        if isinstance(data, dict):
            _print_dict(data)
        elif isinstance(data, list):
            _print_list(data)
        else:
            click.echo(str(data))


def _print_dict(d: dict, indent: int = 0):
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            click.echo(f"{prefix}{k}:")
            _print_dict(v, indent + 1)
        elif isinstance(v, list):
            click.echo(f"{prefix}{k}:")
            _print_list(v, indent + 1)
        else:
            click.echo(f"{prefix}{k}: {v}")


def _print_list(items: list, indent: int = 0):
    prefix = "  " * indent
    if not items:
        click.echo(f"{prefix}(empty)")
        return
    for i, item in enumerate(items):
        if isinstance(item, dict):
            click.echo(f"{prefix}[{i}]")
            _print_dict(item, indent + 1)
        else:
            click.echo(f"{prefix}- {item}")


def handle_error(func):
    """Decorator: catch common exceptions and output consistently."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (FileNotFoundError, FileExistsError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "file_error"}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
        except (ValueError, IndexError, RuntimeError) as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": type(e).__name__}))
            else:
                click.echo(f"Error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
        except Exception as e:
            if _json_output:
                click.echo(json.dumps({"error": str(e), "type": "unexpected"}))
            else:
                click.echo(f"Unexpected error: {e}", err=True)
            if not _repl_mode:
                sys.exit(1)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def _maybe_auto_save():
    """Save project if auto-save is enabled."""
    if _auto_save:
        session = get_session()
        if session.is_open and session.project_path:
            session.save()


# ============================================================================
# Main CLI group
# ============================================================================

@click.group(invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, help="Output in JSON format")
@click.option("--session-id", "session_id", default=None, help="Session ID to use/resume")
@click.option("--project", "project_path", default=None,
              type=click.Path(), help="Open a project file at startup")
@click.option("-s", "--save", "auto_save", is_flag=True,
              help="Auto-save project after each mutation command")
@click.pass_context
def cli(ctx, json_mode, session_id, project_path, auto_save):
    """Ableton Live CLI -- Edit .als projects from the command line.

    Run without a subcommand to enter interactive REPL mode.
    """
    global _json_output, _session, _auto_save
    _json_output = json_mode
    _auto_save = auto_save

    ctx.ensure_object(dict)
    ctx.obj["json"] = json_mode

    if session_id:
        _session = Session(session_id)
    else:
        if _session is None:
            _session = Session()

    if project_path:
        try:
            _session.open_project(project_path)
        except Exception as e:
            if json_mode:
                click.echo(json.dumps({"error": str(e)}))
            else:
                click.echo(f"Error opening project: {e}", err=True)
            sys.exit(1)

    if ctx.invoked_subcommand is None:
        _run_repl()


# ============================================================================
# PROJECT commands
# ============================================================================

@cli.group()
def project():
    """Project management -- create, open, save, info."""
    pass


@project.command("new")
@click.option("-o", "--output", "output_path", default=None,
              help="Output .als file path")
@handle_error
def project_new(output_path):
    """Create a new blank Ableton Live project."""
    session = get_session()
    result = proj_mod.new_project(session)
    if output_path:
        session.save(output_path)
        result["path"] = os.path.abspath(output_path)
    output(result, "Created new project")


@project.command("open")
@click.argument("path", type=click.Path())
@handle_error
def project_open(path):
    """Open an existing .als project file."""
    session = get_session()
    result = proj_mod.open_project(session, path)
    output(result, f"Opened: {path}")


@project.command("save")
@click.argument("path", type=click.Path(), required=False)
@handle_error
def project_save(path):
    """Save the current project (optionally to a new path)."""
    session = get_session()
    result = proj_mod.save_project(session, path)
    output(result, "Project saved")


@project.command("save-as")
@click.argument("path", type=click.Path())
@handle_error
def project_save_as(path):
    """Save the project to a new path."""
    session = get_session()
    result = proj_mod.save_project(session, path)
    output(result, f"Saved as: {path}")


@project.command("info")
@handle_error
def project_info():
    """Show detailed project information."""
    session = get_session()
    result = proj_mod.project_info(session)
    output(result)


@project.command("list-recent")
@handle_error
def project_list_recent():
    """List recently opened projects (from session history)."""
    from pathlib import Path
    session_dir = Path.home() / ".cli-anything-ableton" / "sessions"
    if not session_dir.exists():
        output({"sessions": []})
        return
    sessions = []
    for f in sorted(session_dir.glob("*.json"),
                    key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
        try:
            data = json.loads(f.read_text())
            sessions.append({
                "session_id": data.get("session_id"),
                "project_path": data.get("project_path"),
                "timestamp": data.get("timestamp"),
            })
        except Exception:
            pass
    output({"sessions": sessions})


# ============================================================================
# TRACK commands
# ============================================================================

@cli.group()
def track():
    """Track management -- add, remove, rename, volume, pan, mute, solo."""
    pass


@track.command("list")
@handle_error
def track_list():
    """List all tracks in the project."""
    session = get_session()
    result = proj_mod.list_tracks(session)
    output(result)


@track.command("add")
@click.argument("track_type",
                type=click.Choice(["midi", "audio", "return", "group"]))
@click.argument("name", required=False, default=None)
@click.option("-i", "--index", default=None, type=int, help="Insert position")
@handle_error
def track_add(track_type, name, index):
    """Add a new track (midi, audio, return, group)."""
    session = get_session()
    result = track_mod.add_track(session, track_type, name, index)
    _maybe_auto_save()
    output(result, f"Added {track_type} track")


@track.command("remove")
@click.argument("index", type=int)
@handle_error
def track_remove(index):
    """Remove a track by index."""
    session = get_session()
    result = track_mod.remove_track(session, index)
    _maybe_auto_save()
    output(result, f"Removed track {index}")


@track.command("rename")
@click.argument("index", type=int)
@click.argument("name")
@handle_error
def track_rename(index, name):
    """Rename a track."""
    session = get_session()
    result = track_mod.rename_track(session, index, name)
    _maybe_auto_save()
    output(result)


@track.command("info")
@click.argument("index", type=int)
@handle_error
def track_info(index):
    """Show detailed information about a track."""
    session = get_session()
    tracks = proj_mod.list_tracks(session)
    if index < 0 or index >= len(tracks):
        raise IndexError(f"Track index {index} out of range (0-{len(tracks) - 1})")
    result = tracks[index]
    result["devices_detail"] = device_mod.list_devices(session, index)
    result["clips_detail"] = clip_mod.list_clips(session, track_index=index)
    output(result)


@track.command("volume")
@click.argument("index", type=int)
@click.argument("value", type=float)
@handle_error
def track_volume(index, value):
    """Set track volume (0.0 to 1.0, where 0.85 ~ 0dB)."""
    session = get_session()
    result = track_mod.set_volume(session, index, value)
    _maybe_auto_save()
    output(result)


@track.command("pan")
@click.argument("index", type=int)
@click.argument("value", type=float)
@handle_error
def track_pan(index, value):
    """Set track pan (-1.0 left, 0.0 center, 1.0 right)."""
    session = get_session()
    result = track_mod.set_pan(session, index, value)
    _maybe_auto_save()
    output(result)


@track.command("mute")
@click.argument("index", type=int)
@click.option("--on/--off", default=True, help="Mute on or off")
@handle_error
def track_mute(index, on):
    """Mute or unmute a track."""
    session = get_session()
    result = track_mod.set_mute(session, index, on)
    _maybe_auto_save()
    output(result)


@track.command("solo")
@click.argument("index", type=int)
@click.option("--on/--off", default=True, help="Solo on or off")
@handle_error
def track_solo(index, on):
    """Solo or unsolo a track."""
    session = get_session()
    result = track_mod.set_solo(session, index, on)
    _maybe_auto_save()
    output(result)


@track.command("arm")
@click.argument("index", type=int)
@click.option("--on/--off", default=True, help="Arm on or off")
@handle_error
def track_arm(index, on):
    """Arm or disarm a track for recording."""
    session = get_session()
    result = track_mod.set_arm(session, index, on)
    _maybe_auto_save()
    output(result)


# ============================================================================
# CLIP commands
# ============================================================================

@cli.group()
def clip():
    """Clip management -- list, add, remove, rename, move, duplicate."""
    pass


@clip.command("list")
@click.option("-t", "--track", "track_index", default=None, type=int,
              help="Filter by track index")
@handle_error
def clip_list(track_index):
    """List all clips in the project."""
    session = get_session()
    result = clip_mod.list_clips(session, track_index)
    output(result)


@clip.command("add-midi")
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@click.option("-n", "--name", default="MIDI Clip", help="Clip name")
@click.option("-l", "--length", default=4.0, type=float, help="Length in beats")
@click.option("-c", "--color", default=0, type=int, help="Color index")
@handle_error
def clip_add_midi(track_index, slot_index, name, length, color):
    """Create a new empty MIDI clip in a track/slot."""
    session = get_session()
    result = clip_mod.create_midi_clip(
        session, track_index, slot_index, name, length, color
    )
    _maybe_auto_save()
    output(result, "Created MIDI clip")


@clip.command("add-audio")
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@click.option("-n", "--name", default="Audio Clip", help="Clip name")
@handle_error
def clip_add_audio(track_index, slot_index, name):
    """Create an audio clip placeholder on an audio track."""
    from lxml import etree

    session = get_session()
    if not session.is_open:
        raise RuntimeError("No project is open")

    tracks = als_xml.get_tracks_container(session.root)
    track_list = list(tracks)
    if track_index < 0 or track_index >= len(track_list):
        raise IndexError(f"Track index {track_index} out of range")
    track_el = track_list[track_index]
    if track_el.tag != "AudioTrack":
        raise ValueError(
            f"Track {track_index} is {track_el.tag}, not AudioTrack"
        )

    session.checkpoint()

    dc = track_el.find("DeviceChain")
    if dc is None:
        dc = etree.SubElement(track_el, "DeviceChain")
    main_seq = dc.find("MainSequencer")
    if main_seq is None:
        main_seq = etree.SubElement(dc, "MainSequencer")
    slot_list_el = main_seq.find("ClipSlotList")
    if slot_list_el is None:
        slot_list_el = etree.SubElement(main_seq, "ClipSlotList")
    slots = list(slot_list_el)
    while len(slots) <= slot_index:
        cs = etree.SubElement(slot_list_el, "ClipSlot")
        cs.set("Id", str(len(slots)))
        etree.SubElement(cs, "ClipSlot")
        slots = list(slot_list_el)

    slot = slots[slot_index]
    inner = slot.find("ClipSlot")
    if inner is None:
        inner = etree.SubElement(slot, "ClipSlot")

    clip_id = als_xml.next_id(session.root)
    value_el = etree.SubElement(inner, "Value")
    audio_clip = etree.SubElement(value_el, "AudioClip")
    audio_clip.set("Id", str(clip_id))
    audio_clip.set("Time", "0")
    als_xml._add_value_element(audio_clip, "Name", name)
    als_xml._add_value_element(audio_clip, "Color", "0")
    loop = etree.SubElement(audio_clip, "Loop")
    als_xml._add_value_element(loop, "LoopStart", "0")
    als_xml._add_value_element(loop, "LoopEnd", "4")
    als_xml._add_value_element(loop, "StartRelative", "0")
    als_xml._add_value_element(loop, "LoopOn", "true")

    _maybe_auto_save()
    output({
        "status": "created",
        "clip_id": str(clip_id),
        "track": track_index,
        "slot": slot_index,
        "name": name,
        "type": "audio",
    }, "Created audio clip")


@clip.command("remove")
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@handle_error
def clip_remove(track_index, slot_index):
    """Remove a clip from a slot."""
    session = get_session()
    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()
    tracks = als_xml.get_tracks_container(session.root)
    track_list = list(tracks)
    if track_index < 0 or track_index >= len(track_list):
        raise IndexError(f"Track index {track_index} out of range")
    track_el = track_list[track_index]
    dc = track_el.find("DeviceChain")
    if dc is None:
        raise ValueError("Track has no device chain")
    main_seq = dc.find("MainSequencer")
    if main_seq is None:
        raise ValueError("Track has no main sequencer")
    slot_list_el = main_seq.find("ClipSlotList")
    if slot_list_el is None:
        raise ValueError("Track has no clip slots")
    slots = list(slot_list_el)
    if slot_index < 0 or slot_index >= len(slots):
        raise IndexError(f"Slot index {slot_index} out of range")
    inner = slots[slot_index].find("ClipSlot")
    if inner is None:
        raise ValueError("Slot is empty")
    value_el = inner.find("Value")
    if value_el is None:
        raise ValueError("Slot is already empty")
    inner.remove(value_el)

    _maybe_auto_save()
    output({"status": "removed", "track": track_index, "slot": slot_index})


@clip.command("info")
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@handle_error
def clip_info(track_index, slot_index):
    """Show clip details including notes for MIDI clips."""
    session = get_session()
    clips = clip_mod.list_clips(session, track_index)
    for c in clips:
        if c["slot_index"] == slot_index:
            if c["type"] == "midi":
                c["notes"] = clip_mod.get_clip_notes(
                    session, track_index, slot_index
                )
            output(c)
            return
    raise ValueError(f"No clip at track {track_index}, slot {slot_index}")


@clip.command("rename")
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@click.argument("name")
@handle_error
def clip_rename(track_index, slot_index, name):
    """Rename a clip."""
    session = get_session()
    if not session.is_open:
        raise RuntimeError("No project is open")
    session.checkpoint()

    # Try MIDI clip
    midi_clip = clip_mod._get_midi_clip(session, track_index, slot_index)
    if midi_clip is not None:
        als_xml.set_value(midi_clip, "Name", name)
        _maybe_auto_save()
        output({"status": "renamed", "track": track_index,
                "slot": slot_index, "name": name})
        return

    # Try audio clip
    tracks = als_xml.get_tracks_container(session.root)
    track_list = list(tracks)
    if track_index < 0 or track_index >= len(track_list):
        raise IndexError(f"Track index {track_index} out of range")
    track_el = track_list[track_index]
    dc = track_el.find("DeviceChain")
    if dc is not None:
        ms = dc.find("MainSequencer")
        if ms is not None:
            sl = ms.find("ClipSlotList")
            if sl is not None:
                slots = list(sl)
                if 0 <= slot_index < len(slots):
                    inner = slots[slot_index].find("ClipSlot")
                    if inner is not None:
                        value_el = inner.find("Value")
                        if value_el is not None:
                            ac = value_el.find("AudioClip")
                            if ac is not None:
                                als_xml.set_value(ac, "Name", name)
                                _maybe_auto_save()
                                output({"status": "renamed",
                                        "track": track_index,
                                        "slot": slot_index,
                                        "name": name})
                                return
    raise ValueError(f"No clip at track {track_index}, slot {slot_index}")


@clip.command("move")
@click.argument("track_index", type=int)
@click.argument("src_slot", type=int)
@click.argument("dst_slot", type=int)
@handle_error
def clip_move(track_index, src_slot, dst_slot):
    """Move a clip from one slot to another (cut + paste)."""
    session = get_session()
    result = clip_mod.duplicate_clip(session, track_index, src_slot, dst_slot)
    # Clear source slot
    tracks = als_xml.get_tracks_container(session.root)
    track_list = list(tracks)
    track_el = track_list[track_index]
    dc = track_el.find("DeviceChain")
    ms = dc.find("MainSequencer")
    sl = ms.find("ClipSlotList")
    slots = list(sl)
    inner_src = slots[src_slot].find("ClipSlot")
    if inner_src is not None:
        for child in list(inner_src):
            inner_src.remove(child)
    result["status"] = "moved"
    _maybe_auto_save()
    output(result)


@clip.command("duplicate")
@click.argument("track_index", type=int)
@click.argument("src_slot", type=int)
@click.argument("dst_slot", type=int)
@handle_error
def clip_duplicate(track_index, src_slot, dst_slot):
    """Duplicate a clip from one slot to another."""
    session = get_session()
    result = clip_mod.duplicate_clip(session, track_index, src_slot, dst_slot)
    _maybe_auto_save()
    output(result)


# ============================================================================
# NOTE commands
# ============================================================================

@cli.group()
def note():
    """Note operations -- list, add, remove, quantize."""
    pass


@note.command("list")
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@handle_error
def note_list(track_index, slot_index):
    """List all MIDI notes in a clip."""
    session = get_session()
    result = clip_mod.get_clip_notes(session, track_index, slot_index)
    output(result)


@note.command("add")
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@click.option("-p", "--pitch", required=True, type=int,
              help="MIDI note number (0-127)")
@click.option("-t", "--time", "time_val", required=True, type=float,
              help="Start time in beats")
@click.option("-d", "--duration", default=0.5, type=float,
              help="Duration in beats")
@click.option("-v", "--velocity", default=100, type=int,
              help="Velocity (0-127)")
@handle_error
def note_add(track_index, slot_index, pitch, time_val, duration, velocity):
    """Add a MIDI note to a clip."""
    session = get_session()
    existing = clip_mod.get_clip_notes(session, track_index, slot_index)
    new_note = {
        "pitch": pitch,
        "time": time_val,
        "duration": duration,
        "velocity": velocity,
    }
    existing.append(new_note)
    result = clip_mod.set_clip_notes(session, track_index, slot_index, existing)
    result["added"] = new_note
    _maybe_auto_save()
    output(result)


@note.command("remove")
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@click.option("-p", "--pitch", default=None, type=int,
              help="Remove notes with this pitch")
@click.option("-t", "--time", "time_val", default=None, type=float,
              help="Remove notes at this time")
@handle_error
def note_remove(track_index, slot_index, pitch, time_val):
    """Remove notes from a MIDI clip by pitch and/or time."""
    session = get_session()
    existing = clip_mod.get_clip_notes(session, track_index, slot_index)
    original_count = len(existing)

    if pitch is None and time_val is None:
        raise ValueError("Must specify at least --pitch or --time")

    filtered = []
    for n in existing:
        should_remove = True
        if pitch is not None and n["pitch"] != pitch:
            should_remove = False
        if time_val is not None and abs(n["time"] - time_val) > 0.001:
            should_remove = False
        if not should_remove:
            filtered.append(n)

    removed_count = original_count - len(filtered)
    if removed_count > 0:
        result = clip_mod.set_clip_notes(
            session, track_index, slot_index, filtered
        )
        result["removed_count"] = removed_count
    else:
        result = {"status": "no_match", "removed_count": 0}
    _maybe_auto_save()
    output(result)


@note.command("quantize")
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@click.option("-g", "--grid", default=0.25, type=float,
              help="Grid size in beats (0.25=16th, 0.5=8th, 1.0=quarter)")
@click.option("--strength", default=1.0, type=float,
              help="Quantize strength (0.0 to 1.0)")
@handle_error
def note_quantize(track_index, slot_index, grid, strength):
    """Quantize MIDI notes in a clip to a grid."""
    session = get_session()
    result = clip_mod.quantize_clip(
        session, track_index, slot_index, grid, strength
    )
    _maybe_auto_save()
    output(result)


# ============================================================================
# DEVICE commands
# ============================================================================

@cli.group()
def device():
    """Device management -- list, add, remove, info."""
    pass


@device.command("list")
@click.argument("track_index", type=int)
@handle_error
def device_list(track_index):
    """List all devices on a track."""
    session = get_session()
    result = device_mod.list_devices(session, track_index)
    output(result)


@device.command("add")
@click.argument("track_index", type=int)
@click.argument("device_name")
@click.option("-i", "--index", default=None, type=int, help="Insert position")
@handle_error
def device_add(track_index, device_name, index):
    """Add a built-in device to a track."""
    session = get_session()
    result = device_mod.add_device(session, track_index, device_name, index)
    _maybe_auto_save()
    output(result, f"Added {device_name}")


@device.command("remove")
@click.argument("track_index", type=int)
@click.argument("device_index", type=int)
@handle_error
def device_remove(track_index, device_index):
    """Remove a device from a track."""
    session = get_session()
    result = device_mod.remove_device(session, track_index, device_index)
    _maybe_auto_save()
    output(result)


@device.command("info")
@click.argument("track_index", type=int)
@click.argument("device_index", type=int)
@handle_error
def device_info(track_index, device_index):
    """Show detailed device information and parameters."""
    session = get_session()
    devices = device_mod.list_devices(session, track_index)
    if device_index < 0 or device_index >= len(devices):
        raise IndexError(
            f"Device index {device_index} out of range "
            f"(0-{len(devices) - 1})"
        )
    output(devices[device_index])


@device.command("set-param")
@click.argument("track_index", type=int)
@click.argument("device_index", type=int)
@click.argument("param_name")
@click.argument("value")
@handle_error
def device_set_param(track_index, device_index, param_name, value):
    """Set a device parameter value."""
    session = get_session()
    result = device_mod.set_device_parameter(
        session, track_index, device_index, param_name, value
    )
    _maybe_auto_save()
    output(result)


@device.command("toggle")
@click.argument("track_index", type=int)
@click.argument("device_index", type=int)
@click.option("--on/--off", "enabled", default=None, help="Enable or disable")
@handle_error
def device_toggle(track_index, device_index, enabled):
    """Toggle a device on/off."""
    session = get_session()
    result = device_mod.toggle_device(
        session, track_index, device_index, enabled
    )
    _maybe_auto_save()
    output(result)


@device.command("list-available")
@handle_error
def device_list_available():
    """List all available built-in devices."""
    result = device_mod.list_available_devices()
    output(result)


# ============================================================================
# TRANSPORT commands
# ============================================================================

@cli.group()
def transport():
    """Transport and tempo commands."""
    pass


@transport.command("get")
@handle_error
def transport_get():
    """Show current transport settings (tempo, time-sig, loop)."""
    session = get_session()
    result = transport_mod.get_transport(session)
    output(result)


@transport.command("set-tempo")
@click.argument("bpm", type=float)
@handle_error
def transport_set_tempo(bpm):
    """Set the project tempo in BPM."""
    session = get_session()
    result = transport_mod.set_tempo(session, bpm)
    _maybe_auto_save()
    output(result)


@transport.command("set-time-sig")
@click.argument("numerator", type=int)
@click.argument("denominator", type=int)
@handle_error
def transport_set_time_sig(numerator, denominator):
    """Set the time signature (e.g., 4 4 for 4/4)."""
    session = get_session()
    result = transport_mod.set_time_signature(session, numerator, denominator)
    _maybe_auto_save()
    output(result)


@transport.command("loop")
@click.option("--on/--off", "enabled", default=None,
              help="Enable/disable loop")
@click.option("--start", default=None, type=float,
              help="Loop start in beats")
@click.option("--length", default=None, type=float,
              help="Loop length in beats")
@handle_error
def transport_loop(enabled, start, length):
    """Configure loop settings."""
    session = get_session()
    result = transport_mod.set_loop(session, enabled, start, length)
    _maybe_auto_save()
    output(result)


# ============================================================================
# EXPORT commands
# ============================================================================

@cli.group("export")
def export_group():
    """Export and render commands."""
    pass


@export_group.command("als")
@click.argument("output_path", type=click.Path())
@click.option("--overwrite", is_flag=True, help="Overwrite existing file")
@handle_error
def export_als(output_path, overwrite):
    """Export the project as a .als file."""
    session = get_session()
    result = export_mod.export_als(session, output_path, overwrite=overwrite)
    output(result, f"Exported: {output_path}")


@export_group.command("xml-dump")
@click.argument("output_path", type=click.Path(), required=False)
@handle_error
def export_xml_dump(output_path):
    """Dump project XML for debugging. Prints to stdout if no path given."""
    session = get_session()
    if not session.is_open:
        raise RuntimeError("No project is open")

    if output_path:
        result = export_mod.export_xml(
            session, output_path, overwrite=True
        )
        output(result, f"Exported XML: {output_path}")
    else:
        xml_str = als_xml.to_xml_string(session.root)
        click.echo(xml_str)


@export_group.command("midi")
@click.argument("output_path", type=click.Path())
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@click.option("--overwrite", is_flag=True, help="Overwrite existing file")
@handle_error
def export_midi(output_path, track_index, slot_index, overwrite):
    """Export a MIDI clip as a .mid file."""
    session = get_session()
    result = export_mod.export_midi(
        session, output_path, track_index, slot_index, overwrite=overwrite
    )
    output(result, f"Exported MIDI: {output_path}")


# ============================================================================
# SESSION commands
# ============================================================================

@cli.group("session")
def session_group():
    """Session management -- status, undo, redo, history, save, load."""
    pass


@session_group.command("status")
@handle_error
def session_status():
    """Show current session status."""
    session = get_session()
    output(session.session_info())


@session_group.command("undo")
@handle_error
def session_undo():
    """Undo the last operation."""
    session = get_session()
    if session.undo():
        _maybe_auto_save()
        output({"status": "undone", "undo_depth": len(session._undo_stack)})
    else:
        output({"status": "nothing_to_undo"})


@session_group.command("redo")
@handle_error
def session_redo():
    """Redo the last undone operation."""
    session = get_session()
    if session.redo():
        _maybe_auto_save()
        output({"status": "redone", "redo_depth": len(session._redo_stack)})
    else:
        output({"status": "nothing_to_redo"})


@session_group.command("history")
@handle_error
def session_history():
    """Show undo/redo stack depth."""
    session = get_session()
    output({
        "undo_depth": len(session._undo_stack),
        "redo_depth": len(session._redo_stack),
        "modified": session.is_modified,
    })


@session_group.command("save")
@handle_error
def session_persist():
    """Persist session state to disk for later restoration."""
    session = get_session()
    path = session.persist()
    output({"status": "saved", "path": path})


@session_group.command("load")
@click.argument("session_id")
@handle_error
def session_load(session_id):
    """Restore a session from disk."""
    global _session
    _session = Session.restore(session_id)
    output(_session.session_info())


# ============================================================================
# OSC commands (live control)
# ============================================================================

@cli.group()
def osc():
    """OSC bridge commands for live Ableton control."""
    pass


@osc.command("connect")
@click.option("-h", "--host", "host", default="127.0.0.1", help="OSC host")
@click.option("-p", "--port", default=9876, type=int, help="OSC port")
@handle_error
def osc_connect(host, port):
    """Connect to a running Ableton instance via OSC bridge."""
    global _osc_bridge
    _osc_bridge = OscBridge(host, port)
    result = _osc_bridge.connect()
    output(result)


@osc.command("status")
@handle_error
def osc_status():
    """Show OSC bridge connection status."""
    if _osc_bridge is None:
        output({"connected": False, "message": "No bridge configured"})
    else:
        output(_osc_bridge.status())


@osc.command("send")
@click.argument("address")
@click.argument("args", nargs=-1)
@handle_error
def osc_send(address, args):
    """Send a raw OSC message."""
    if _osc_bridge is None or not _osc_bridge.connected:
        raise RuntimeError("Not connected. Use 'osc connect' first.")
    parsed_args = []
    for a in args:
        try:
            parsed_args.append(int(a))
        except ValueError:
            try:
                parsed_args.append(float(a))
            except ValueError:
                parsed_args.append(a)
    result = _osc_bridge.send(address, *parsed_args)
    output(result)


@osc.command("play")
@handle_error
def osc_play():
    """Send play command via OSC."""
    if _osc_bridge is None or not _osc_bridge.connected:
        raise RuntimeError("Not connected. Use 'osc connect' first.")
    result = transport_mod.osc_play(_osc_bridge)
    output(result)


@osc.command("stop")
@handle_error
def osc_stop():
    """Send stop command via OSC."""
    if _osc_bridge is None or not _osc_bridge.connected:
        raise RuntimeError("Not connected. Use 'osc connect' first.")
    result = transport_mod.osc_stop(_osc_bridge)
    output(result)


@osc.command("record")
@handle_error
def osc_record():
    """Toggle recording via OSC."""
    if _osc_bridge is None or not _osc_bridge.connected:
        raise RuntimeError("Not connected. Use 'osc connect' first.")
    result = transport_mod.osc_record(_osc_bridge)
    output(result)


# ============================================================================
# INSTALL-CHECK command
# ============================================================================

@cli.command("install-check")
@handle_error
def install_check():
    """Show Ableton Live installation information."""
    result = get_install_info()
    output(result)


# ── Backward-compatible aliases ──────────────────────────────────────

@cli.command("install-info", hidden=True)
@handle_error
def install_info_alias():
    """Alias for install-check (backward compat)."""
    result = get_install_info()
    output(result)


@project.command("list-tracks", hidden=True)
@handle_error
def project_list_tracks():
    """Alias for 'track list' (backward compat)."""
    session = get_session()
    result = proj_mod.list_tracks(session)
    output(result)


@clip.command("create-midi", hidden=True)
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@click.option("-n", "--name", default="MIDI Clip", help="Clip name")
@click.option("-l", "--length", default=4.0, type=float, help="Length in beats")
@handle_error
def clip_create_midi_alias(track_index, slot_index, name, length):
    """Alias for 'clip add-midi' (backward compat)."""
    session = get_session()
    result = clip_mod.create_midi_clip(
        session, track_index, slot_index, name, length
    )
    _maybe_auto_save()
    output(result)


@clip.command("set-notes", hidden=True)
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@click.option("--notes", "notes_json", required=True,
              help='JSON array of notes')
@handle_error
def clip_set_notes_alias(track_index, slot_index, notes_json):
    """Alias for 'note add' bulk mode (backward compat)."""
    notes = json.loads(notes_json)
    session = get_session()
    result = clip_mod.set_clip_notes(session, track_index, slot_index, notes)
    _maybe_auto_save()
    output(result)


@clip.command("get-notes", hidden=True)
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@handle_error
def clip_get_notes_alias(track_index, slot_index):
    """Alias for 'note list' (backward compat)."""
    session = get_session()
    result = clip_mod.get_clip_notes(session, track_index, slot_index)
    output(result)


@clip.command("quantize", hidden=True)
@click.argument("track_index", type=int)
@click.argument("slot_index", type=int)
@click.option("-g", "--grid", default=0.25, type=float)
@click.option("--strength", default=1.0, type=float)
@handle_error
def clip_quantize_alias(track_index, slot_index, grid, strength):
    """Alias for 'note quantize' (backward compat)."""
    session = get_session()
    result = clip_mod.quantize_clip(
        session, track_index, slot_index, grid, strength
    )
    _maybe_auto_save()
    output(result)


@transport.command("info", hidden=True)
@handle_error
def transport_info_alias():
    """Alias for 'transport get' (backward compat)."""
    session = get_session()
    result = transport_mod.get_transport(session)
    output(result)


@device.command("available", hidden=True)
@handle_error
def device_available_alias():
    """Alias for 'device list-available' (backward compat)."""
    result = device_mod.list_available_devices()
    output(result)


@session_group.command("info", hidden=True)
@handle_error
def session_info_alias():
    """Alias for 'session status' (backward compat)."""
    session = get_session()
    output(session.session_info())


# Also add scene group + commands from the original CLI

@cli.group()
def scene():
    """Scene management -- list, create, delete, rename, set-tempo."""
    pass


@scene.command("list")
@handle_error
def scene_list():
    """List all scenes in the project."""
    session = get_session()
    result = scene_mod.list_scenes(session)
    output(result)


@scene.command("create")
@click.option("-n", "--name", default=None, help="Scene name")
@click.option("-i", "--index", default=None, type=int, help="Insert position")
@handle_error
def scene_create(name, index):
    """Create a new scene."""
    session = get_session()
    result = scene_mod.create_scene(session, name, index)
    _maybe_auto_save()
    output(result, "Created scene")


@scene.command("delete")
@click.argument("index", type=int)
@handle_error
def scene_delete(index):
    """Delete a scene by index."""
    session = get_session()
    result = scene_mod.delete_scene(session, index)
    _maybe_auto_save()
    output(result)


@scene.command("rename")
@click.argument("index", type=int)
@click.argument("name")
@handle_error
def scene_rename(index, name):
    """Rename a scene."""
    session = get_session()
    result = scene_mod.rename_scene(session, index, name)
    _maybe_auto_save()
    output(result)


@scene.command("set-tempo")
@click.argument("index", type=int)
@click.argument("tempo", type=float)
@handle_error
def scene_set_tempo(index, tempo):
    """Set a scene-specific tempo (-1 for global)."""
    session = get_session()
    result = scene_mod.set_scene_tempo(session, index, tempo)
    _maybe_auto_save()
    output(result)


# Also add export xml alias

@export_group.command("xml", hidden=True)
@click.argument("output_path", type=click.Path())
@click.option("--overwrite", is_flag=True, help="Overwrite existing file")
@handle_error
def export_xml_alias(output_path, overwrite):
    """Alias for 'export xml-dump' (backward compat)."""
    session = get_session()
    result = export_mod.export_xml(session, output_path, overwrite=overwrite)
    output(result)


# ============================================================================
# REPL
# ============================================================================

@cli.command("repl")
@click.argument("project_path", required=False, default=None)
def repl_command(project_path):
    """Start the interactive REPL."""
    _run_repl(project_path)


def _run_repl(project_path: Optional[str] = None):
    """Main REPL loop."""
    global _repl_mode
    _repl_mode = True

    from cli_anything.ableton.utils.repl_skin import ReplSkin

    skin = ReplSkin("ableton", version="1.0.0")
    skin.print_banner()

    session = get_session()

    if project_path:
        try:
            session.open_project(project_path)
            skin.success(f"Opened: {project_path}")
        except Exception as e:
            skin.error(f"Cannot open: {e}")

    pt_session = skin.create_prompt_session()

    _HELP_COMMANDS = {
        "project new [-o path]": "Create a new project",
        "project open <path>": "Open an .als file",
        "project save [path]": "Save the project",
        "project save-as <path>": "Save project to new path",
        "project info": "Show project info",
        "project list-recent": "List recent sessions",
        "track list": "List all tracks",
        "track add <type> [name]": "Add track (midi/audio/return/group)",
        "track remove <index>": "Remove a track",
        "track rename <idx> <name>": "Rename a track",
        "track info <index>": "Show track details",
        "track volume <idx> <val>": "Set volume (0.0-1.0)",
        "track pan <idx> <val>": "Set pan (-1.0 to 1.0)",
        "track mute <index>": "Mute a track",
        "track solo <index>": "Solo a track",
        "clip list [-t track]": "List clips",
        "clip add-midi <trk> <slot>": "Create MIDI clip",
        "clip add-audio <trk> <slot>": "Create audio clip",
        "clip remove <trk> <slot>": "Remove a clip",
        "clip info <trk> <slot>": "Show clip details",
        "clip rename <trk> <slot> <nm>": "Rename a clip",
        "clip move <trk> <src> <dst>": "Move clip between slots",
        "clip duplicate <trk> <s> <d>": "Duplicate a clip",
        "note list <trk> <slot>": "List MIDI notes",
        "note add <trk> <slot> -p -t": "Add a MIDI note",
        "note remove <trk> <slot>": "Remove notes by pitch/time",
        "note quantize <trk> <slot>": "Quantize notes",
        "device list <track>": "List devices on a track",
        "device add <track> <name>": "Add a device",
        "device remove <trk> <idx>": "Remove a device",
        "device info <trk> <idx>": "Show device details",
        "device list-available": "List available devices",
        "transport get": "Show transport settings",
        "transport set-tempo <bpm>": "Set tempo",
        "transport set-time-sig <n> <d>": "Set time signature",
        "export als <path>": "Export .als file",
        "export xml-dump [path]": "Dump XML (debug)",
        "export midi <path> <trk> <slt>": "Export MIDI file",
        "session status": "Session status",
        "session undo": "Undo last operation",
        "session redo": "Redo last undone operation",
        "session history": "Show undo/redo depth",
        "session save": "Persist session to disk",
        "session load <id>": "Restore session from disk",
        "install-check": "Ableton installation info",
        "help": "Show this help",
        "quit / exit": "Exit the REPL",
    }

    while True:
        try:
            proj_name = ""
            modified = False
            if session.is_open:
                proj_name = os.path.basename(
                    session.project_path or "untitled"
                )
                modified = session.is_modified

            line = skin.get_input(
                pt_session,
                project_name=proj_name,
                modified=modified,
            )

            if not line:
                continue

            lower = line.strip().lower()
            if lower in ("quit", "exit", "q"):
                if session.is_modified:
                    skin.warning(
                        "Unsaved changes! Use 'project save' first, "
                        "or type 'quit!' to force exit."
                    )
                    continue
                skin.print_goodbye()
                break
            if lower in ("quit!", "exit!"):
                skin.print_goodbye()
                break

            if lower == "help":
                skin.help(_HELP_COMMANDS)
                continue

            try:
                args = shlex.split(line)
            except ValueError as e:
                skin.error(f"Parse error: {e}")
                continue

            try:
                cli.main(args=args, standalone_mode=False)
            except SystemExit:
                pass
            except click.exceptions.UsageError as e:
                skin.error(str(e))
            except Exception as e:
                skin.error(str(e))

        except KeyboardInterrupt:
            click.echo()
            continue
        except EOFError:
            skin.print_goodbye()
            break


# ============================================================================
# Entry point
# ============================================================================

def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
