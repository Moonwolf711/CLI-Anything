"""Unit tests for Serum CLI core modules.

Tests FXP parsing, preset management, and session handling with
both synthetic data and real preset files.
"""

import json
import os
import struct
import tempfile
import zlib
from pathlib import Path

import pytest

from cli_anything.serum.core.fxp import (
    FXP_CHUNK_TYPE,
    FXP_HEADER_SIZE,
    FXP_MAGIC,
    PARAM_MAP,
    PARAM_NAME_TO_INDEX,
    SERUM_FX_ID,
    SERUM_PARAM_COUNT,
    _build_fxp_bytes,
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
    duplicate_preset,
    find_preset_dirs,
    organize_by_category,
    preset_info,
    scan_presets,
    scan_wavetables,
    search_presets,
    wavetable_info,
)
from cli_anything.serum.core.session import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def init_fxp(tmp_dir):
    """Create a valid init .fxp file and return its path."""
    path = os.path.join(tmp_dir, "init.fxp")
    write_fxp(path, "Init Patch")
    return path


@pytest.fixture
def custom_fxp(tmp_dir):
    """Create an .fxp with custom parameters."""
    path = os.path.join(tmp_dir, "custom.fxp")
    params = _default_params()
    params[1] = 0.75     # osc_a_volume = 0.75 (vidx 1)
    params[60] = 1.0     # filter1_enable = on (vidx 60)
    params[61] = 0.5     # filter1_cutoff = 0.5 (vidx 61)
    params[205] = 1.0    # fx_reverb_enable = on (vidx 205)
    write_fxp(path, "Custom Bass", params=params)
    return path


# ---------------------------------------------------------------------------
# FXP Module Tests
# ---------------------------------------------------------------------------

class TestFxpDefaults:
    """Test default parameter generation."""

    def test_default_params_length(self):
        params = _default_params()
        assert len(params) == SERUM_PARAM_COUNT

    def test_default_params_osc_a_enabled(self):
        params = _default_params()
        assert params[0] == 1.0  # osc_a_enable

    def test_default_params_master_volume(self):
        params = _default_params()
        assert abs(params[50] - 0.999) < 1e-2  # master_volume at virtual 50

    def test_default_params_match_param_map(self):
        params = _default_params()
        for idx, (name, desc, pmin, pmax, default) in PARAM_MAP.items():
            assert abs(params[idx] - default) < 1e-2, (
                f"param {idx} ({name}): expected {default}, got {params[idx]}"
            )


class TestFxpWriteRead:
    """Test .fxp write and read round-trip."""

    def test_write_creates_file(self, init_fxp):
        assert os.path.exists(init_fxp)
        assert os.path.getsize(init_fxp) > FXP_HEADER_SIZE

    def test_read_init_fxp(self, init_fxp):
        fxp = read_fxp(init_fxp)
        assert fxp["name"] == "Init Patch"
        assert fxp["fx_id"] == "XfsX"
        assert fxp["param_count"] == SERUM_PARAM_COUNT
        assert len(fxp["params"]) == SERUM_PARAM_COUNT

    def test_round_trip_params(self, init_fxp):
        fxp = read_fxp(init_fxp)
        defaults = _default_params()
        for i in range(SERUM_PARAM_COUNT):
            assert abs(fxp["params"][i] - defaults[i]) < 1e-6, (
                f"param {i}: expected {defaults[i]}, got {fxp['params'][i]}"
            )

    def test_round_trip_custom(self, custom_fxp):
        fxp = read_fxp(custom_fxp)
        assert fxp["name"] == "Custom Bass"
        assert abs(fxp["params"][1] - 0.75) < 1e-6     # osc_a_volume
        assert abs(fxp["params"][60] - 1.0) < 1e-6     # filter1_enable
        assert abs(fxp["params"][61] - 0.5) < 1e-6     # filter1_cutoff
        assert abs(fxp["params"][205] - 1.0) < 1e-6    # fx_reverb_enable

    def test_write_no_overwrite(self, init_fxp):
        with pytest.raises(FileExistsError):
            write_fxp(init_fxp, "Duplicate")

    def test_write_overwrite(self, init_fxp):
        out = write_fxp(init_fxp, "Overwritten", overwrite=True)
        fxp = read_fxp(out)
        assert fxp["name"] == "Overwritten"

    def test_write_wrong_param_count(self, tmp_dir):
        path = os.path.join(tmp_dir, "bad.fxp")
        with pytest.raises(ValueError, match="Expected 512"):
            write_fxp(path, "Bad", params=[0.0] * 100)

    def test_read_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            read_fxp("/nonexistent/file.fxp")

    def test_magic_bytes(self, init_fxp):
        with open(init_fxp, "rb") as f:
            assert f.read(4) == FXP_MAGIC
            f.seek(8)
            assert f.read(4) == FXP_CHUNK_TYPE
            f.seek(16)
            assert f.read(4) == SERUM_FX_ID


