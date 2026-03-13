"""Unit tests for cli-anything-ableton core modules.

Tests all core functions in isolation with synthetic data.
No external dependencies required.
"""

import os
import sys
import gzip
import pytest
from lxml import etree

# Ensure imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from cli_anything.ableton.utils import als_xml
from cli_anything.ableton.core.session import Session
from cli_anything.ableton.core import project as proj_mod
from cli_anything.ableton.core import track as track_mod
from cli_anything.ableton.core import clip as clip_mod
from cli_anything.ableton.core import device as device_mod
from cli_anything.ableton.core import scene as scene_mod
from cli_anything.ableton.core import transport as transport_mod
from cli_anything.ableton.core import export as export_mod


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory."""
    return str(tmp_path)


@pytest.fixture
def session():
    """Provide a session with a new blank project."""
    s = Session()
    s.new_project()
    return s


@pytest.fixture
def session_with_tracks(session):
    """Provide a session with a project that has tracks."""
    track_mod.add_track(session, "midi", "Bass")
    track_mod.add_track(session, "midi", "Drums")
    track_mod.add_track(session, "audio", "Vocals")
    return session


@pytest.fixture
def session_with_clip(session):
    """Provide a session with a MIDI track and clip."""
    track_mod.add_track(session, "midi", "Lead")
    clip_mod.create_midi_clip(session, 0, 0, "Test Clip", 4.0)
    return session


# ============================================================================
# als_xml module tests
# ============================================================================

class TestAlsXml:
    """Tests for the als_xml utility module."""

    def test_new_ableton_root(self):
        root = als_xml.new_ableton_root()
        assert root.tag == "Ableton"
        assert root.get("MajorVersion") == "5"
        assert root.find("LiveSet") is not None

    def test_new_root_has_transport(self):
        root = als_xml.new_ableton_root()
        ls = root.find("LiveSet")
        transport = ls.find("Transport")
        assert transport is not None
        tempo = transport.find("Tempo")
        assert tempo is not None
        assert tempo.get("Value") == "120.0"

    def test_new_root_has_tracks_container(self):
        root = als_xml.new_ableton_root()
        tracks = als_xml.get_tracks_container(root)
        assert tracks is not None
        assert tracks.tag == "Tracks"
        assert len(tracks) == 0

    def test_new_root_has_scenes(self):
        root = als_xml.new_ableton_root()
        scenes = als_xml.get_scenes_container(root)
        assert scenes is not None
        assert len(scenes.findall("Scene")) == 1

    def test_new_root_has_master_track(self):
        root = als_xml.new_ableton_root()
        master = als_xml.get_master_track(root)
        assert master is not None

    def test_serialize_deserialize_roundtrip(self):
        root = als_xml.new_ableton_root()
        data = als_xml.serialize_xml(root)
        restored = als_xml.deserialize_xml(data)
        assert restored.tag == "Ableton"
        assert restored.get("MajorVersion") == root.get("MajorVersion")

    def test_get_value_direct(self):
        root = als_xml.new_ableton_root()
        transport = als_xml.get_transport(root)
        val = als_xml.get_value(transport, "Tempo")
        assert val == "120.0"

    def test_get_value_automatable(self):
        root = als_xml.new_ableton_root()
        master = als_xml.get_master_track(root)
        dc = master.find("DeviceChain")
        mixer = dc.find("Mixer")
        vol = als_xml.get_value(mixer, "Volume")
        assert vol == "1.0"

    def test_get_value_missing_returns_default(self):
        root = als_xml.new_ableton_root()
        transport = als_xml.get_transport(root)
        val = als_xml.get_value(transport, "NonExistent", "fallback")
        assert val == "fallback"

    def test_set_value(self):
        root = als_xml.new_ableton_root()
        transport = als_xml.get_transport(root)
        als_xml.set_value(transport, "Tempo", "140.0")
        assert als_xml.get_value(transport, "Tempo") == "140.0"

    def test_next_id(self):
        root = als_xml.new_ableton_root()
        id1 = als_xml.next_id(root)
        assert isinstance(id1, int)
        assert id1 > 0

    def test_to_xml_string(self):
        root = als_xml.new_ableton_root()
        xml_str = als_xml.to_xml_string(root)
        assert "<Ableton" in xml_str
        assert "<LiveSet>" in xml_str

    def test_write_read_als_roundtrip(self, tmp_dir):
        root = als_xml.new_ableton_root()
        path = os.path.join(tmp_dir, "test.als")
        als_xml.write_als(root, path, compress=True)
        assert os.path.exists(path)

        # Verify it's gzip
        with open(path, "rb") as f:
            magic = f.read(2)
        assert magic == b"\x1f\x8b"  # gzip magic bytes

        restored = als_xml.read_als(path)
        assert restored.tag == "Ableton"

    def test_write_uncompressed(self, tmp_dir):
        root = als_xml.new_ableton_root()
        path = os.path.join(tmp_dir, "test.xml")
        als_xml.write_als(root, path, compress=False)
        assert os.path.exists(path)

        with open(path, "rb") as f:
            data = f.read()
        assert b"<Ableton" in data

    def test_read_als_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            als_xml.read_als("/nonexistent/path.als")

    def test_read_als_invalid_xml(self, tmp_dir):
        path = os.path.join(tmp_dir, "bad.als")
        with gzip.open(path, "wb") as f:
            f.write(b"not xml at all")
        with pytest.raises(ValueError, match="Invalid XML"):
            als_xml.read_als(path)

    def test_read_als_wrong_root(self, tmp_dir):
        path = os.path.join(tmp_dir, "wrong.als")
        root = etree.Element("NotAbleton")
        data = etree.tostring(root)
        with gzip.open(path, "wb") as f:
            f.write(data)
        with pytest.raises(ValueError, match="Not an Ableton project"):
            als_xml.read_als(path)


# ============================================================================
# Session tests
# ============================================================================

class TestSession:
    """Tests for the session module."""

    def test_new_session(self):
        s = Session()
        assert not s.is_open
        assert not s.is_modified
        assert s.project_path is None

    def test_new_project(self):
        s = Session()
        s.new_project()
        assert s.is_open
        assert not s.is_modified
        assert s.root is not None
        assert s.root.tag == "Ableton"

    def test_open_save_roundtrip(self, tmp_dir):
        # Create and save
        s1 = Session()
        s1.new_project()
        path = os.path.join(tmp_dir, "test.als")
        s1.save(path)

        # Open in new session
        s2 = Session()
        info = s2.open_project(path)
        assert info["open"] is True
        assert s2.project_path == os.path.abspath(path)

    def test_undo_redo(self, session):
        # Get initial tempo
        transport = als_xml.get_transport(session.root)
        assert als_xml.get_value(transport, "Tempo") == "120.0"

        # Change tempo (with checkpoint)
        session.checkpoint()
        als_xml.set_value(transport, "Tempo", "140.0")
        assert als_xml.get_value(als_xml.get_transport(session.root), "Tempo") == "140.0"

        # Undo
        assert session.undo()
        assert als_xml.get_value(als_xml.get_transport(session.root), "Tempo") == "120.0"

        # Redo
        assert session.redo()
        assert als_xml.get_value(als_xml.get_transport(session.root), "Tempo") == "140.0"

    def test_undo_empty(self, session):
        assert not session.undo()

    def test_redo_empty(self, session):
        assert not session.redo()

    def test_checkpoint_sets_modified(self, session):
        assert not session.is_modified
        session.checkpoint()
        assert session.is_modified

    def test_session_info(self, session):
        info = session.session_info()
        assert "session_id" in info
        assert info["project_open"] is True
        assert info["modified"] is False

    def test_project_info(self, session):
        info = session.project_info()
        assert info["open"] is True
        assert "version" in info
        assert "transport" in info
        assert "tracks" in info
        assert info["tracks"]["total"] == 0


# ============================================================================
# Project tests
# ============================================================================

class TestProject:
    """Tests for the project module."""

    def test_new_project(self):
        s = Session()
        result = proj_mod.new_project(s)
        assert result["open"] is True
        assert result["tracks"]["total"] == 0

    def test_list_tracks_empty(self, session):
        result = proj_mod.list_tracks(session)
        assert result == []

    def test_list_tracks_with_tracks(self, session_with_tracks):
        result = proj_mod.list_tracks(session_with_tracks)
        assert len(result) == 3
        assert result[0]["name"] == "Bass"
        assert result[0]["type"] == "midi"
        assert result[2]["name"] == "Vocals"
        assert result[2]["type"] == "audio"

    def test_project_info_fields(self, session):
        result = proj_mod.project_info(session)
        assert "track_list" in result
        assert "version" in result
        assert "transport" in result

    def test_project_not_open_error(self):
        s = Session()
        with pytest.raises(RuntimeError, match="No project is open"):
            proj_mod.project_info(s)


# ============================================================================
# Track tests
# ============================================================================

class TestTrack:
    """Tests for the track module."""

    def test_add_midi_track(self, session):
        result = track_mod.add_track(session, "midi", "Bass")
        assert result["status"] == "created"
        assert result["type"] == "midi"
        assert result["name"] == "Bass"

    def test_add_audio_track(self, session):
        result = track_mod.add_track(session, "audio", "Vocals")
        assert result["type"] == "audio"

    def test_add_return_track(self, session):
        result = track_mod.add_track(session, "return", "Reverb Bus")
        assert result["type"] == "return"

    def test_add_group_track(self, session):
        result = track_mod.add_track(session, "group", "Drums Group")
        assert result["type"] == "group"

    def test_add_track_auto_name(self, session):
        result = track_mod.add_track(session, "midi")
        assert "Midi" in result["name"]

    def test_add_invalid_type(self, session):
        with pytest.raises(ValueError, match="Unknown track type"):
            track_mod.add_track(session, "invalid_type")

    def test_remove_track(self, session_with_tracks):
        result = track_mod.remove_track(session_with_tracks, 0)
        assert result["status"] == "removed"
        tracks = proj_mod.list_tracks(session_with_tracks)
        assert len(tracks) == 2

    def test_remove_track_invalid_index(self, session_with_tracks):
        with pytest.raises(IndexError):
            track_mod.remove_track(session_with_tracks, 99)

    def test_rename_track(self, session_with_tracks):
        result = track_mod.rename_track(session_with_tracks, 0, "New Name")
        assert result["name"] == "New Name"
        tracks = proj_mod.list_tracks(session_with_tracks)
        assert tracks[0]["name"] == "New Name"

    def test_set_volume(self, session_with_tracks):
        result = track_mod.set_volume(session_with_tracks, 0, 0.75)
        assert result["volume"] == 0.75

    def test_set_volume_out_of_range(self, session_with_tracks):
        with pytest.raises(ValueError, match="Volume must be"):
            track_mod.set_volume(session_with_tracks, 0, 1.5)

    def test_set_pan(self, session_with_tracks):
        result = track_mod.set_pan(session_with_tracks, 0, -0.5)
        assert result["pan"] == -0.5

    def test_set_pan_out_of_range(self, session_with_tracks):
        with pytest.raises(ValueError, match="Pan must be"):
            track_mod.set_pan(session_with_tracks, 0, 2.0)

    def test_set_mute(self, session_with_tracks):
        result = track_mod.set_mute(session_with_tracks, 0, True)
        assert result["muted"] is True

    def test_set_solo(self, session_with_tracks):
        result = track_mod.set_solo(session_with_tracks, 0, True)
        assert result["solo"] is True

    def test_set_arm(self, session_with_tracks):
        result = track_mod.set_arm(session_with_tracks, 0, True)
        assert result["armed"] is True

    def test_no_project_open(self):
        s = Session()
        with pytest.raises(RuntimeError, match="No project is open"):
            track_mod.add_track(s, "midi")


# ============================================================================
# Clip tests
# ============================================================================

class TestClip:
    """Tests for the clip module."""

    def test_create_midi_clip(self, session_with_clip):
        clips = clip_mod.list_clips(session_with_clip)
        assert len(clips) == 1
        assert clips[0]["type"] == "midi"
        assert clips[0]["name"] == "Test Clip"

    def test_create_clip_on_wrong_track_type(self, session):
        track_mod.add_track(session, "audio", "Audio Track")
        with pytest.raises(ValueError, match="not a MidiTrack"):
            clip_mod.create_midi_clip(session, 0, 0)

    def test_set_notes(self, session_with_clip):
        notes = [
            {"pitch": 60, "time": 0, "duration": 1.0, "velocity": 100},
            {"pitch": 64, "time": 1, "duration": 0.5, "velocity": 80},
            {"pitch": 67, "time": 2, "duration": 1.0, "velocity": 90},
        ]
        result = clip_mod.set_clip_notes(session_with_clip, 0, 0, notes)
        assert result["note_count"] == 3

    def test_get_notes(self, session_with_clip):
        notes = [
            {"pitch": 60, "time": 0.0, "duration": 1.0, "velocity": 100},
            {"pitch": 64, "time": 1.0, "duration": 0.5, "velocity": 80},
        ]
        clip_mod.set_clip_notes(session_with_clip, 0, 0, notes)
        retrieved = clip_mod.get_clip_notes(session_with_clip, 0, 0)
        assert len(retrieved) == 2
        assert retrieved[0]["pitch"] == 60
        assert retrieved[1]["pitch"] == 64

    def test_get_notes_empty_clip(self, session_with_clip):
        result = clip_mod.get_clip_notes(session_with_clip, 0, 0)
        assert result == []

    def test_quantize(self, session_with_clip):
        notes = [
            {"pitch": 60, "time": 0.1, "duration": 1.0, "velocity": 100},
            {"pitch": 64, "time": 0.97, "duration": 0.5, "velocity": 80},
        ]
        clip_mod.set_clip_notes(session_with_clip, 0, 0, notes)
        result = clip_mod.quantize_clip(session_with_clip, 0, 0, grid=0.25)
        assert result["notes_affected"] > 0

        # Verify quantized positions
        quantized = clip_mod.get_clip_notes(session_with_clip, 0, 0)
        assert abs(quantized[0]["time"] - 0.0) < 0.01  # 0.1 -> 0.0
        assert abs(quantized[1]["time"] - 1.0) < 0.01  # 0.97 -> 1.0

    def test_quantize_with_strength(self, session_with_clip):
        notes = [{"pitch": 60, "time": 0.1, "duration": 1.0, "velocity": 100}]
        clip_mod.set_clip_notes(session_with_clip, 0, 0, notes)
        result = clip_mod.quantize_clip(
            session_with_clip, 0, 0, grid=0.25, strength=0.5
        )
        quantized = clip_mod.get_clip_notes(session_with_clip, 0, 0)
        # 50% strength: 0.1 -> halfway to 0.0 = 0.05
        assert abs(quantized[0]["time"] - 0.05) < 0.01

    def test_duplicate_clip(self, session_with_clip):
        # Set notes in source
        notes = [{"pitch": 60, "time": 0, "duration": 1.0, "velocity": 100}]
        clip_mod.set_clip_notes(session_with_clip, 0, 0, notes)

        # Duplicate to slot 1
        result = clip_mod.duplicate_clip(session_with_clip, 0, 0, 1)
        assert result["status"] == "duplicated"

    def test_invalid_note_pitch(self, session_with_clip):
        notes = [{"pitch": 200, "time": 0, "duration": 1.0}]
        with pytest.raises(ValueError, match="pitch must be 0-127"):
            clip_mod.set_clip_notes(session_with_clip, 0, 0, notes)

    def test_invalid_note_missing_field(self, session_with_clip):
        notes = [{"pitch": 60, "time": 0}]  # Missing duration
        with pytest.raises(ValueError, match="missing required field"):
            clip_mod.set_clip_notes(session_with_clip, 0, 0, notes)

    def test_list_clips_empty(self, session):
        track_mod.add_track(session, "midi", "Empty")
        clips = clip_mod.list_clips(session)
        assert clips == []


# ============================================================================
# Device tests
# ============================================================================

class TestDevice:
    """Tests for the device module."""

    def test_add_device(self, session_with_tracks):
        result = device_mod.add_device(session_with_tracks, 0, "eq-eight")
        assert result["status"] == "added"
        assert result["device_name"] == "eq-eight"
        assert result["device_class"] == "Eq8"

    def test_list_devices(self, session_with_tracks):
        device_mod.add_device(session_with_tracks, 0, "eq-eight")
        device_mod.add_device(session_with_tracks, 0, "compressor")
        devices = device_mod.list_devices(session_with_tracks, 0)
        assert len(devices) == 2

    def test_remove_device(self, session_with_tracks):
        device_mod.add_device(session_with_tracks, 0, "eq-eight")
        result = device_mod.remove_device(session_with_tracks, 0, 0)
        assert result["status"] == "removed"
        devices = device_mod.list_devices(session_with_tracks, 0)
        assert len(devices) == 0

    def test_set_parameter(self, session_with_tracks):
        device_mod.add_device(session_with_tracks, 0, "eq-eight")
        result = device_mod.set_device_parameter(
            session_with_tracks, 0, 0, "Gain", "6.0"
        )
        assert result["status"] == "set"

    def test_toggle_device(self, session_with_tracks):
        device_mod.add_device(session_with_tracks, 0, "eq-eight")
        result = device_mod.toggle_device(session_with_tracks, 0, 0, False)
        assert result["enabled"] is False

        result = device_mod.toggle_device(session_with_tracks, 0, 0)
        assert result["enabled"] is True

    def test_available_devices(self):
        devices = device_mod.list_available_devices()
        assert len(devices) > 20
        names = [d["name"] for d in devices]
        assert "eq-eight" in names
        assert "compressor" in names
        assert "reverb" in names

    def test_add_invalid_device(self, session_with_tracks):
        with pytest.raises(ValueError, match="Unknown device"):
            device_mod.add_device(session_with_tracks, 0, "nonexistent")


# ============================================================================
# Scene tests
# ============================================================================

class TestScene:
    """Tests for the scene module."""

    def test_list_scenes_default(self, session):
        scenes = scene_mod.list_scenes(session)
        assert len(scenes) == 1
        assert scenes[0]["name"] == "Scene 1"

    def test_create_scene(self, session):
        result = scene_mod.create_scene(session, "Verse")
        assert result["status"] == "created"
        assert result["name"] == "Verse"
        scenes = scene_mod.list_scenes(session)
        assert len(scenes) == 2

    def test_delete_scene(self, session):
        scene_mod.create_scene(session, "Extra")
        result = scene_mod.delete_scene(session, 1)
        assert result["status"] == "deleted"
        scenes = scene_mod.list_scenes(session)
        assert len(scenes) == 1

    def test_delete_last_scene_error(self, session):
        with pytest.raises(ValueError, match="Cannot delete the last scene"):
            scene_mod.delete_scene(session, 0)

    def test_rename_scene(self, session):
        result = scene_mod.rename_scene(session, 0, "Intro")
        assert result["name"] == "Intro"
        scenes = scene_mod.list_scenes(session)
        assert scenes[0]["name"] == "Intro"

    def test_set_scene_tempo(self, session):
        result = scene_mod.set_scene_tempo(session, 0, 140.0)
        assert result["tempo"] == 140.0


# ============================================================================
# Transport tests
# ============================================================================

class TestTransport:
    """Tests for the transport module."""

    def test_get_transport(self, session):
        result = transport_mod.get_transport(session)
        assert result["tempo"] == 120.0
        assert result["time_signature"]["numerator"] == 4
        assert result["time_signature"]["denominator"] == 4

    def test_set_tempo(self, session):
        result = transport_mod.set_tempo(session, 140.0)
        assert result["tempo"] == 140.0
        info = transport_mod.get_transport(session)
        assert info["tempo"] == 140.0

    def test_set_tempo_invalid(self, session):
        with pytest.raises(ValueError, match="Tempo must be"):
            transport_mod.set_tempo(session, 10.0)

    def test_set_time_signature(self, session):
        result = transport_mod.set_time_signature(session, 3, 4)
        assert result["time_signature"] == "3/4"

    def test_set_time_signature_invalid_numerator(self, session):
        with pytest.raises(ValueError, match="Numerator"):
            transport_mod.set_time_signature(session, 0, 4)

    def test_set_time_signature_invalid_denominator(self, session):
        with pytest.raises(ValueError, match="Denominator"):
            transport_mod.set_time_signature(session, 4, 3)

    def test_set_loop(self, session):
        result = transport_mod.set_loop(session, enabled=True, start=4.0, length=8.0)
        assert result["loop"]["enabled"] is True
        assert result["loop"]["start"] == 4.0
        assert result["loop"]["length"] == 8.0


# ============================================================================
# Export tests
# ============================================================================

class TestExport:
    """Tests for the export module."""

    def test_export_als(self, session, tmp_dir):
        path = os.path.join(tmp_dir, "output.als")
        result = export_mod.export_als(session, path)
        assert result["status"] == "exported"
        assert result["format"] == "als"
        assert os.path.exists(path)
        assert result["file_size"] > 0

        # Verify gzip
        with open(path, "rb") as f:
            assert f.read(2) == b"\x1f\x8b"

    def test_export_xml(self, session, tmp_dir):
        path = os.path.join(tmp_dir, "output.xml")
        result = export_mod.export_xml(session, path)
        assert result["format"] == "xml"
        assert result["compressed"] is False
        with open(path, "rb") as f:
            data = f.read()
        assert b"<Ableton" in data

    def test_export_als_overwrite_protection(self, session, tmp_dir):
        path = os.path.join(tmp_dir, "output.als")
        export_mod.export_als(session, path)
        with pytest.raises(FileExistsError):
            export_mod.export_als(session, path)

    def test_export_als_overwrite_flag(self, session, tmp_dir):
        path = os.path.join(tmp_dir, "output.als")
        export_mod.export_als(session, path)
        result = export_mod.export_als(session, path, overwrite=True)
        assert result["status"] == "exported"

    def test_export_midi(self, session_with_clip, tmp_dir):
        # Add notes
        notes = [
            {"pitch": 60, "time": 0, "duration": 1.0, "velocity": 100},
            {"pitch": 64, "time": 1, "duration": 0.5, "velocity": 80},
            {"pitch": 67, "time": 2, "duration": 1.0, "velocity": 90},
        ]
        clip_mod.set_clip_notes(session_with_clip, 0, 0, notes)

        path = os.path.join(tmp_dir, "output.mid")
        result = export_mod.export_midi(session_with_clip, path, 0, 0)
        assert result["status"] == "exported"
        assert result["format"] == "midi"
        assert result["note_count"] == 3
        assert os.path.exists(path)

        # Verify MIDI file magic bytes
        with open(path, "rb") as f:
            header = f.read(4)
        assert header == b"MThd"
        print(f"\n  MIDI: {path} ({result['file_size']:,} bytes)")

    def test_export_midi_empty_clip(self, session_with_clip, tmp_dir):
        path = os.path.join(tmp_dir, "empty.mid")
        with pytest.raises(ValueError, match="No notes found"):
            export_mod.export_midi(session_with_clip, path, 0, 0)

    def test_midi_var_length_encoding(self):
        """Test variable-length quantity encoding for MIDI."""
        assert export_mod._write_var_length(0) == b"\x00"
        assert export_mod._write_var_length(127) == b"\x7f"
        assert export_mod._write_var_length(128) == b"\x81\x00"
        assert export_mod._write_var_length(16383) == b"\xff\x7f"


# ============================================================================
# Integration / workflow tests
# ============================================================================

class TestWorkflows:
    """Tests for realistic multi-step workflows."""

    def test_beat_production_workflow(self, tmp_dir):
        """Simulate a producer creating a beat from scratch."""
        session = Session()
        proj_mod.new_project(session)

        # Add tracks
        track_mod.add_track(session, "midi", "Drums")
        track_mod.add_track(session, "midi", "Bass")
        track_mod.add_track(session, "midi", "Keys")
        track_mod.add_track(session, "audio", "Vocals")

        # Set tempo
        transport_mod.set_tempo(session, 140.0)

        # Create drum clip with kick pattern
        clip_mod.create_midi_clip(session, 0, 0, "Kick", 4.0)
        kick_notes = [
            {"pitch": 36, "time": 0.0, "duration": 0.25, "velocity": 127},
            {"pitch": 36, "time": 1.0, "duration": 0.25, "velocity": 120},
            {"pitch": 36, "time": 2.0, "duration": 0.25, "velocity": 127},
            {"pitch": 36, "time": 3.0, "duration": 0.25, "velocity": 120},
        ]
        clip_mod.set_clip_notes(session, 0, 0, kick_notes)

        # Create bass clip
        clip_mod.create_midi_clip(session, 1, 0, "Bass Line", 4.0)
        bass_notes = [
            {"pitch": 36, "time": 0.0, "duration": 0.5, "velocity": 100},
            {"pitch": 39, "time": 1.0, "duration": 0.5, "velocity": 90},
            {"pitch": 43, "time": 2.0, "duration": 1.0, "velocity": 95},
        ]
        clip_mod.set_clip_notes(session, 1, 0, bass_notes)

        # Add devices
        device_mod.add_device(session, 0, "eq-eight")
        device_mod.add_device(session, 0, "compressor")
        device_mod.add_device(session, 1, "eq-eight")

        # Set mixer
        track_mod.set_volume(session, 0, 0.85)
        track_mod.set_volume(session, 1, 0.75)
        track_mod.set_pan(session, 3, 0.3)

        # Verify
        info = session.project_info()
        assert info["tracks"]["total"] == 4
        assert info["tracks"]["midi"] == 3
        assert info["tracks"]["audio"] == 1
        assert info["transport"]["tempo"] == "140.0"

        clips = clip_mod.list_clips(session)
        assert len(clips) == 2

        # Save
        path = os.path.join(tmp_dir, "beat.als")
        session.save(path)
        assert os.path.exists(path)

    def test_undo_redo_workflow(self, tmp_dir):
        """Test undo/redo through a series of operations."""
        session = Session()
        proj_mod.new_project(session)

        # Add tracks
        track_mod.add_track(session, "midi", "Track 1")
        track_mod.add_track(session, "midi", "Track 2")

        # Verify 2 tracks
        tracks = proj_mod.list_tracks(session)
        assert len(tracks) == 2

        # Remove track 1
        track_mod.remove_track(session, 1)
        tracks = proj_mod.list_tracks(session)
        assert len(tracks) == 1

        # Undo removal
        session.undo()
        tracks = proj_mod.list_tracks(session)
        assert len(tracks) == 2

        # Redo removal
        session.redo()
        tracks = proj_mod.list_tracks(session)
        assert len(tracks) == 1

    def test_midi_export_pipeline(self, tmp_dir):
        """Test creating a clip and exporting as MIDI."""
        session = Session()
        proj_mod.new_project(session)

        # Build a chord progression
        track_mod.add_track(session, "midi", "Chords")
        clip_mod.create_midi_clip(session, 0, 0, "Progression", 16.0)

        # C major chord
        notes = [
            {"pitch": 60, "time": 0, "duration": 4.0, "velocity": 80},
            {"pitch": 64, "time": 0, "duration": 4.0, "velocity": 70},
            {"pitch": 67, "time": 0, "duration": 4.0, "velocity": 70},
            # F major chord
            {"pitch": 65, "time": 4, "duration": 4.0, "velocity": 80},
            {"pitch": 69, "time": 4, "duration": 4.0, "velocity": 70},
            {"pitch": 72, "time": 4, "duration": 4.0, "velocity": 70},
            # G major chord
            {"pitch": 67, "time": 8, "duration": 4.0, "velocity": 80},
            {"pitch": 71, "time": 8, "duration": 4.0, "velocity": 70},
            {"pitch": 74, "time": 8, "duration": 4.0, "velocity": 70},
            # C major chord (resolution)
            {"pitch": 60, "time": 12, "duration": 4.0, "velocity": 85},
            {"pitch": 64, "time": 12, "duration": 4.0, "velocity": 75},
            {"pitch": 67, "time": 12, "duration": 4.0, "velocity": 75},
        ]
        clip_mod.set_clip_notes(session, 0, 0, notes)

        # Export MIDI
        mid_path = os.path.join(tmp_dir, "chords.mid")
        result = export_mod.export_midi(session, mid_path, 0, 0)

        assert os.path.exists(mid_path)
        assert result["note_count"] == 12

        # Verify MIDI file structure
        with open(mid_path, "rb") as f:
            data = f.read()

        # MThd header
        assert data[:4] == b"MThd"
        # Format 0
        assert data[8:10] == b"\x00\x00"
        # 1 track
        assert data[10:12] == b"\x00\x01"
        # MTrk chunk
        assert b"MTrk" in data

        print(f"\n  MIDI: {mid_path} ({os.path.getsize(mid_path):,} bytes)")
