# SERUM -- CLI-Anything Software-Specific SOP

## Software Overview

**Xfer Records Serum** is a proprietary wavetable synthesizer VST plugin.
It is closed-source with no official CLI, scripting API, or headless mode.

Key constraints:
- No source code available
- No command-line interface
- No scripting/batch API
- Binary preset formats (.fxp for v1, .SerumPreset for v2)

## What CAN Be Controlled

Despite being closed-source, the preset file formats are well-understood:

### Serum 1 (.fxp)
- Standard VST FXP container (CcnK + FPCh header)
- 60-byte header, then zlib-compressed payload
- Payload = 512 little-endian float32 parameters
- Plugin ID: "XfsX"
- Parameters are positional (index 0-511), ~80 have known mappings

### Serum 2 (.SerumPreset)
- Custom Xfer format: XferJson magic + JSON header + Zstandard-compressed CBOR
- Header contains: preset name, author, hash (MD5 of zstd bytes)
- Payload is a deeply nested CBOR dict with named parameters
- Format documented in serum_preset_io.py

### Wavetables
- Standard WAV files in Tables/ subdirectory
- Each wavetable frame = 2048 samples
- Multi-frame wavetables are concatenated frames

## Architecture

```
cli_anything/serum/
  serum_cli.py          # Click CLI with REPL (main entry)
  core/
    fxp.py              # Serum 1 .fxp binary reader/writer
    preset.py           # Preset scanning, search, organize
    session.py          # Session state with undo/redo
  utils/
    serum_backend.py    # VST installation detection
    repl_skin.py        # Unified REPL interface
```

## Data Model

The CLI operates on two levels:

1. **File-level** -- scan, search, organize, validate, duplicate preset files
2. **Parameter-level** -- parse FXP binary, read/write individual float32 params

Session state tracks:
- Currently loaded preset (parsed FXP data)
- Undo/redo stack (deep-copy snapshots)
- Modified flag
- Source file path

## Known Parameter Map (Serum 1)

| Index | Name | Range | Default |
|-------|------|-------|---------|
| 0 | osc_a_enable | 0-1 | 1.0 |
| 1 | osc_a_volume | 0-1 | 0.5 |
| 6 | osc_a_wave_pos | 0-1 | 0.0 |
| 10 | osc_b_enable | 0-1 | 0.0 |
| 20 | filter_enable | 0-1 | 0.0 |
| 21 | filter_cutoff | 0-1 | 1.0 |
| 30-33 | env1 ADSR | 0-1 | varies |
| 40 | master_volume | 0-1 | 0.8 |
| 50-53 | lfo1 | 0-1 | varies |
| 100+ | effects | 0-1 | 0.0 |

See `fxp.py:PARAM_MAP` for the complete known mapping.

## Preset Directory Layout

```
Documents/Xfer/Serum Presets/
  Presets/
    User/              # User presets (.fxp)
    Splice/            # Third-party presets
  Tables/
    User/              # User wavetables (.wav)
    AI Generated/      # Generated wavetables

D:/OneDrive/Documents/Xfer/Serum Presets/
  Presets/User/        # OneDrive-synced presets (3000+ .fxp)
```

## Limitations

- Cannot load presets into the Serum GUI programmatically
- Cannot trigger audio rendering/preview
- Cannot access plugin state while Serum is running in a DAW
- Serum 2 .SerumPreset write support requires cbor2 + zstandard
- Parameter names beyond the ~80 mapped indices are unknown
- Wavetable .wav files can be read but not generated (no synthesis)
