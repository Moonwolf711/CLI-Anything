# TEST.md -- Serum CLI Test Plan and Results

## Test Inventory Plan

| File | Type | Estimated Tests |
|------|------|-----------------|
| `test_core.py` | Unit tests | ~35 tests |
| `test_full_e2e.py` | E2E + subprocess | ~20 tests |

## Unit Test Plan (test_core.py)

### Module: fxp.py
- **read_fxp**: Read real .fxp files, verify header parsing, param extraction
- **write_fxp**: Create .fxp, re-read, verify round-trip
- **get_param**: By name, by index, invalid name, out-of-range
- **set_param**: Set by name, by index, out-of-range value, boundary values
- **dump_params**: Full dump, named-only, non-default filtering
- **diff_params**: Identical presets, different presets, edge cases
- **validate_fxp**: Valid file, truncated, bad magic, corrupted
- **_default_params**: Verify init patch values match PARAM_MAP defaults
- Edge cases: Empty params, max index, 0-byte files

### Module: preset.py
- **scan_presets**: Scan real directory, empty directory
- **search_presets**: Match found, no match, case-insensitive
- **preset_info**: .fxp info, .SerumPreset info, non-existent file
- **duplicate_preset**: Copy with auto-name, copy with custom name, no-overwrite
- **find_duplicates**: Real duplicates, no duplicates
- **organize_by_category**: Prefix matching, uncategorized fallback, dry-run
- **scan_wavetables**: Find .wav files, empty dir
- **wavetable_info**: Valid WAV, invalid file

### Module: session.py
- **Session**: Create, load preset, snapshot, undo, redo, undo overflow
- **save_session / load_session**: Round-trip JSON serialization
- **status**: Verify all status fields
- **list_history**: After multiple operations

## E2E Test Plan (test_full_e2e.py)

### Real-File Workflows
1. **Create-Edit-Save**: Create init preset, modify params, save, re-read, verify
2. **Duplicate-Diff**: Duplicate a preset, modify copy, diff the two
3. **Batch Scan**: Scan the OneDrive preset directory (3000+ files)
4. **Library Organization**: Organize presets by category (dry-run)
5. **Wavetable Inspection**: Read real wavetable WAV headers
6. **Validation Pipeline**: Validate multiple real .fxp files
7. **Session Round-Trip**: Full undo/redo/save/load cycle

### CLI Subprocess Tests
- `--help` returns 0
- `--version` prints version
- `--json preset dirs` returns valid JSON
- `preset create` + `param dump --json` round-trip
- `preset validate` on a real file
- `param names --json` returns known params
- `install-check --json` returns installation info

### Output Verification
- FXP files have correct magic bytes (CcnK)
- FXP files can be round-tripped (write -> read -> compare)
- JSON output is valid JSON (parseable)
- Wavetable WAV files have RIFF header

## Realistic Workflow Scenarios

### Workflow 1: Sound Designer Preset Library Audit
**Simulates**: A sound designer auditing 3000+ presets
**Operations**: scan -> search "bass" -> find duplicates -> organize
**Verified**: Correct counts, duplicate detection, category mapping

### Workflow 2: Preset Parameter Tweaking
**Simulates**: Modifying a preset's filter and effects settings
**Operations**: open -> set filter_cutoff -> set reverb_enable -> undo -> redo -> save
**Verified**: Parameter values correct, undo/redo integrity, file validity

### Workflow 3: Agent-Driven Preset Creation
**Simulates**: An AI agent creating presets via JSON output
**Operations**: create --json -> param set -> param dump --json -> save
**Verified**: JSON parseable, params match, file valid

---

## Test Results

### Run: 2026-03-12

**Environment**: Python 3.13.5, pytest 9.0.2, Windows (MSYS_NT-10.0-26200)
**Install method**: `pip install -e ".[dev]"` (editable mode)
**Command**: `python -m pytest cli_anything/serum/tests/ -v --tb=short`

**Result: 77 passed in 84.18s**

| File | Tests | Passed | Failed | Skipped |
|------|-------|--------|--------|---------|
| `test_core.py` | 56 | 56 | 0 | 0 |
| `test_full_e2e.py` | 21 | 21 | 0 | 0 |
| **Total** | **77** | **77** | **0** | **0** |

#### test_core.py (56 tests)

| Class | Tests | Status |
|-------|-------|--------|
| TestFxpDefaults | 4 | All passed |
| TestFxpWriteRead | 9 | All passed |
| TestFxpGetSetParam | 8 | All passed |
| TestFxpDumpDiff | 4 | All passed |
| TestFxpValidate | 4 | All passed |
| TestParamNameLookup | 2 | All passed |
| TestPresetScan | 5 | All passed |
| TestPresetInfo | 3 | All passed |
| TestPresetDuplicate | 3 | All passed |
| TestOrganize | 1 | All passed |
| TestSession | 10 | All passed |
| TestWavetable | 3 | All passed |

#### test_full_e2e.py (21 tests)

| Class | Tests | Status | Notes |
|-------|-------|--------|-------|
| TestCreateEditSave | 1 | Passed | Create -> edit -> save -> verify round-trip |
| TestDuplicateDiff | 1 | Passed | Duplicate -> modify -> diff |
| TestRealPresetLibrary | 3 | Passed | OneDrive scan (3000+ presets detected) |
| TestRealFxpParsing | 4 | Passed | Real .fxp parsing, validation, param dump |
| TestRealWavetable | 1 | Passed | Real .wav wavetable inspection |
| TestSessionRoundTrip | 1 | Passed | Full undo/redo/save/load cycle |
| TestValidationPipeline | 1 | Passed | Batch validation (5 synthetic presets) |
| TestCLISubprocess | 9 | Passed | --help, --version, JSON output, workflows |

#### CLI Subprocess Tests Detail

- `--help` returns 0, contains "serum"
- `--version` returns "1.0.0"
- `--json install-check` returns valid JSON with serum1_installed key
- `--json preset dirs` returns JSON array
- `--json param names` returns 60+ named parameters
- `--json preset create` + `param dump` + `validate` round-trip: all valid
- `--json preset info` returns format, summary
- `--json param get` returns correct param value
- `--json param diff` returns empty array for identical presets
