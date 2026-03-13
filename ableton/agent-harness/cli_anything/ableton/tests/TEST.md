# TEST.md — cli-anything-ableton Test Plan & Results

## Part 1: Test Plan

### Test Inventory

| File | Description | Estimated Tests |
|------|-------------|----------------|
| `test_core.py` | Unit tests for all core modules | ~55 tests |
| `test_full_e2e.py` | E2E tests with real .als files + subprocess CLI tests | ~20 tests |

### Unit Test Plan (test_core.py)

#### als_xml module (~10 tests)
- `test_new_ableton_root` — Verify blank project has correct structure
- `test_serialize_deserialize_roundtrip` — XML bytes roundtrip
- `test_get_live_set` — Retrieve LiveSet from root
- `test_get_value_direct` — Get Value= attributes
- `test_get_value_automatable` — Get Manual/Value= attributes
- `test_set_value` — Set values on elements
- `test_next_id` — ID generation
- Edge cases: missing elements, empty projects

#### session module (~8 tests)
- `test_new_session` — Fresh session state
- `test_new_project` — Create project in session
- `test_open_save_roundtrip` — Open, modify, save, re-open
- `test_undo_redo` — Undo/redo stack behavior
- `test_undo_empty` — Undo with nothing to undo
- `test_checkpoint_modified` — Modified flag behavior
- `test_session_info` — Info dict structure
- `test_project_info` — Project info dict structure

#### project module (~5 tests)
- `test_new_project` — New project creation
- `test_list_tracks_empty` — Empty project has no tracks
- `test_project_info_fields` — All expected fields present
- Edge cases: no project open

#### track module (~10 tests)
- `test_add_midi_track` — Add MIDI track
- `test_add_audio_track` — Add audio track
- `test_add_return_track` — Add return track
- `test_remove_track` — Remove by index
- `test_rename_track` — Rename track
- `test_set_volume` — Set volume
- `test_set_pan` — Set pan
- `test_set_mute` — Mute/unmute
- `test_set_solo` — Solo/unsolo
- Edge cases: invalid index, invalid type, volume out of range

#### clip module (~10 tests)
- `test_create_midi_clip` — Create clip in slot
- `test_set_notes` — Set notes in clip
- `test_get_notes` — Retrieve notes
- `test_quantize` — Quantize notes to grid
- `test_duplicate_clip` — Duplicate between slots
- `test_list_clips` — List all clips
- Edge cases: wrong track type, invalid note data, empty clip

#### device module (~6 tests)
- `test_add_device` — Add built-in device
- `test_remove_device` — Remove device
- `test_list_devices` — List devices
- `test_set_parameter` — Set device parameter
- `test_toggle_device` — Toggle on/off
- `test_available_devices` — List available devices

#### scene module (~5 tests)
- `test_list_scenes` — List scenes in new project
- `test_create_scene` — Create a scene
- `test_delete_scene` — Delete a scene
- `test_rename_scene` — Rename a scene
- Edge cases: delete last scene

#### transport module (~5 tests)
- `test_get_transport` — Get transport info
- `test_set_tempo` — Set tempo
- `test_set_time_signature` — Set time sig
- `test_set_loop` — Configure loop
- Edge cases: invalid tempo, invalid time sig

#### export module (~5 tests)
- `test_export_als` — Export .als file
- `test_export_xml` — Export uncompressed XML
- `test_export_midi` — Export MIDI file
- `test_midi_file_format` — Verify MIDI file magic bytes and structure
- Edge cases: no notes, overwrite protection

### E2E Test Plan (test_full_e2e.py)

#### Real file tests (~10 tests)
- Create complete project, save as .als, verify gzip XML structure
- Create project with tracks, clips, notes, devices — full workflow
- Export MIDI file, verify MThd header and note data
- Round-trip: create -> save -> open -> verify all data preserved
- Multiple track types in one project

#### Subprocess CLI tests (~10 tests)
- `test_help` — --help exits 0
- `test_project_new_json` — Create project with --json
- `test_full_workflow_json` — Complete workflow via subprocess
- `test_track_operations` — Add/list/remove tracks via CLI
- `test_clip_operations` — Create clip, set notes via CLI
- `test_device_operations` — Add/list devices via CLI
- `test_scene_operations` — Create/list/delete scenes via CLI
- `test_transport_operations` — Set tempo, time sig via CLI
- `test_export_als_subprocess` — Export .als via CLI
- `test_export_midi_subprocess` — Export MIDI via CLI

### Realistic Workflow Scenarios

