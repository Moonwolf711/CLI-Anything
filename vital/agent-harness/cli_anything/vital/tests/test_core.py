"""Unit tests for cli-anything-vital core modules."""

import copy
import json
import os
import tempfile

import pytest

from cli_anything.vital.core.preset import (
    create_preset, load_preset, save_preset, preset_info,
    get_param_value, set_param_value, set_params_bulk,
    compare_presets, list_presets, search_presets,
)
from cli_anything.vital.core.parameters import (
    PARAM_REGISTRY, get_param, validate_param_value,
    list_params_by_group, search_params, get_groups,
    build_full_registry, ParamDef,
)
from cli_anything.vital.core.modulation import (
    list_modulations, add_modulation, remove_modulation,
    update_modulation, list_sources, list_destinations,
)
from cli_anything.vital.core.effects import (
    list_effects, enable_effect, disable_effect, toggle_effect,
    get_effect_params, set_effect_param,
)
from cli_anything.vital.core.session import Session
from cli_anything.vital.core.wavetable import (
    create_basic_wavetable, set_wavetable, list_wavetables,
    get_wavetable_frame, set_wavetable_frame,
)


# -- Parameter registry tests --------------------------------------------

class TestParameters:
    def test_registry_not_empty(self):
        assert len(PARAM_REGISTRY) > 100

    def test_get_known_param(self):
        p = get_param("volume")
        assert p is not None
        assert p.name == "volume"
        assert p.min_val == 0.0
        assert p.max_val == 1.0

    def test_get_unknown_param(self):
        assert get_param("nonexistent_param_xyz") is None

    def test_validate_in_range(self):
        ok, msg = validate_param_value("volume", 0.5)
        assert ok is True
        assert msg == ""

    def test_validate_out_of_range(self):
        ok, msg = validate_param_value("volume", 2.0)
        assert ok is False
        assert "out of range" in msg

    def test_validate_unknown(self):
        ok, msg = validate_param_value("nonexistent", 0.5)
        assert ok is False
        assert "Unknown" in msg

    def test_osc_params_exist(self):
        for i in range(1, 4):
            assert get_param(f"osc_{i}_level") is not None
            assert get_param(f"osc_{i}_on") is not None
            assert get_param(f"osc_{i}_tune") is not None

    def test_filter_params_exist(self):
        assert get_param("filter_1_cutoff") is not None
        assert get_param("filter_2_resonance") is not None

    def test_env_params_exist(self):
        for i in range(1, 7):
            assert get_param(f"env_{i}_attack") is not None
            assert get_param(f"env_{i}_release") is not None

    def test_lfo_params_exist(self):
        for i in range(1, 9):
            assert get_param(f"lfo_{i}_frequency") is not None

    def test_modulation_params_exist(self):
        assert get_param("modulation_1_amount") is not None
        assert get_param("modulation_64_amount") is not None

    def test_search_params(self):
        results = search_params("cutoff")
        assert len(results) > 0
        assert all("cutoff" in p.name.lower() or "cutoff" in p.description.lower() for p in results)

    def test_list_by_group(self):
        results = list_params_by_group("global")
        assert len(results) > 0
        assert all(p.group == "global" for p in results)

    def test_get_groups(self):
        groups = get_groups()
        assert "global" in groups
        assert "osc_1" in groups
        assert "chorus" in groups


# -- Preset tests ---------------------------------------------------------