class TestFxpGetSetParam:
    """Test parameter get/set operations."""

    def test_get_by_name(self, init_fxp):
        fxp = read_fxp(init_fxp)
        info = get_param(fxp["params"], "osc_a_volume")
        assert info["index"] == 1
        assert info["name"] == "osc_a_volume"
        assert abs(info["value"] - 0.70) < 1e-2  # real init default is ~0.70

    def test_get_by_index(self, init_fxp):
        fxp = read_fxp(init_fxp)
        info = get_param(fxp["params"], 50)  # master_volume at virtual 50
        assert info["name"] == "master_volume"
        assert abs(info["value"] - 0.999) < 1e-2

    def test_get_by_index_string(self, init_fxp):
        fxp = read_fxp(init_fxp)
        info = get_param(fxp["params"], "50")  # master_volume at virtual 50
        assert info["name"] == "master_volume"

    def test_get_unknown_name(self, init_fxp):
        fxp = read_fxp(init_fxp)
        with pytest.raises(ValueError, match="Unknown parameter"):
            get_param(fxp["params"], "bogus_param")

    def test_get_out_of_range(self, init_fxp):
        fxp = read_fxp(init_fxp)
        with pytest.raises(ValueError, match="out of range"):
            get_param(fxp["params"], 999)

    def test_set_by_name(self, init_fxp):
        fxp = read_fxp(init_fxp)
        new_params = set_param(fxp["params"], "osc_a_volume", 0.9)
        assert abs(new_params[1] - 0.9) < 1e-6
        # Original not mutated
        assert abs(fxp["params"][1] - 0.70) < 1e-2  # real init default ~0.70

    def test_set_by_index(self, init_fxp):
        fxp = read_fxp(init_fxp)
        new_params = set_param(fxp["params"], 40, 0.6)
        assert abs(new_params[40] - 0.6) < 1e-6

    def test_set_out_of_range_value(self, init_fxp):
        fxp = read_fxp(init_fxp)
        with pytest.raises(ValueError, match="out of range"):
            set_param(fxp["params"], "osc_a_volume", 5.0)


class TestFxpDumpDiff:
    """Test parameter dump and diff operations."""

    def test_dump_all(self, init_fxp):
        fxp = read_fxp(init_fxp)
        result = dump_params(fxp["params"])
        assert len(result) == SERUM_PARAM_COUNT

    def test_dump_named_only(self, init_fxp):
        fxp = read_fxp(init_fxp)
        result = dump_params(fxp["params"], named_only=True)
        assert len(result) == len(PARAM_MAP)
        assert all("name" in r for r in result)

    def test_diff_identical(self, init_fxp):
        fxp = read_fxp(init_fxp)
        diffs = diff_params(fxp["params"], fxp["params"])
        assert len(diffs) == 0

    def test_diff_different(self, init_fxp, custom_fxp):
        a = read_fxp(init_fxp)
        b = read_fxp(custom_fxp)
        diffs = diff_params(a["params"], b["params"])
        assert len(diffs) > 0
        # osc_a_volume changed from ~0.70 to 0.75 (delta ~0.05)
        vol_diff = next(d for d in diffs if d["index"] == 1)
        assert abs(vol_diff["delta"] - 0.05) < 1e-2


class TestFxpValidate:
    """Test .fxp validation."""

    def test_validate_good_file(self, init_fxp):
        result = validate_fxp(init_fxp)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_nonexistent(self):
        result = validate_fxp("/nonexistent/file.fxp")
        assert result["valid"] is False

    def test_validate_bad_magic(self, tmp_dir):
        path = os.path.join(tmp_dir, "bad.fxp")
        with open(path, "wb") as f:
            f.write(b"XXXX" + b"\x00" * 100)
        result = validate_fxp(path)
        assert result["valid"] is False
        assert any("magic" in e.lower() for e in result["errors"])

    def test_validate_truncated(self, tmp_dir):
        path = os.path.join(tmp_dir, "truncated.fxp")
        with open(path, "wb") as f:
            f.write(b"CcnK\x00\x00\x00\x10")
        result = validate_fxp(path)
        assert result["valid"] is False