#### Workflow 1: Beat Production
**Simulates**: Producer creating a beat from scratch
**Operations chained**: new project -> add 4 MIDI tracks (drums, bass, keys, lead) -> create clips -> set drum pattern notes -> set bass notes -> add EQ and compressor to each track -> set tempo to 140 BPM -> save
**Verified**: Track count, clip count, note count, device count, tempo

#### Workflow 2: Arrangement Edit
**Simulates**: Editing an existing project's arrangement
**Operations chained**: open project -> rename tracks -> add/delete scenes -> duplicate clips -> adjust volumes and panning -> quantize MIDI -> undo last change -> save as new file
**Verified**: Scene count, track names, volume values, quantized note positions

#### Workflow 3: MIDI Export Pipeline
**Simulates**: Exporting MIDI data for use in another DAW
**Operations chained**: new project -> add MIDI track -> create clip -> set chord progression notes -> export MIDI file
**Verified**: MIDI file magic bytes, note count in file, file size > 0

---

## Part 2: Test Results

### Run Date: 2026-03-12

**Environment:**
- Python 3.13.5
- pytest 9.0.2
- Platform: win32 (MSYS_NT-10.0-26200)
- CLI entry point: `C:\ProgramData\miniconda3\Scripts\cli-anything-ableton.EXE`

### Summary

| Metric | Value |
|--------|-------|
| Total tests | 106 |
| Passed | 106 |
| Failed | 0 |
| Errors | 0 |
| Skipped | 0 |
| Warnings | 0 |
| Pass rate | 100% |
| Unit test time | 0.31s |
| E2E test time | 15.88s |
| Total time | ~16.2s |

### Detailed Results

#### test_core.py -- 89 unit tests PASSED (0.31s)

| Class | Tests | Status |
|-------|-------|--------|
| TestAlsXml | 17 | ALL PASSED |
| TestSession | 9 | ALL PASSED |
| TestProject | 5 | ALL PASSED |
| TestTrack | 17 | ALL PASSED |
| TestClip | 10 | ALL PASSED |
| TestDevice | 7 | ALL PASSED |
| TestScene | 6 | ALL PASSED |
| TestTransport | 7 | ALL PASSED |
| TestExport | 7 | ALL PASSED |
| TestWorkflows | 3 | ALL PASSED |

#### test_full_e2e.py -- 17 E2E tests PASSED (15.88s)

| Class | Tests | Status |
|-------|-------|--------|
| TestAlsFileE2E | 5 | ALL PASSED |
| TestCLISubprocess | 12 | ALL PASSED |

### Coverage Notes

- **Core modules**: Full coverage of all public API functions in session, project, track, clip, device, scene, transport, and export modules.
- **XML I/O**: Covers creation, read, write, roundtrip, error cases (file not found, invalid XML, wrong root element).
- **Edge cases**: Invalid indices, out-of-range values, missing fields, wrong track types, overwrite protection, empty clips, undo with empty stack.
- **CLI subprocess**: All command groups tested end-to-end via the installed `cli-anything-ableton` entry point. Both human-readable and `--json` output verified.
- **Workflow scenarios**: Three realistic multi-step workflows (beat production, arrangement editing with undo/redo, MIDI export pipeline).
- **Not covered**: OSC bridge (requires running Ableton), REPL interactive mode (requires TTY), audio clip operations (no sample file fixtures).

### Full pytest -v --tb=no output

#### test_core.py

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.0.2, pluggy-1.5.0
rootdir: C:\Users\Owner\CLI-Anything\ableton\agent-harness