class TestPreset:
    def test_create_default(self):
        p = create_preset()
        assert p["preset_name"] == "Init"
        assert "settings" in p
        assert p["settings"]["osc_1_on"] == 1.0
        assert p["settings"]["osc_2_on"] == 0.0

    def test_create_with_metadata(self):
        p = create_preset(name="Test", author="Tester", style="Bass", comments="A test")
        assert p["preset_name"] == "Test"
        assert p["author"] == "Tester"
        assert p["preset_style"] == "Bass"
        assert p["comments"] == "A test"

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = create_preset(name="Roundtrip")
            path = os.path.join(tmpdir, "test.vital")
            save_preset(p, path)
            loaded = load_preset(path)
            assert loaded["preset_name"] == "Roundtrip"
            assert loaded["settings"]["osc_1_on"] == 1.0

    def test_save_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = create_preset()
            path = os.path.join(tmpdir, "test.vital")
            save_preset(p, path)
            with pytest.raises(FileExistsError):
                save_preset(p, path, overwrite=False)

    def test_save_allows_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = create_preset()
            path = os.path.join(tmpdir, "test.vital")
            save_preset(p, path)
            save_preset(p, path, overwrite=True)  # should not raise

    def test_load_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            load_preset("/nonexistent/path.vital")

    def test_preset_info(self):
        p = create_preset(name="Info Test", author="Me")
        info = preset_info(p)
        assert info["preset_name"] == "Info Test"
        assert info["active_oscillators"] == 1
        assert info["param_count"] > 0

    def test_get_param_value(self):
        p = create_preset()
        found, val, msg = get_param_value(p, "volume")
        assert found is True
        assert isinstance(val, float)

    def test_set_param_value(self):
        p = create_preset()
        ok, msg = set_param_value(p, "volume", 0.5)
        assert ok is True
        assert p["settings"]["volume"] == 0.5

    def test_set_param_invalid(self):
        p = create_preset()
        ok, msg = set_param_value(p, "volume", 99.0)
        assert ok is False

    def test_set_params_bulk(self):
        p = create_preset()
        count, errors = set_params_bulk(p, {"volume": 0.3, "polyphony": 4.0})
        assert count == 2
        assert len(errors) == 0

    def test_compare_presets(self):
        a = create_preset(name="A")
        b = create_preset(name="B")
        b["settings"]["volume"] = 0.9
        diffs = compare_presets(a, b)
        assert diffs["total_diffs"] > 0
        assert "volume" in diffs["settings_diffs"]

    def test_list_presets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = create_preset(name="Listed")
            save_preset(p, os.path.join(tmpdir, "one.vital"))
            save_preset(p, os.path.join(tmpdir, "two.vital"))
            results = list_presets(tmpdir)
            assert len(results) == 2

    def test_search_presets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = create_preset(name="Bass Wobble")
            p2 = create_preset(name="Pad Lush")
            save_preset(p1, os.path.join(tmpdir, "bass.vital"))
            save_preset(p2, os.path.join(tmpdir, "pad.vital"))
            results = search_presets(tmpdir, "bass")
            assert len(results) == 1
            assert results[0]["preset_name"] == "Bass Wobble"


# -- Modulation tests -----------------------------------------------------

class TestModulation:
    def _preset_with_mod(self):
        p = create_preset()
        add_modulation(p, "lfo_1", "osc_1_level", amount=0.5)
        return p

    def test_add_modulation(self):
        p = create_preset()
        ok, slot, msg = add_modulation(p, "lfo_1", "osc_1_level", amount=0.7)
        assert ok is True
        assert slot == 1
        assert len(p["modulations"]) == 1

    def test_add_invalid_source(self):
        p = create_preset()
        ok, slot, msg = add_modulation(p, "invalid_source", "osc_1_level")
        assert ok is False

    def test_add_invalid_destination(self):
        p = create_preset()
        ok, slot, msg = add_modulation(p, "lfo_1", "nonexistent_param")
        assert ok is False

    def test_list_modulations(self):
        p = self._preset_with_mod()
        mods = list_modulations(p)
        assert len(mods) == 1
        assert mods[0]["source"] == "lfo_1"
        assert mods[0]["destination"] == "osc_1_level"

    def test_remove_modulation(self):
        p = self._preset_with_mod()
        ok, msg = remove_modulation(p, 1)
        assert ok is True
        assert len(p["modulations"]) == 0

    def test_remove_invalid_index(self):
        p = self._preset_with_mod()
        ok, msg = remove_modulation(p, 99)
        assert ok is False

    def test_update_modulation(self):
        p = self._preset_with_mod()
        ok, msg = update_modulation(p, 1, amount=0.9)
        assert ok is True
        assert p["settings"]["modulation_1_amount"] == 0.9

    def test_list_sources(self):
        sources = list_sources()
        assert "lfo_1" in sources
        assert "env_1" in sources

    def test_list_destinations(self):
        dests = list_destinations()
        assert "volume" in dests
        assert "osc_1_level" in dests


# -- Effects tests --------------------------------------------------------

