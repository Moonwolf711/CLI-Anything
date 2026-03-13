"""E2E tests for Serum CLI -- real files, real workflows, subprocess tests.

Tests operate on real preset files from the OneDrive preset library
and verify the CLI works end-to-end as a subprocess.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from cli_anything.serum.core.fxp import (
    FXP_MAGIC,
    SERUM_PARAM_COUNT,
    _default_params,
    diff_params,
    dump_params,
    get_param,
    read_fxp,
    set_param,
    validate_fxp,
    write_fxp,
)
from cli_anything.serum.core.preset import (
    find_duplicates,
    organize_by_category,
    preset_info,
    scan_presets,
    scan_wavetables,
    search_presets,
    wavetable_info,
)
from cli_anything.serum.core.session import Session

# ---------------------------------------------------------------------------
# Real preset paths
# ---------------------------------------------------------------------------

ONEDRIVE_PRESETS = Path("D:/OneDrive/Documents/Xfer/Serum Presets/Presets/User")
WAVETABLE_DIR = Path("C:/Users/Owner/Documents/Xfer/Serum Presets/Tables")
ONEDRIVE_WAVETABLES = Path("D:/OneDrive/Documents/Xfer/Serum Presets/Tables")


def _find_real_fxp() -> Path | None:
    """Find a real .fxp file for testing."""
    if ONEDRIVE_PRESETS.is_dir():
        for f in ONEDRIVE_PRESETS.glob("*.fxp"):
            try:
                f.read_bytes()
                return f
            except OSError:
                continue
    return None


def _find_real_wav() -> Path | None:
    """Find a real wavetable .wav for testing."""
    for d in [WAVETABLE_DIR, ONEDRIVE_WAVETABLES]:
        if d.is_dir():
            for f in d.rglob("*.wav"):
                try:
                    f.read_bytes()
                    return f
                except OSError:
                    continue
    return None


REAL_FXP = _find_real_fxp()
REAL_WAV = _find_real_wav()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ---------------------------------------------------------------------------
# CLI subprocess helper
# ---------------------------------------------------------------------------

def _resolve_cli(name: str) -> list[str]:
    """Resolve installed CLI command; falls back to python -m for dev."""
    import shutil

    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.serum.serum_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


# ---------------------------------------------------------------------------
# E2E: Real File Workflows
# ---------------------------------------------------------------------------

class TestCreateEditSave:
    """Workflow: Create preset -> edit params -> save -> verify."""

    def test_full_create_edit_save(self, tmp_dir):
        path = os.path.join(tmp_dir, "new_bass.fxp")

        # Create
        write_fxp(path, "E2E Bass")
        assert os.path.exists(path)

        # Read
        fxp = read_fxp(path)
        assert fxp["name"] == "E2E Bass"

        # Modify
        params = set_param(fxp["params"], "osc_a_volume", 0.9)
        params = set_param(params, "filter_enable", 1.0)
        params = set_param(params, "filter_cutoff", 0.4)
        params = set_param(params, "fx_reverb_enable", 1.0)

        # Save
        write_fxp(path, "E2E Bass Modified", params=params, overwrite=True)

        # Verify -- use current virtual indices
        fxp2 = read_fxp(path)
        assert fxp2["name"] == "E2E Bass Modified"
        assert abs(fxp2["params"][1] - 0.9) < 1e-6    # osc_a_volume (vidx 1)
        assert abs(fxp2["params"][60] - 1.0) < 1e-6   # filter1_enable (vidx 60)
        assert abs(fxp2["params"][61] - 0.4) < 1e-6   # filter1_cutoff (vidx 61)

        # Verify magic bytes
        with open(path, "rb") as f:
            assert f.read(4) == FXP_MAGIC

        size = os.path.getsize(path)
        print(f"\n  FXP: {path} ({size:,} bytes)")


class TestDuplicateDiff:
    """Workflow: Duplicate -> modify -> diff."""

    def test_duplicate_and_diff(self, tmp_dir):
        # Create original
        orig = os.path.join(tmp_dir, "original.fxp")
        write_fxp(orig, "Original")

        # Duplicate
        from cli_anything.serum.core.preset import duplicate_preset
        copy_path = duplicate_preset(orig, new_name="Copy")

        # Modify copy
        fxp = read_fxp(copy_path)
        params = set_param(fxp["params"], "master_volume", 0.5)
        params = set_param(params, "osc_a_volume", 0.3)
        write_fxp(copy_path, "Copy", params=params, overwrite=True)

        # Diff
        a = read_fxp(orig)
        b = read_fxp(copy_path)
        diffs = diff_params(a["params"], b["params"])
        assert len(diffs) >= 2

        diff_indices = {d["index"] for d in diffs}
        assert 1 in diff_indices    # osc_a_volume (vidx 1)
        assert 50 in diff_indices   # master_volume (vidx 50)

        print(f"\n  {len(diffs)} differences between original and copy")


@pytest.mark.skipif(
    not ONEDRIVE_PRESETS.is_dir(),
    reason="OneDrive Serum presets not available"
)
class TestRealPresetLibrary:
    """Workflow: Scan real preset library."""

    def test_scan_onedrive(self):
        results = scan_presets(root=str(ONEDRIVE_PRESETS))
        assert len(results) > 100, f"Expected 100+ presets, got {len(results)}"
        print(f"\n  Scanned: {len(results)} presets from OneDrive")

    def test_search_real(self):
        results = search_presets("bass", root=str(ONEDRIVE_PRESETS))
        print(f"\n  Found: {len(results)} presets matching 'bass'")

    def test_find_real_duplicates(self):
        groups = find_duplicates(root=str(ONEDRIVE_PRESETS))
        total_dupes = sum(len(g) - 1 for g in groups)
        print(f"\n  {len(groups)} duplicate groups, {total_dupes} redundant files")


@pytest.mark.skipif(REAL_FXP is None, reason="No real .fxp files available")
class TestRealFxpParsing:
    """Parse real .fxp files from the Serum library."""

    def test_read_real_fxp(self):
        fxp = read_fxp(REAL_FXP)
        assert fxp["fx_id"] == "XfsX"
        assert len(fxp["params"]) == SERUM_PARAM_COUNT
        print(f"\n  Parsed: {REAL_FXP.name}")
        print(f"    Name: {fxp['name']}")
        print(f"    Raw size: {fxp['raw_size']} bytes")
        print(f"    File size: {fxp['file_size']} bytes")

    def test_validate_real_fxp(self):
        result = validate_fxp(str(REAL_FXP))
        assert result["valid"] is True, f"Errors: {result['errors']}"
        print(f"\n  Validated: {REAL_FXP.name} (OK)")

    def test_preset_info_real(self):
        info = preset_info(str(REAL_FXP))
        assert info["format"] == "Serum 1 FXP"
        assert "summary" in info
        print(f"\n  Info: {REAL_FXP.name}")
        print(f"    Effects: {info['summary'].get('active_effects', [])}")

    def test_dump_named_params_real(self):
        fxp = read_fxp(REAL_FXP)
        params = dump_params(fxp["params"], named_only=True)
        non_default = [p for p in params if not p.get("is_default", True)]
        print(f"\n  {REAL_FXP.name}: {len(non_default)} non-default params")
        for p in non_default[:10]:
            print(f"    [{p['index']}] {p['name']} = {p['value']:.4f}")


@pytest.mark.skipif(REAL_WAV is None, reason="No real wavetable .wav available")
class TestRealWavetable:
    """Parse real wavetable files."""

    def test_wavetable_info_real(self):
        info = wavetable_info(str(REAL_WAV))
        assert "sample_rate" in info or "error" not in info
        print(f"\n  Wavetable: {REAL_WAV.name}")
        print(f"    Size: {info.get('size', 0):,} bytes")
        print(f"    Frames: {info.get('num_frames', '?')}")
        print(f"    Sample rate: {info.get('sample_rate', '?')}")


class TestSessionRoundTrip:
    """Full session workflow: open -> edit -> undo -> redo -> save -> load."""

    def test_full_session_workflow(self, tmp_dir):
        # Create a preset
        fxp_path = os.path.join(tmp_dir, "session_test.fxp")
        write_fxp(fxp_path, "Session Test")

        # Open in session
        s = Session()
        fxp = read_fxp(fxp_path)
        s.set_preset(fxp, fxp_path)

        # Make 3 edits (using current virtual indices)
        s.snapshot("set volume")
        s.preset["params"][1] = 0.9        # osc_a_volume (vidx 1)

        s.snapshot("enable reverb")
        s.preset["params"][205] = 1.0      # fx_reverb_enable (vidx 205, default 0.0)

        s.snapshot("set cutoff")
        s.preset["params"][61] = 0.3       # filter1_cutoff (vidx 61)

        assert s.status()["undo_count"] == 3

        # Undo twice
        s.undo()  # undo cutoff
        s.undo()  # undo reverb
        assert abs(s.preset["params"][205] - 0.0) < 1e-6

        # Redo once
        s.redo()  # redo reverb
        assert abs(s.preset["params"][205] - 1.0) < 1e-6

        # Save session
        session_file = os.path.join(tmp_dir, "test.session.json")
        s.save_session(session_file)
        assert os.path.exists(session_file)

        # Load in fresh session
        s2 = Session()
        s2.load_session(session_file)
        assert s2.has_preset()
        assert abs(s2.preset["params"][1] - 0.9) < 1e-6
        assert abs(s2.preset["params"][205] - 1.0) < 1e-6

        print(f"\n  Session file: {session_file}")


class TestValidationPipeline:
    """Validate multiple .fxp files (synthetic + real)."""

    def test_validate_synthetic_batch(self, tmp_dir):
        paths = []
        for i in range(5):
            p = os.path.join(tmp_dir, f"test_{i}.fxp")
            write_fxp(p, f"Test {i}")
            paths.append(p)

        results = []
        for p in paths:
            r = validate_fxp(p)
            results.append(r)
            assert r["valid"], f"{p}: {r['errors']}"

        print(f"\n  Validated {len(results)} synthetic presets (all OK)")


# ---------------------------------------------------------------------------
# CLI Subprocess Tests
# ---------------------------------------------------------------------------

class TestCLISubprocess:
    """Test the installed CLI command via subprocess."""

    CLI_BASE = _resolve_cli("cli-anything-serum")

    def _run(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True,
            text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "serum" in result.stdout.lower()

    def test_version(self):
        result = self._run(["--version"])
        assert result.returncode == 0
        assert "1.0.0" in result.stdout

    def test_install_check_json(self):
        result = self._run(["--json", "install-check"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "serum1_installed" in data

    def test_preset_dirs_json(self):
        result = self._run(["--json", "preset", "dirs"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_param_names_json(self):
        result = self._run(["--json", "param", "names"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 50
        assert data[0]["name"] == "osc_a_enable"

    def test_create_and_dump_workflow(self, tmp_dir):
        """Full workflow: create preset, dump params, verify JSON."""
        fxp_path = os.path.join(tmp_dir, "cli_test.fxp")

        # Create
        result = self._run(["--json", "preset", "create", fxp_path])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["created"] is True

        # Dump params
        result = self._run([
            "--json", "param", "dump", fxp_path, "--named-only"
        ])
        assert result.returncode == 0
        params = json.loads(result.stdout)
        assert isinstance(params, list)
        assert len(params) > 50

        # Validate
        result = self._run(["--json", "preset", "validate", fxp_path])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["valid"] is True

        # Verify file has correct magic
        with open(fxp_path, "rb") as f:
            assert f.read(4) == FXP_MAGIC

        size = os.path.getsize(fxp_path)
        print(f"\n  CLI-created FXP: {fxp_path} ({size:,} bytes)")

    def test_preset_info_json(self, tmp_dir):
        fxp_path = os.path.join(tmp_dir, "info_test.fxp")
        self._run(["preset", "create", fxp_path])

        result = self._run(["--json", "preset", "info", fxp_path])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["format"] == "Serum 1 FXP"
        assert "summary" in data

    def test_param_get_json(self, tmp_dir):
        fxp_path = os.path.join(tmp_dir, "get_test.fxp")
        self._run(["preset", "create", fxp_path])

        result = self._run([
            "--json", "param", "get", fxp_path, "osc_a_volume"
        ])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["name"] == "osc_a_volume"
        assert abs(data["value"] - 0.70) < 1e-2

    def test_param_diff_json(self, tmp_dir):
        a_path = os.path.join(tmp_dir, "diff_a.fxp")
        b_path = os.path.join(tmp_dir, "diff_b.fxp")
        self._run(["preset", "create", a_path])
        self._run(["preset", "create", b_path])

        result = self._run(["--json", "param", "diff", a_path, b_path])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        # Two identical presets should have no diffs
        assert isinstance(data, list)
        assert len(data) == 0
