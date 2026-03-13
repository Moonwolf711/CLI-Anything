"""End-to-end tests for cli-anything-ableton.

Tests real file I/O, .als format validation, MIDI export verification,
and full CLI subprocess invocation.
"""

import os
import sys
import json
import gzip
import struct
import subprocess
import pytest
from lxml import etree

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from cli_anything.ableton.core.session import Session
from cli_anything.ableton.core import project as proj_mod
from cli_anything.ableton.core import track as track_mod
from cli_anything.ableton.core import clip as clip_mod
from cli_anything.ableton.core import device as device_mod
from cli_anything.ableton.core import scene as scene_mod
from cli_anything.ableton.core import transport as transport_mod
from cli_anything.ableton.core import export as export_mod
from cli_anything.ableton.utils import als_xml


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir(tmp_path):
    return str(tmp_path)


# ── Helpers ─────────────────────────────────────────────────────────

def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev.

    Set env CLI_ANYTHING_FORCE_INSTALLED=1 to require the installed command.
    """
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    # Fallback: run as python -m cli_anything.ableton
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m cli_anything.ableton")
    return [sys.executable, "-m", "cli_anything.ableton"]


# ============================================================================
# Real file E2E tests
# ============================================================================

class TestAlsFileE2E:
    """Tests that verify real .als file creation and structure."""

    def test_create_and_verify_als(self, tmp_dir):
        """Create a project, save as .als, verify gzip XML structure."""
        session = Session()
        proj_mod.new_project(session)
        track_mod.add_track(session, "midi", "Synth")
        track_mod.add_track(session, "audio", "Audio")
        transport_mod.set_tempo(session, 128.0)

        path = os.path.join(tmp_dir, "test_project.als")
        session.save(path)

        # Verify file exists
        assert os.path.exists(path)
        size = os.path.getsize(path)
        assert size > 0
        print(f"\n  ALS: {path} ({size:,} bytes)")

        # Verify gzip magic bytes
        with open(path, "rb") as f:
            magic = f.read(2)
        assert magic == b"\x1f\x8b", "File is not gzip-compressed"

        # Verify XML content
        with open(path, "rb") as f:
            raw = f.read()
        xml_data = gzip.decompress(raw)
        root = etree.fromstring(xml_data)
        assert root.tag == "Ableton"

        # Verify structure
        live_set = root.find("LiveSet")
        assert live_set is not None
        tracks = live_set.find("Tracks")
        assert tracks is not None
        assert len(tracks) == 2

    def test_full_project_roundtrip(self, tmp_dir):
        """Create a complex project, save, reopen, verify everything preserved."""
        # Build project
        session = Session()
        proj_mod.new_project(session)

        # Add tracks
        track_mod.add_track(session, "midi", "Drums")
        track_mod.add_track(session, "midi", "Bass")
        track_mod.add_track(session, "midi", "Lead")
        track_mod.add_track(session, "audio", "Vox")
        track_mod.add_track(session, "return", "Reverb")

        # Set transport
        transport_mod.set_tempo(session, 95.5)
        transport_mod.set_time_signature(session, 3, 4)
        transport_mod.set_loop(session, enabled=True, start=0, length=12)

        # Create clips with notes
        clip_mod.create_midi_clip(session, 0, 0, "Beat", 4.0)
        clip_mod.set_clip_notes(session, 0, 0, [
            {"pitch": 36, "time": 0, "duration": 0.25, "velocity": 127},
            {"pitch": 38, "time": 1, "duration": 0.25, "velocity": 100},
            {"pitch": 42, "time": 0, "duration": 0.25, "velocity": 90},
            {"pitch": 42, "time": 0.5, "duration": 0.25, "velocity": 70},
        ])

        clip_mod.create_midi_clip(session, 1, 0, "Bass Line", 4.0)
        clip_mod.set_clip_notes(session, 1, 0, [
            {"pitch": 36, "time": 0, "duration": 2.0, "velocity": 100},
            {"pitch": 43, "time": 2, "duration": 2.0, "velocity": 90},
        ])

        # Add devices
        device_mod.add_device(session, 0, "eq-eight")
        device_mod.add_device(session, 0, "compressor")
        device_mod.add_device(session, 1, "auto-filter")

        # Add scenes
        scene_mod.create_scene(session, "Chorus")
        scene_mod.create_scene(session, "Bridge")

        # Set mixer
        track_mod.set_volume(session, 0, 0.8)
        track_mod.set_pan(session, 3, 0.4)
        track_mod.set_mute(session, 4, True)

        # Save
        path = os.path.join(tmp_dir, "complex.als")
        session.save(path)

        # Reopen in a new session
        session2 = Session()
        session2.open_project(path)

        info = session2.project_info()
        assert info["tracks"]["total"] == 5
        assert info["tracks"]["midi"] == 3
        assert info["tracks"]["audio"] == 1
        assert info["tracks"]["return"] == 1
        assert info["transport"]["tempo"] == "95.5"
        assert info["scenes"] == 3

        # Verify clips survived
        clips = clip_mod.list_clips(session2)
        assert len(clips) == 2

        # Verify notes survived
        drum_notes = clip_mod.get_clip_notes(session2, 0, 0)
        assert len(drum_notes) == 4

        bass_notes = clip_mod.get_clip_notes(session2, 1, 0)
        assert len(bass_notes) == 2

        print(f"\n  ALS roundtrip: {path} ({os.path.getsize(path):,} bytes)")

    def test_midi_export_format(self, tmp_dir):
        """Export MIDI and verify the file format structure."""
        session = Session()
        proj_mod.new_project(session)
        track_mod.add_track(session, "midi", "Test")
        clip_mod.create_midi_clip(session, 0, 0, "Notes", 4.0)
        clip_mod.set_clip_notes(session, 0, 0, [
            {"pitch": 60, "time": 0, "duration": 1.0, "velocity": 100},
            {"pitch": 62, "time": 1, "duration": 1.0, "velocity": 90},
            {"pitch": 64, "time": 2, "duration": 1.0, "velocity": 80},
            {"pitch": 65, "time": 3, "duration": 1.0, "velocity": 70},
        ])

        mid_path = os.path.join(tmp_dir, "test.mid")
        result = export_mod.export_midi(session, mid_path, 0, 0)

        assert os.path.exists(mid_path)
        size = os.path.getsize(mid_path)
        assert size > 0

        with open(mid_path, "rb") as f:
            data = f.read()

        # MThd header
        assert data[:4] == b"MThd", "Missing MThd header"
        header_len = struct.unpack(">I", data[4:8])[0]
        assert header_len == 6

        # Format type 0
        fmt = struct.unpack(">H", data[8:10])[0]
        assert fmt == 0, f"Expected format 0, got {fmt}"

        # 1 track
        num_tracks = struct.unpack(">H", data[10:12])[0]
        assert num_tracks == 1

        # Division (ticks per beat)
        division = struct.unpack(">H", data[12:14])[0]
        assert division == 480  # Our TICKS_PER_BEAT constant

        # MTrk chunk follows
        assert data[14:18] == b"MTrk", "Missing MTrk chunk"

        print(f"\n  MIDI: {mid_path} ({size:,} bytes)")

    def test_multiple_track_types(self, tmp_dir):
        """Test project with all track types."""
        session = Session()
        proj_mod.new_project(session)

        track_mod.add_track(session, "midi", "MIDI Track")
        track_mod.add_track(session, "audio", "Audio Track")
        track_mod.add_track(session, "return", "Return Track")
        track_mod.add_track(session, "group", "Group Track")

        path = os.path.join(tmp_dir, "all_types.als")
        session.save(path)

        # Reopen and verify
        session2 = Session()
        session2.open_project(path)
        tracks = proj_mod.list_tracks(session2)
        types = [t["type"] for t in tracks]
        assert "midi" in types
        assert "audio" in types
        assert "return" in types
        assert "group" in types

    def test_export_uncompressed_xml(self, tmp_dir):
        """Test XML export for debugging."""
        session = Session()
        proj_mod.new_project(session)
        track_mod.add_track(session, "midi", "Debug Track")

        xml_path = os.path.join(tmp_dir, "debug.xml")
        result = export_mod.export_xml(session, xml_path)

        assert os.path.exists(xml_path)
        with open(xml_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "<Ableton" in content
        assert "<MidiTrack" in content
        assert "Debug Track" in content

        print(f"\n  XML: {xml_path} ({result['file_size']:,} bytes)")


# ============================================================================
# CLI Subprocess tests
# ============================================================================

class TestCLISubprocess:
    """Tests that invoke the installed CLI command via subprocess."""

    CLI_BASE = _resolve_cli("cli-anything-ableton")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "Ableton" in result.stdout or "ableton" in result.stdout

    def test_project_new_json(self, tmp_dir):
        out_path = os.path.join(tmp_dir, "new.als")
        result = self._run(["--json", "project", "new", "-o", out_path])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["open"] is True
        assert os.path.exists(out_path)

    def test_project_info_json(self, tmp_dir):
        als_path = os.path.join(tmp_dir, "info_test.als")
        self._run(["project", "new", "-o", als_path])
        result = self._run(["--json", "--project", als_path, "project", "info"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "tracks" in data
        assert "transport" in data

    def test_track_operations(self, tmp_dir):
        als_path = os.path.join(tmp_dir, "track_test.als")
        self._run(["project", "new", "-o", als_path])

        # Add track (positional args: type name)
        result = self._run([
            "--json", "--project", als_path, "-s",
            "track", "add", "midi", "TestTrack"
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "created"
        assert data["name"] == "TestTrack"

        # List tracks
        result = self._run(["--json", "--project", als_path, "track", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["name"] == "TestTrack"

    def test_clip_operations(self, tmp_dir):
        als_path = os.path.join(tmp_dir, "clip_test.als")
        self._run(["project", "new", "-o", als_path])
        self._run(["--project", als_path, "-s", "track", "add", "midi"])

        # Create clip (add-midi)
        result = self._run([
            "--json", "--project", als_path, "-s",
            "clip", "add-midi", "0", "0", "-n", "TestClip"
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "created"

        # Add a note using note add
        result = self._run([
            "--json", "--project", als_path, "-s",
            "note", "add", "0", "0", "-p", "60", "-t", "0", "-d", "1.0", "-v", "100"
        ])
        assert result.returncode == 0

        # Get notes using note list
        result = self._run([
            "--json", "--project", als_path,
            "note", "list", "0", "0"
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["pitch"] == 60

    def test_device_operations(self, tmp_dir):
        als_path = os.path.join(tmp_dir, "device_test.als")
        self._run(["project", "new", "-o", als_path])
        self._run(["--project", als_path, "-s", "track", "add", "midi"])

        # Add device
        result = self._run([
            "--json", "--project", als_path, "-s",
            "device", "add", "0", "eq-eight"
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["device_name"] == "eq-eight"

        # List devices
        result = self._run([
            "--json", "--project", als_path,
            "device", "list", "0"
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 1

        # Available devices
        result = self._run(["--json", "device", "list-available"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) > 20

    def test_scene_operations(self, tmp_dir):
        als_path = os.path.join(tmp_dir, "scene_test.als")
        self._run(["project", "new", "-o", als_path])

        # Create scene
        result = self._run([
            "--json", "--project", als_path, "-s",
            "scene", "create", "-n", "Verse"
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["name"] == "Verse"

        # List scenes
        result = self._run([
            "--json", "--project", als_path,
            "scene", "list"
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 2

    def test_transport_operations(self, tmp_dir):
        als_path = os.path.join(tmp_dir, "transport_test.als")
        self._run(["project", "new", "-o", als_path])

        # Set tempo
        result = self._run([
            "--json", "--project", als_path, "-s",
            "transport", "set-tempo", "140"
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["tempo"] == 140.0

        # Get transport info
        result = self._run([
            "--json", "--project", als_path,
            "transport", "get"
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["tempo"] == 140.0

    def test_export_als_subprocess(self, tmp_dir):
        als_path = os.path.join(tmp_dir, "export_src.als")
        export_path = os.path.join(tmp_dir, "exported.als")
        self._run(["project", "new", "-o", als_path])
        self._run([
            "--project", als_path, "-s",
            "track", "add", "midi", "TestTrack"
        ])

        result = self._run([
            "--json", "--project", als_path,
            "export", "als", export_path, "--overwrite"
        ])
        assert result.returncode == 0
        assert os.path.exists(export_path)

        # Verify gzip
        with open(export_path, "rb") as f:
            magic = f.read(2)
        assert magic == b"\x1f\x8b"

        print(f"\n  ALS export: {export_path} ({os.path.getsize(export_path):,} bytes)")

    def test_export_midi_subprocess(self, tmp_dir):
        als_path = os.path.join(tmp_dir, "midi_src.als")
        mid_path = os.path.join(tmp_dir, "output.mid")

        self._run(["project", "new", "-o", als_path])
        self._run(["--project", als_path, "-s", "track", "add", "midi"])
        self._run([
            "--project", als_path, "-s",
            "clip", "add-midi", "0", "0", "-n", "Notes"
        ])

        # Add notes via note add
        self._run([
            "--project", als_path, "-s",
            "note", "add", "0", "0", "-p", "60", "-t", "0", "-d", "1.0", "-v", "100"
        ])
        self._run([
            "--project", als_path, "-s",
            "note", "add", "0", "0", "-p", "64", "-t", "1", "-d", "0.5", "-v", "80"
        ])

        result = self._run([
            "--json", "--project", als_path,
            "export", "midi", mid_path, "0", "0", "--overwrite"
        ])
        assert result.returncode == 0
        assert os.path.exists(mid_path)

        # Verify MIDI magic bytes
        with open(mid_path, "rb") as f:
            header = f.read(4)
        assert header == b"MThd"

        print(f"\n  MIDI export: {mid_path} ({os.path.getsize(mid_path):,} bytes)")

    def test_full_workflow_json(self, tmp_dir):
        """Complete workflow: create -> tracks -> clips -> notes -> devices -> save -> export."""
        als_path = os.path.join(tmp_dir, "workflow.als")
        mid_path = os.path.join(tmp_dir, "workflow.mid")

        # Create project
        self._run(["project", "new", "-o", als_path])

        # Add tracks
        self._run(["--project", als_path, "-s", "track", "add", "midi", "Drums"])
        self._run(["--project", als_path, "-s", "track", "add", "midi", "Bass"])
        self._run(["--project", als_path, "-s", "track", "add", "audio", "Vox"])

        # Set tempo
        self._run(["--project", als_path, "-s", "transport", "set-tempo", "120"])

        # Create clip
        self._run([
            "--project", als_path, "-s",
            "clip", "add-midi", "0", "0", "-n", "Beat"
        ])

        # Add notes via note add
        self._run([
            "--project", als_path, "-s",
            "note", "add", "0", "0", "-p", "36", "-t", "0", "-d", "0.25", "-v", "127"
        ])
        self._run([
            "--project", als_path, "-s",
            "note", "add", "0", "0", "-p", "38", "-t", "1", "-d", "0.25", "-v", "100"
        ])
        self._run([
            "--project", als_path, "-s",
            "note", "add", "0", "0", "-p", "42", "-t", "0.5", "-d", "0.25", "-v", "80"
        ])

        # Add device
        self._run([
            "--project", als_path, "-s",
            "device", "add", "0", "compressor"
        ])

        # Create scene
        self._run(["--project", als_path, "-s", "scene", "create", "-n", "Chorus"])

        # Verify via JSON info
        result = self._run(["--json", "--project", als_path, "project", "info"])
        data = json.loads(result.stdout)
        assert data["tracks"]["total"] == 3
        assert data["scenes"] == 2

        # Export MIDI
        self._run([
            "--project", als_path,
            "export", "midi", mid_path, "0", "0", "--overwrite"
        ])
        assert os.path.exists(mid_path)
        with open(mid_path, "rb") as f:
            assert f.read(4) == b"MThd"

        print(f"\n  Full workflow:")
        print(f"    ALS: {als_path} ({os.path.getsize(als_path):,} bytes)")
        print(f"    MIDI: {mid_path} ({os.path.getsize(mid_path):,} bytes)")

    def test_install_check(self):
        """Test install-check command."""
        result = self._run(["--json", "install-check"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "installed" in data