cli_anything/ableton/tests/test_core.py::TestAlsXml::test_new_ableton_root PASSED [  1%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_new_root_has_transport PASSED [  2%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_new_root_has_tracks_container PASSED [  3%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_new_root_has_scenes PASSED [  4%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_new_root_has_master_track PASSED [  5%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_serialize_deserialize_roundtrip PASSED [  6%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_get_value_direct PASSED [  7%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_get_value_automatable PASSED [  8%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_get_value_missing_returns_default PASSED [ 10%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_set_value PASSED [ 11%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_next_id PASSED [ 12%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_to_xml_string PASSED [ 13%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_write_read_als_roundtrip PASSED [ 14%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_write_uncompressed PASSED [ 15%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_read_als_file_not_found PASSED [ 16%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_read_als_invalid_xml PASSED [ 17%]
cli_anything/ableton/tests/test_core.py::TestAlsXml::test_read_als_wrong_root PASSED [ 19%]
cli_anything/ableton/tests/test_core.py::TestSession::test_new_session PASSED [ 20%]
cli_anything/ableton/tests/test_core.py::TestSession::test_new_project PASSED [ 21%]
cli_anything/ableton/tests/test_core.py::TestSession::test_open_save_roundtrip PASSED [ 22%]
cli_anything/ableton/tests/test_core.py::TestSession::test_undo_redo PASSED [ 23%]
cli_anything/ableton/tests/test_core.py::TestSession::test_undo_empty PASSED [ 24%]
cli_anything/ableton/tests/test_core.py::TestSession::test_redo_empty PASSED [ 25%]
cli_anything/ableton/tests/test_core.py::TestSession::test_checkpoint_sets_modified PASSED [ 26%]
cli_anything/ableton/tests/test_core.py::TestSession::test_session_info PASSED [ 28%]
cli_anything/ableton/tests/test_core.py::TestSession::test_project_info PASSED [ 29%]
cli_anything/ableton/tests/test_core.py::TestProject::test_new_project PASSED [ 30%]
cli_anything/ableton/tests/test_core.py::TestProject::test_list_tracks_empty PASSED [ 31%]
cli_anything/ableton/tests/test_core.py::TestProject::test_list_tracks_with_tracks PASSED [ 32%]
cli_anything/ableton/tests/test_core.py::TestProject::test_project_info_fields PASSED [ 33%]
cli_anything/ableton/tests/test_core.py::TestProject::test_project_not_open_error PASSED [ 34%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_add_midi_track PASSED [ 35%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_add_audio_track PASSED [ 37%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_add_return_track PASSED [ 38%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_add_group_track PASSED [ 39%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_add_track_auto_name PASSED [ 40%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_add_invalid_type PASSED [ 41%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_remove_track PASSED [ 42%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_remove_track_invalid_index PASSED [ 43%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_rename_track PASSED [ 44%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_set_volume PASSED [ 46%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_set_volume_out_of_range PASSED [ 47%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_set_pan PASSED  [ 48%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_set_pan_out_of_range PASSED [ 49%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_set_mute PASSED [ 50%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_set_solo PASSED [ 51%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_set_arm PASSED  [ 52%]
cli_anything/ableton/tests/test_core.py::TestTrack::test_no_project_open PASSED [ 53%]
cli_anything/ableton/tests/test_core.py::TestClip::test_create_midi_clip PASSED [ 55%]
cli_anything/ableton/tests/test_core.py::TestClip::test_create_clip_on_wrong_track_type PASSED [ 56%]
cli_anything/ableton/tests/test_core.py::TestClip::test_set_notes PASSED [ 57%]
cli_anything/ableton/tests/test_core.py::TestClip::test_get_notes PASSED [ 58%]
cli_anything/ableton/tests/test_core.py::TestClip::test_get_notes_empty_clip PASSED [ 59%]
cli_anything/ableton/tests/test_core.py::TestClip::test_quantize PASSED  [ 60%]
cli_anything/ableton/tests/test_core.py::TestClip::test_quantize_with_strength PASSED [ 61%]
cli_anything/ableton/tests/test_core.py::TestClip::test_duplicate_clip PASSED [ 62%]
cli_anything/ableton/tests/test_core.py::TestClip::test_invalid_note_pitch PASSED [ 64%]
cli_anything/ableton/tests/test_core.py::TestClip::test_invalid_note_missing_field PASSED [ 65%]
cli_anything/ableton/tests/test_core.py::TestClip::test_list_clips_empty PASSED [ 66%]
cli_anything/ableton/tests/test_core.py::TestDevice::test_add_device PASSED [ 67%]
cli_anything/ableton/tests/test_core.py::TestDevice::test_list_devices PASSED [ 68%]
cli_anything/ableton/tests/test_core.py::TestDevice::test_remove_device PASSED [ 69%]
cli_anything/ableton/tests/test_core.py::TestDevice::test_set_parameter PASSED [ 70%]
cli_anything/ableton/tests/test_core.py::TestDevice::test_toggle_device PASSED [ 71%]
cli_anything/ableton/tests/test_core.py::TestDevice::test_available_devices PASSED [ 73%]
cli_anything/ableton/tests/test_core.py::TestDevice::test_add_invalid_device PASSED [ 74%]
cli_anything/ableton/tests/test_core.py::TestScene::test_list_scenes_default PASSED [ 75%]
cli_anything/ableton/tests/test_core.py::TestScene::test_create_scene PASSED [ 76%]
cli_anything/ableton/tests/test_core.py::TestScene::test_delete_scene PASSED [ 77%]
cli_anything/ableton/tests/test_core.py::TestScene::test_delete_last_scene_error PASSED [ 78%]
cli_anything/ableton/tests/test_core.py::TestScene::test_rename_scene PASSED [ 79%]
cli_anything/ableton/tests/test_core.py::TestScene::test_set_scene_tempo PASSED [ 80%]
cli_anything/ableton/tests/test_core.py::TestTransport::test_get_transport PASSED [ 82%]
cli_anything/ableton/tests/test_core.py::TestTransport::test_set_tempo PASSED [ 83%]
cli_anything/ableton/tests/test_core.py::TestTransport::test_set_tempo_invalid PASSED [ 84%]
cli_anything/ableton/tests/test_core.py::TestTransport::test_set_time_signature PASSED [ 85%]
cli_anything/ableton/tests/test_core.py::TestTransport::test_set_time_signature_invalid_numerator PASSED [ 86%]
cli_anything/ableton/tests/test_core.py::TestTransport::test_set_time_signature_invalid_denominator PASSED [ 87%]
cli_anything/ableton/tests/test_core.py::TestTransport::test_set_loop PASSED [ 88%]
cli_anything/ableton/tests/test_core.py::TestExport::test_export_als PASSED [ 89%]
cli_anything/ableton/tests/test_core.py::TestExport::test_export_xml PASSED [ 91%]
cli_anything/ableton/tests/test_core.py::TestExport::test_export_als_overwrite_protection PASSED [ 92%]
cli_anything/ableton/tests/test_core.py::TestExport::test_export_als_overwrite_flag PASSED [ 93%]
cli_anything/ableton/tests/test_core.py::TestExport::test_export_midi PASSED [ 94%]
cli_anything/ableton/tests/test_core.py::TestExport::test_export_midi_empty_clip PASSED [ 95%]
cli_anything/ableton/tests/test_core.py::TestExport::test_midi_var_length_encoding PASSED [ 96%]
cli_anything/ableton/tests/test_core.py::TestWorkflows::test_beat_production_workflow PASSED [ 97%]
cli_anything/ableton/tests/test_core.py::TestWorkflows::test_undo_redo_workflow PASSED [ 98%]
cli_anything/ableton/tests/test_core.py::TestWorkflows::test_midi_export_pipeline PASSED [100%]

============================= 89 passed in 0.31s ==============================
```

#### test_full_e2e.py

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.0.2, pluggy-1.5.0
rootdir: C:\Users\Owner\CLI-Anything\ableton\agent-harness

cli_anything/ableton/tests/test_full_e2e.py::TestAlsFileE2E::test_create_and_verify_als PASSED [  5%]
cli_anything/ableton/tests/test_full_e2e.py::TestAlsFileE2E::test_full_project_roundtrip PASSED [ 11%]
cli_anything/ableton/tests/test_full_e2e.py::TestAlsFileE2E::test_midi_export_format PASSED [ 17%]
cli_anything/ableton/tests/test_full_e2e.py::TestAlsFileE2E::test_multiple_track_types PASSED [ 23%]
cli_anything/ableton/tests/test_full_e2e.py::TestAlsFileE2E::test_export_uncompressed_xml PASSED [ 29%]
cli_anything/ableton/tests/test_full_e2e.py::TestCLISubprocess::test_help PASSED [ 35%]
cli_anything/ableton/tests/test_full_e2e.py::TestCLISubprocess::test_project_new_json PASSED [ 41%]
cli_anything/ableton/tests/test_full_e2e.py::TestCLISubprocess::test_project_info_json PASSED [ 47%]
cli_anything/ableton/tests/test_full_e2e.py::TestCLISubprocess::test_track_operations PASSED [ 52%]
cli_anything/ableton/tests/test_full_e2e.py::TestCLISubprocess::test_clip_operations PASSED [ 58%]
cli_anything/ableton/tests/test_full_e2e.py::TestCLISubprocess::test_device_operations PASSED [ 64%]
cli_anything/ableton/tests/test_full_e2e.py::TestCLISubprocess::test_scene_operations PASSED [ 70%]
cli_anything/ableton/tests/test_full_e2e.py::TestCLISubprocess::test_transport_operations PASSED [ 76%]
cli_anything/ableton/tests/test_full_e2e.py::TestCLISubprocess::test_export_als_subprocess PASSED [ 82%]
cli_anything/ableton/tests/test_full_e2e.py::TestCLISubprocess::test_export_midi_subprocess PASSED [ 88%]
cli_anything/ableton/tests/test_full_e2e.py::TestCLISubprocess::test_full_workflow_json PASSED [ 94%]
cli_anything/ableton/tests/test_full_e2e.py::TestCLISubprocess::test_install_check PASSED [100%]

============================= 17 passed in 15.88s =============================
```