class TestEffects:
    def test_list_effects(self):
        p = create_preset()
        effects = list_effects(p)
        assert len(effects) > 0
        names = [e["name"] for e in effects]
        assert "reverb" in names
        assert "chorus" in names

    def test_enable_effect(self):
        p = create_preset()
        ok, msg = enable_effect(p, "reverb")
        assert ok is True
        assert p["settings"]["reverb_on"] == 1.0

    def test_disable_effect(self):
        p = create_preset()
        enable_effect(p, "reverb")
        ok, msg = disable_effect(p, "reverb")
        assert ok is True
        assert p["settings"]["reverb_on"] == 0.0

    def test_toggle_effect(self):
        p = create_preset()
        ok, state, msg = toggle_effect(p, "chorus")
        assert ok is True
        assert state is True
        ok, state, msg = toggle_effect(p, "chorus")
        assert state is False

    def test_invalid_effect(self):
        p = create_preset()
        ok, msg = enable_effect(p, "nonexistent")
        assert ok is False

    def test_get_effect_params(self):
        p = create_preset()
        ok, params, msg = get_effect_params(p, "reverb")
        assert ok is True
        assert "reverb_dry_wet" in params

    def test_set_effect_param(self):
        p = create_preset()
        ok, msg = set_effect_param(p, "reverb", "dry_wet", 0.8)
        assert ok is True
        assert p["settings"]["reverb_dry_wet"] == 0.8


# -- Session tests --------------------------------------------------------

class TestSession:
    def test_initial_state(self):
        s = Session()
        assert s.has_preset is False
        assert s.preset_name == ""

    def test_load_preset(self):
        s = Session()
        p = create_preset(name="Session Test")
        s.load_preset(p)
        assert s.has_preset is True
        assert s.preset_name == "Session Test"

    def test_set_param(self):
        s = Session()
        s.load_preset(create_preset())
        ok = s.set_param("volume", 0.3)
        assert ok is True
        assert s.preset["settings"]["volume"] == 0.3
        assert s.modified is True

    def test_undo(self):
        s = Session()
        s.load_preset(create_preset())
        s.set_param("volume", 0.3)
        old_val = 0.3
        ok, desc = s.undo()
        assert ok is True
        # After undo, volume should be back to default (0.7)
        assert s.preset["settings"]["volume"] == 0.7

    def test_redo(self):
        s = Session()
        s.load_preset(create_preset())
        s.set_param("volume", 0.3)
        s.undo()
        ok, desc = s.redo()
        assert ok is True
        assert s.preset["settings"]["volume"] == 0.3

    def test_undo_empty(self):
        s = Session()
        ok, desc = s.undo()
        assert ok is False

    def test_redo_empty(self):
        s = Session()
        ok, desc = s.redo()
        assert ok is False

    def test_history(self):
        s = Session()
        s.load_preset(create_preset())
        s.set_param("volume", 0.5)
        s.set_param("polyphony", 4.0)
        history = s.get_history()
        assert len(history) >= 2

    def test_status(self):
        s = Session()
        s.load_preset(create_preset())
        status = s.status()
        assert status["has_preset"] is True
        assert status["undo_depth"] >= 0

    def test_save_and_restore(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            spath = os.path.join(tmpdir, "session.json")
            s = Session()
            s.load_preset(create_preset(name="Saved"))
            s.set_param("volume", 0.2)
            s.save_session(spath)

            s2 = Session()
            ok = s2.restore_session(spath)
            assert ok is True
            assert s2.preset["settings"]["volume"] == 0.2


# -- Wavetable tests ------------------------------------------------------

class TestWavetable:
    def test_create_basic_wavetable(self):
        wt = create_basic_wavetable("sine")
        assert "groups" in wt
        assert wt["name"] == "Sine"

    def test_create_invalid_waveform(self):
        with pytest.raises(ValueError):
            create_basic_wavetable("invalid")

    def test_set_wavetable(self):
        p = create_preset()
        wt = create_basic_wavetable("saw")
        ok, msg = set_wavetable(p, 1, wt)
        assert ok is True

    def test_set_wavetable_invalid_index(self):
        p = create_preset()
        wt = create_basic_wavetable("saw")
        ok, msg = set_wavetable(p, 0, wt)
        assert ok is False

    def test_get_wavetable_frame(self):
        p = create_preset()
        frame = get_wavetable_frame(p, 1)
        assert isinstance(frame, int)

    def test_set_wavetable_frame(self):
        p = create_preset()
        ok, msg = set_wavetable_frame(p, 1, 128)
        assert ok is True
        assert p["settings"]["osc_1_wave_frame"] == 128.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