class TestParamNameLookup:
    """Test parameter name reverse lookup."""

    def test_all_names_unique(self):
        names = [v[0] for v in PARAM_MAP.values()]
        assert len(names) == len(set(names))

    def test_reverse_lookup(self):
        for idx, (name, *_) in PARAM_MAP.items():
            assert PARAM_NAME_TO_INDEX[name] == idx


# ---------------------------------------------------------------------------
# Preset Module Tests
# ---------------------------------------------------------------------------

class TestPresetScan:
    """Test preset scanning and searching."""

    def test_find_preset_dirs(self):
        dirs = find_preset_dirs()
        assert isinstance(dirs, list)
        assert all(isinstance(d, dict) for d in dirs)
        assert all("path" in d and "exists" in d for d in dirs)

    def test_scan_empty_dir(self, tmp_dir):
        results = scan_presets(root=tmp_dir)
        assert results == []

    def test_scan_with_files(self, tmp_dir):
        # Create some test .fxp files
        for name in ["Bass Lead.fxp", "Pad Warm.fxp", "FX Rise.fxp"]:
            write_fxp(os.path.join(tmp_dir, name), name.replace(".fxp", ""))
        results = scan_presets(root=tmp_dir)
        assert len(results) == 3
        names = [r["name"] for r in results]
        assert "Bass Lead" in names

    def test_search_found(self, tmp_dir):
        for name in ["BA - Heavy Sub.fxp", "LD - Bright Lead.fxp", "BA - Clean.fxp"]:
            write_fxp(os.path.join(tmp_dir, name), name.replace(".fxp", ""))
        results = search_presets("bass", root=tmp_dir)
        # No matches since "bass" is not in "BA -" names
        # But "BA" names don't contain "bass" -- let's search "heavy"
        results = search_presets("heavy", root=tmp_dir)
        assert len(results) == 1
        assert "Heavy" in results[0]["name"]

    def test_search_case_insensitive(self, tmp_dir):
        write_fxp(os.path.join(tmp_dir, "BASS.fxp"), "BASS")
        results = search_presets("bass", root=tmp_dir)
        assert len(results) == 1


class TestPresetInfo:
    """Test preset info extraction."""

    def test_info_fxp(self, init_fxp):
        info = preset_info(init_fxp)
        assert info["format"] == "Serum 1 FXP"
        assert info["program_name"] == "Init Patch"
        assert "summary" in info

    def test_info_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            preset_info("/nonexistent.fxp")

    def test_info_summary_structure(self, custom_fxp):
        info = preset_info(custom_fxp)
        s = info["summary"]
        assert "osc_a" in s
        assert "filter" in s
        assert "env1" in s
        assert "master" in s
        assert s["filter"]["enabled"] is True
        assert "Reverb" in s["active_effects"]


class TestPresetDuplicate:
    """Test preset duplication."""

    def test_duplicate_auto_name(self, init_fxp):
        out = duplicate_preset(init_fxp)
        assert os.path.exists(out)
        assert "Copy" in out

    def test_duplicate_custom_name(self, init_fxp, tmp_dir):
        out = duplicate_preset(init_fxp, new_name="My Variant")
        assert os.path.exists(out)
        assert "My Variant" in out

    def test_duplicate_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            duplicate_preset("/nonexistent.fxp")


class TestOrganize:
    """Test preset organization by category."""

    def test_organize_dry_run(self, tmp_dir):
        src = os.path.join(tmp_dir, "src")
        dst = os.path.join(tmp_dir, "dst")
        os.makedirs(src)

        for name in ["BA - Sub.fxp", "LD - Saw.fxp", "PD - Warm.fxp", "Random.fxp"]:
            write_fxp(os.path.join(src, name), name.replace(".fxp", ""))

        actions = organize_by_category(src, dst, dry_run=True)
        assert len(actions) == 4

        categories = set(a["category"] for a in actions)
        assert "Bass" in categories
        assert "Lead" in categories
        assert "Pad" in categories
        assert "Uncategorized" in categories

        # Dry run should NOT create files
        assert not os.path.exists(dst)


# ---------------------------------------------------------------------------
# Session Module Tests
# ---------------------------------------------------------------------------

