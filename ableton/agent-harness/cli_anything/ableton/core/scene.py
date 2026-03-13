"""Scene management operations for Ableton Live projects.

Handles creating, listing, renaming, and deleting scenes.
"""

from lxml import etree
from typing import Optional

from ..utils import als_xml
from .session import Session


def list_scenes(session: Session) -> list[dict]:
    """List all scenes in the project.

    Args:
        session: The active session.

    Returns:
        List of scene info dicts.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    scenes = als_xml.get_scenes_container(session.root)
    result = []
    for idx, scene in enumerate(scenes.findall("Scene")):
        result.append(_extract_scene_info(scene, idx))

    return result


def create_scene(
    session: Session,
    name: Optional[str] = None,
    index: Optional[int] = None,
) -> dict:
    """Create a new scene.

    Args:
        session: The active session.
        name: Scene name (auto-generated if None).
        index: Insert position (appended if None).

    Returns:
        Dict with scene info.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()

    scenes = als_xml.get_scenes_container(session.root)
    existing = scenes.findall("Scene")
    scene_idx = len(existing)

    if name is None:
        name = f"Scene {scene_idx + 1}"

    scene_id = als_xml.next_id(session.root)
    scene = etree.Element("Scene")
    scene.set("Id", str(scene_id))
    als_xml._add_value_element(scene, "Name", name)
    als_xml._add_value_element(scene, "Tempo", "-1")
    als_xml._add_value_element(scene, "TimeSignatureId", "-1")

    if index is not None and 0 <= index < len(existing):
        scenes.insert(index, scene)
    else:
        scenes.append(scene)
        index = len(scenes.findall("Scene")) - 1

    # Add clip slots to all tracks for this new scene
    tracks = als_xml.get_tracks_container(session.root)
    for track in tracks:
        dc = track.find("DeviceChain")
        if dc is None:
            continue
        main_seq = dc.find("MainSequencer")
        if main_seq is None:
            continue
        slot_list = main_seq.find("ClipSlotList")
        if slot_list is None:
            continue

        cs = etree.SubElement(slot_list, "ClipSlot")
        cs.set("Id", str(scene_idx))
        etree.SubElement(cs, "ClipSlot")

    return {
        "status": "created",
        "index": index,
        "id": str(scene_id),
        "name": name,
    }


def delete_scene(session: Session, index: int) -> dict:
    """Delete a scene by index.

    Args:
        session: The active session.
        index: Scene index to delete.

    Returns:
        Dict with result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    scenes = als_xml.get_scenes_container(session.root)
    scene_list = scenes.findall("Scene")

    if len(scene_list) <= 1:
        raise ValueError("Cannot delete the last scene")

    if index < 0 or index >= len(scene_list):
        raise IndexError(
            f"Scene index {index} out of range (0-{len(scene_list) - 1})"
        )

    session.checkpoint()

    removed = scene_list[index]
    name = als_xml.get_value(removed, "Name", "Untitled")
    scenes.remove(removed)

    # Remove corresponding clip slots from all tracks
    tracks = als_xml.get_tracks_container(session.root)
    for track in tracks:
        dc = track.find("DeviceChain")
        if dc is None:
            continue
        main_seq = dc.find("MainSequencer")
        if main_seq is None:
            continue
        slot_list = main_seq.find("ClipSlotList")
        if slot_list is None:
            continue

        slots = list(slot_list)
        if index < len(slots):
            slot_list.remove(slots[index])

    return {
        "status": "deleted",
        "index": index,
        "name": name,
    }


def rename_scene(session: Session, index: int, name: str) -> dict:
    """Rename a scene.

    Args:
        session: The active session.
        index: Scene index.
        name: New scene name.

    Returns:
        Dict with result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    scenes = als_xml.get_scenes_container(session.root)
    scene_list = scenes.findall("Scene")

    if index < 0 or index >= len(scene_list):
        raise IndexError(
            f"Scene index {index} out of range (0-{len(scene_list) - 1})"
        )

    session.checkpoint()

    scene = scene_list[index]
    als_xml.set_value(scene, "Name", name)

    return {
        "status": "renamed",
        "index": index,
        "name": name,
    }


def set_scene_tempo(session: Session, index: int, tempo: float) -> dict:
    """Set a scene-specific tempo.

    Args:
        session: The active session.
        index: Scene index.
        tempo: Tempo in BPM (use -1 to follow global tempo).

    Returns:
        Dict with result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    if tempo != -1 and (tempo < 20 or tempo > 999):
        raise ValueError(f"Tempo must be 20-999 BPM or -1 (follow global), got {tempo}")

    scenes = als_xml.get_scenes_container(session.root)
    scene_list = scenes.findall("Scene")

    if index < 0 or index >= len(scene_list):
        raise IndexError(
            f"Scene index {index} out of range (0-{len(scene_list) - 1})"
        )

    session.checkpoint()

    scene = scene_list[index]
    als_xml.set_value(scene, "Tempo", str(tempo))

    return {
        "status": "set",
        "index": index,
        "tempo": tempo,
    }


# ── Helpers ─────────────────────────────────────────────────────────

def _extract_scene_info(scene_el, index: int) -> dict:
    """Extract info from a scene XML element."""
    name = als_xml.get_value(scene_el, "Name", f"Scene {index + 1}")
    tempo = als_xml.get_value(scene_el, "Tempo", "-1")
    scene_id = scene_el.get("Id", str(index))

    return {
        "index": index,
        "id": scene_id,
        "name": name,
        "tempo": float(tempo) if tempo != "-1" else None,
    }
