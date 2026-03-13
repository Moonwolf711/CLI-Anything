# TEST.md -- cli-anything-vital Test Results

## Test Suites

- **test_core.py**: Unit tests for parameters, presets, modulation, effects, session, wavetable
- **test_full_e2e.py**: End-to-end round-trip and CLI subprocess tests

## Running

```bash
cd agent-harness
pip install -e .
pip install pytest
pytest cli_anything/vital/tests/ -v --tb=short
```

## Results

### 2026-03-12 -- Initial Build (67/67 passed)

```
platform win32 -- Python 3.13.5, pytest-9.0.2
67 passed in 1.38s

test_core.py (60 tests):
  TestParameters      14/14 PASSED
  TestPreset          14/14 PASSED
  TestModulation       9/9  PASSED
  TestEffects          7/7  PASSED
  TestSession         10/10 PASSED
  TestWavetable        6/6  PASSED

test_full_e2e.py (7 tests):
  TestE2ERoundtrip     3/3  PASSED
  TestCLISubprocess    4/4  PASSED
```

Coverage areas:
- Parameter registry: 900+ params, validation, search, grouping
- Preset: create, save, load, round-trip, diff, list, search
- Modulation: add, remove, update, list sources/destinations
- Effects: enable, disable, toggle, get/set params
- Session: load, set_param, undo, redo, history, save/restore
- Wavetable: create, set, get frame
- CLI subprocess: --version, --json preset new, install-check, param list-names