class TestSession:
    """Test session management with undo/redo."""

    def test_initial_state(self):
        s = Session()
        assert not s.has_preset()
        assert not s.modified

    def test_set_preset(self, init_fxp):
        s = Session()
        fxp = read_fxp(init_fxp)
        s.set_preset(fxp, init_fxp)
        assert s.has_preset()
        assert s.preset["name"] == "Init Patch"

    def test_snapshot_undo(self, init_fxp):
        s = Session()
        fxp = read_fxp(init_fxp)
        s.set_preset(fxp, init_fxp)

        # Modify
        s.snapshot("set volume")
        s.preset["params"][1] = 0.9

        assert s.modified
        assert abs(s.preset["params"][1] - 0.9) < 1e-6

        # Undo
        desc = s.undo()
        assert desc == "set volume"
        assert abs(s.preset["params"][1] - 0.70) < 1e-2

    def test_redo(self, init_fxp):
        s = Session()
        fxp = read_fxp(init_fxp)
        s.set_preset(fxp, init_fxp)

        s.snapshot("change")
        s.preset["params"][1] = 0.9
        s.undo()
        s.redo()
        assert abs(s.preset["params"][1] - 0.9) < 1e-6

    def test_undo_empty(self):
        s = Session()
        s.set_preset({"name": "test", "params": [0.0] * 512})
        with pytest.raises(RuntimeError, match="Nothing to undo"):
            s.undo()

    def test_redo_empty(self):
        s = Session()
        s.set_preset({"name": "test", "params": [0.0] * 512})
        with pytest.raises(RuntimeError, match="Nothing to redo"):
            s.redo()

    def test_status(self, init_fxp):
        s = Session()
        fxp = read_fxp(init_fxp)
        s.set_preset(fxp, init_fxp)

        status = s.status()
        assert status["has_preset"] is True
        assert status["preset_name"] == "Init Patch"
        assert status["modified"] is False
        assert status["undo_count"] == 0

    def test_save_load_session(self, init_fxp, tmp_dir):
        s = Session()
        fxp = read_fxp(init_fxp)
        s.set_preset(fxp, init_fxp)
        s.snapshot("change")
        s.preset["params"][1] = 0.9

        session_path = os.path.join(tmp_dir, "test.session.json")
        saved = s.save_session(session_path)
        assert os.path.exists(saved)

        # Load into new session
        s2 = Session()
        s2.load_session(saved)
        assert s2.has_preset()
        assert abs(s2.preset["params"][1] - 0.9) < 1e-6

    def test_history(self, init_fxp):
        s = Session()
        fxp = read_fxp(init_fxp)
        s.set_preset(fxp, init_fxp)

        for i in range(5):
            s.snapshot(f"edit {i}")
            s.preset["params"][1] = float(i) / 10.0

        history = s.list_history()
        assert len(history) == 5
        assert history[0]["description"] == "edit 4"

    def test_max_undo_limit(self, init_fxp):
        s = Session()
        s.MAX_UNDO = 5
        fxp = read_fxp(init_fxp)
        s.set_preset(fxp, init_fxp)

        for i in range(10):
            s.snapshot(f"edit {i}")
            s.preset["params"][1] = float(i) / 10.0

        assert len(s._undo_stack) == 5


# ---------------------------------------------------------------------------
# Wavetable Tests
# ---------------------------------------------------------------------------

class TestWavetable:
    """Test wavetable scanning and info."""

    def test_scan_empty(self, tmp_dir):
        results = scan_wavetables(root=tmp_dir)
        assert results == []

    def test_wavetable_info_valid(self, tmp_dir):
        # Create a minimal valid WAV file
        path = os.path.join(tmp_dir, "test.wav")
        _write_minimal_wav(path, num_samples=4096, sample_rate=44100)

        info = wavetable_info(path)
        assert info["name"] == "test"
        assert info.get("sample_rate") == 44100
        assert info.get("num_frames") == 2  # 4096 / 2048

    def test_wavetable_info_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            wavetable_info("/nonexistent.wav")


def _write_minimal_wav(path: str, num_samples: int = 2048,
                       sample_rate: int = 44100) -> None:
    """Write a minimal valid WAV file for testing."""
    import struct as st
    bits = 16
    channels = 1
    data_size = num_samples * channels * (bits // 8)
    file_size = 36 + data_size  # RIFF header + fmt + data

    with open(path, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(st.pack("<I", file_size))
        f.write(b"WAVE")

        # fmt chunk
        f.write(b"fmt ")
        f.write(st.pack("<I", 16))  # chunk size
        f.write(st.pack("<H", 1))   # PCM format
        f.write(st.pack("<H", channels))
        f.write(st.pack("<I", sample_rate))
        f.write(st.pack("<I", sample_rate * channels * bits // 8))  # byte rate
        f.write(st.pack("<H", channels * bits // 8))  # block align
        f.write(st.pack("<H", bits))

        # data chunk
        f.write(b"data")
        f.write(st.pack("<I", data_size))
        f.write(b"\x00" * data_size)  # silence
