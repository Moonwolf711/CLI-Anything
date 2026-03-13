"""Ableton .als file I/O — gzip-compressed XML parsing and writing.

.als files are gzip-compressed XML documents. This module handles
reading, writing, and creating new project XML trees.
"""

import gzip
import os
from lxml import etree
from typing import Optional


# ── Ableton version constants ────────────────────────────────────────
MAJOR_VERSION = "5"
MINOR_VERSION = "12.0.0"
SCHEMA_VERSION = "12.0"
CREATOR = "cli-anything-ableton"


def read_als(path: str) -> etree._Element:
    """Read an .als file and return the root XML element.

    Args:
        path: Path to the .als file.

    Returns:
        The root <Ableton> element.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the file is not valid gzip or XML.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Project file not found: {path}")

    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        raise ValueError(f"Cannot read file {path}: {e}")

    try:
        xml_data = gzip.decompress(raw)
    except gzip.BadGzipFile:
        # Maybe it's already uncompressed XML
        xml_data = raw

    try:
        root = etree.fromstring(xml_data)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Invalid XML in {path}: {e}")

    if root.tag != "Ableton":
        raise ValueError(
            f"Not an Ableton project file: root element is <{root.tag}>, "
            f"expected <Ableton>"
        )

    return root


def write_als(root: etree._Element, path: str, compress: bool = True) -> str:
    """Write an XML element tree to an .als file.

    Args:
        root: The root <Ableton> element.
        path: Output file path.
        compress: Whether to gzip-compress (default True for .als).

    Returns:
        The absolute path of the written file.
    """
    xml_bytes = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", pretty_print=True
    )

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    if compress:
        with gzip.open(path, "wb") as f:
            f.write(xml_bytes)
    else:
        with open(path, "wb") as f:
            f.write(xml_bytes)

    return os.path.abspath(path)


def serialize_xml(root: etree._Element) -> bytes:
    """Serialize an XML tree to bytes (for undo snapshots)."""
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8")


def deserialize_xml(data: bytes) -> etree._Element:
    """Deserialize bytes back to an XML element tree."""
    return etree.fromstring(data)


def to_xml_string(root: etree._Element) -> str:
    """Return pretty-printed XML as a string (for debugging)."""
    return etree.tostring(root, pretty_print=True, encoding="unicode")


# ── Template creation ────────────────────────────────────────────────

def new_ableton_root(
    major_version: str = MAJOR_VERSION,
    minor_version: str = MINOR_VERSION,
    creator: str = CREATOR,
) -> etree._Element:
    """Create a new blank <Ableton> root element.

    Returns:
        A minimal but valid Ableton project XML tree.
    """
    root = etree.Element("Ableton")
    root.set("MajorVersion", major_version)
    root.set("MinorVersion", minor_version)
    root.set("SchemaChangeCount", "4")
    root.set("Creator", creator)
    root.set("Revision", "")

    live_set = etree.SubElement(root, "LiveSet")

    # Transport
    transport = etree.SubElement(live_set, "Transport")
    _add_value_element(transport, "Tempo", "120.0")
    _add_value_element(transport, "TimeSignatureNumerator", "4")
    _add_value_element(transport, "TimeSignatureDenominator", "4")
    _add_value_element(transport, "LoopOn", "false")
    _add_value_element(transport, "LoopStart", "0")
    _add_value_element(transport, "LoopLength", "16")
    _add_value_element(transport, "CurrentTime", "0")

    # Tracks container
    etree.SubElement(live_set, "Tracks")

    # Scenes container
    scenes = etree.SubElement(live_set, "Scenes")
    _create_scene(scenes, 0, "Scene 1")

    # Master track
    master = etree.SubElement(live_set, "MasterTrack")
    _add_value_element(master, "Id", "0")
    _add_value_element(master, "Name", "Master")
    master_mixer = etree.SubElement(master, "DeviceChain")
    mixer = etree.SubElement(master_mixer, "Mixer")
    _add_automatable_value(mixer, "Volume", "1.0")
    _add_automatable_value(mixer, "Pan", "0.0")

    # Pre-hear (cue) track
    prehear = etree.SubElement(live_set, "PreHearTrack")
    _add_value_element(prehear, "Id", "-1")

    # View states
    view = etree.SubElement(live_set, "ViewStates")
    _add_value_element(view, "SessionView", "true")
    _add_value_element(view, "ArrangementView", "false")

    # Global quantization
    _add_value_element(live_set, "QuantizationGrid", "4")

    return root


def _create_scene(parent: etree._Element, index: int, name: str) -> etree._Element:
    """Create a Scene element."""
    scene = etree.SubElement(parent, "Scene")
    scene.set("Id", str(index))
    _add_value_element(scene, "Name", name)
    _add_value_element(scene, "Tempo", "-1")
    _add_value_element(scene, "TimeSignatureId", "-1")
    return scene


def _add_value_element(
    parent: etree._Element, tag: str, value: str
) -> etree._Element:
    """Add a simple <Tag Value="..."/> element."""
    elem = etree.SubElement(parent, tag)
    elem.set("Value", value)
    return elem


def _add_automatable_value(
    parent: etree._Element, tag: str, value: str
) -> etree._Element:
    """Add an automatable value element (with Manual child)."""
    elem = etree.SubElement(parent, tag)
    manual = etree.SubElement(elem, "Manual")
    manual.set("Value", value)
    auto_target = etree.SubElement(elem, "AutomationTarget")
    auto_target.set("Id", "0")
    return elem


# ── Query helpers ────────────────────────────────────────────────────

def get_live_set(root: etree._Element) -> etree._Element:
    """Get the <LiveSet> element from an Ableton root."""
    ls = root.find("LiveSet")
    if ls is None:
        raise ValueError("No <LiveSet> found in project")
    return ls


def get_tracks_container(root: etree._Element) -> etree._Element:
    """Get the <Tracks> container element."""
    ls = get_live_set(root)
    tracks = ls.find("Tracks")
    if tracks is None:
        tracks = etree.SubElement(ls, "Tracks")
    return tracks


def get_scenes_container(root: etree._Element) -> etree._Element:
    """Get the <Scenes> container element."""
    ls = get_live_set(root)
    scenes = ls.find("Scenes")
    if scenes is None:
        scenes = etree.SubElement(ls, "Scenes")
    return scenes


def get_transport(root: etree._Element) -> etree._Element:
    """Get the <Transport> element."""
    ls = get_live_set(root)
    transport = ls.find("Transport")
    if transport is None:
        transport = etree.SubElement(ls, "Transport")
    return transport


def get_master_track(root: etree._Element) -> etree._Element:
    """Get the <MasterTrack> element."""
    ls = get_live_set(root)
    master = ls.find("MasterTrack")
    if master is None:
        raise ValueError("No <MasterTrack> found in project")
    return master


def get_value(elem: etree._Element, tag: str, default: Optional[str] = None) -> Optional[str]:
    """Get the Value attribute of a child element.

    Works for both <Tag Value="x"/> and <Tag><Manual Value="x"/></Tag> patterns.
    """
    child = elem.find(tag)
    if child is None:
        return default

    # Direct Value attribute
    val = child.get("Value")
    if val is not None:
        return val

    # Automatable value with Manual sub-element
    manual = child.find("Manual")
    if manual is not None:
        return manual.get("Value", default)

    return default


def set_value(elem: etree._Element, tag: str, value: str) -> None:
    """Set the Value attribute of a child element (create if missing)."""
    child = elem.find(tag)
    if child is None:
        child = etree.SubElement(elem, tag)

    # Check for Manual sub-element (automatable)
    manual = child.find("Manual")
    if manual is not None:
        manual.set("Value", value)
    else:
        child.set("Value", value)


def next_id(root: etree._Element) -> int:
    """Generate the next unique ID for a new element."""
    max_id = 0
    for elem in root.iter():
        id_val = elem.get("Id")
        if id_val is not None:
            try:
                max_id = max(max_id, int(id_val))
            except ValueError:
                pass
    return max_id + 1
