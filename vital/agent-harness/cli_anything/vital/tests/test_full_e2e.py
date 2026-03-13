"""End-to-end tests for cli-anything-vital.

Tests the full workflow: create -> modify -> save -> reload -> verify.
Also tests CLI subprocess invocation.
"""

import json
import os
import subprocess
import sys
import tempfile

import pytest

from cli_anything.vital.core.preset import (
    create_preset, load_preset, save_preset, preset_info,
    set_param_value, get_param_value,
)
from cli_anything.vital.core.modulation import add_modulation, list_modulations
from cli_anything.vital.core.effects import enable_effect, list_effects
from cli_anything.vital.core.session import Session


def _resolve_cli(name):
    """Find the CLI executable."""
    import shutil
    exe = shutil.which(name)
    if exe:
        return [exe]
    # Fallback: run as module
    return [sys.executable, "-m", "cli_anything.vital"]


class TestE2ERoundtrip:
    """Full round-trip: create, modify, save, load, verify."""

    def test_create_modify_save_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create
            p = create_preset(name="E2E Test", author="Bot", style="Lead")

            # Modify oscillator
            set_param_value(p, "osc_1_level", 0.9)
            set_param_value(p, "osc_1_unison_voices", 4.0)
            set_param_value(p, "osc_1_unison_detune", 5.0)

            # Enable filter
            set_param_value(p, "filter_1_on", 1.0)
            set_param_value(p, "filter_1_cutoff", 80.0)
            set_param_value(p, "filter_1_resonance", 0.6)

            # Add modulation
            ok, slot, msg = add_modulation(p, "lfo_1", "filter_1_cutoff", amount=0.7)
            assert ok

            # Enable effects
            enable_effect(p, "reverb")
            set_param_value(p, "reverb_dry_wet", 0.4)

            # Set envelope
            set_param_value(p, "env_1_attack", 0.05)
            set_param_value(p, "env_1_decay", 0.8)
            set_param_value(p, "env_1_sustain", 0.6)
            set_param_value(p, "env_1_release", 0.5)

            # Save
            path = os.path.join(tmpdir, "e2e_test.vital")
            result = save_preset(p, path)
            assert os.path.isfile(path)

            # Reload
            loaded = load_preset(path)
            assert loaded["preset_name"] == "E2E Test"
            assert loaded["author"] == "Bot"

            # Verify all modifications survived round-trip
            s = loaded["settings"]
            assert s["osc_1_level"] == 0.9
            assert s["osc_1_unison_voices"] == 4.0
            assert s["osc_1_unison_detune"] == 5.0
            assert s["filter_1_on"] == 1.0
            assert s["filter_1_cutoff"] == 80.0
            assert s["filter_1_resonance"] == 0.6
            assert s["reverb_on"] == 1.0
            assert s["reverb_dry_wet"] == 0.4
            assert s["env_1_attack"] == 0.05
            assert s["env_1_sustain"] == 0.6

            # Verify modulation
            mods = list_modulations(loaded)
            assert len(mods) == 1
            assert mods[0]["source"] == "lfo_1"
            assert mods[0]["destination"] == "filter_1_cutoff"

    def test_session_undo_redo_flow(self):
        """Test undo/redo through a realistic editing session."""
        session = Session()
        session.load_preset(create_preset(name="Undo Test"))

        # Make a series of changes
        session.set_param("volume", 0.3)
        session.set_param("osc_1_level", 0.5)
        session.set_param("osc_1_pan", 0.2)

        assert session.preset["settings"]["osc_1_pan"] == 0.2

        # Undo last change
        ok, _ = session.undo()
        assert ok
        assert session.preset["settings"]["osc_1_pan"] == 0.0

        # Undo another
        ok, _ = session.undo()
        assert ok
        assert session.preset["settings"]["osc_1_level"] == 0.7

        # Redo
        ok, _ = session.redo()
        assert ok
        assert session.preset["settings"]["osc_1_level"] == 0.5

    def test_multiple_presets_workflow(self):
        """Create two presets, modify differently, compare."""
        with tempfile.TemporaryDirectory() as tmpdir:
            a = create_preset(name="Preset A")
            b = create_preset(name="Preset B")

            set_param_value(a, "volume", 0.3)
            set_param_value(b, "volume", 0.9)

            enable_effect(a, "reverb")
            enable_effect(b, "delay")

            path_a = os.path.join(tmpdir, "a.vital")
            path_b = os.path.join(tmpdir, "b.vital")
            save_preset(a, path_a)
            save_preset(b, path_b)

            loaded_a = load_preset(path_a)
            loaded_b = load_preset(path_b)

            assert loaded_a["settings"]["volume"] == 0.3
            assert loaded_b["settings"]["volume"] == 0.9
            assert loaded_a["settings"]["reverb_on"] == 1.0
            assert loaded_b["settings"]["delay_on"] == 1.0


class TestCLISubprocess:
    """Test the CLI via subprocess calls."""

    def test_version(self):
        result = subprocess.run(
            _resolve_cli("cli-anything-vital") + ["--version"],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0
        assert "1.0.0" in result.stdout

    def test_preset_new_json(self):
        result = subprocess.run(
            _resolve_cli("cli-anything-vital") + ["--json", "preset", "new", "--name", "SubTest"],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["preset_name"] == "SubTest"

    def test_install_check(self):
        result = subprocess.run(
            _resolve_cli("cli-anything-vital") + ["install-check"],
            capture_output=True, text=True, timeout=30
        )
        # Should not crash, return code 0
        assert result.returncode == 0

    def test_param_list_names(self):
        result = subprocess.run(
            _resolve_cli("cli-anything-vital") + ["param", "list-names", "--search", "volume"],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0
        assert "volume" in result.stdout.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
