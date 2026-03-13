# Vital Wavetable Synthesizer - CLI Harness Analysis

## Phase 1: Codebase Analysis

### Architecture
Vital is an open-source wavetable synthesizer written in C++ with JUCE.
- **Source**: https://github.com/mtytel/vital
- **Engine**: Custom DSP with 3 wavetable oscillators, 2 filters, 6 envelopes, 8 LFOs, 4 random LFOs, 64 modulation slots, 9 effects
- **Data model**: JSON preset files (.vital extension)
- **Plugin formats**: VST3, CLAP, standalone

### Data Model
Vital presets are plain JSON files with this structure:
```json
{
  "preset_name": "My Sound",
  "author": "User",
  "comments": "",
  "preset_style": "Bass",
  "settings": {
    "volume": 0.7,
    "osc_1_on": 1.0,
    "osc_1_level": 0.7,
    ...hundreds more parameters...
  },
  "modulations": [
    {"source": "lfo_1", "destination": "osc_1_level"}
  ],
  "wavetables": [...]
}
```

### Key Dimensions
- **Parameters**: ~600+ named parameters across all components
- **Oscillators**: 3, each with 29 parameters (wavetable frame, unison, detune, spectral morph, etc.)
- **Filters**: 2 main + 1 FX, 8 models (analog, dirty, ladder, digital, diode, formant, comb, phase)
- **Envelopes**: 6, each with 9 parameters (ADSR + power curves)
- **LFOs**: 8 standard + 4 random, each with ~12 parameters
- **Effects**: 9 (chorus, compressor, delay, distortion, EQ, filter FX, flanger, phaser, reverb)
- **Modulation**: 64 slots, each with source/destination/amount/power/bipolar/stereo/bypass

### File Locations (Windows)
- VST3: `C:\Program Files\Common Files\VST3\Vital.vst3`
- CLAP: `C:\Program Files\Common Files\CLAP\Vital.clap`
- Config: `%APPDATA%\vital\Vital.config`
- Library: `%APPDATA%\vital\Vital.library`
- User presets: Configured in Vital.config `data_directory`

### Backend Integration
Unlike DAWs, Vital has no headless CLI mode. The CLI operates on the JSON preset
format directly. The "real software" validation comes from Vital loading the
generated presets. The backend module validates installations and reads config.

## Phase 2: CLI Design

### Command Groups
1. **preset** - Create, load, save, list, search, compare, validate
2. **param** - Get/set parameters, search, list by group
3. **effect** - Enable/disable/toggle effects, get/set effect params
4. **mod** - List/add/remove/update modulation routings
5. **wt** - Wavetable frame control, list wavetables, create basics
6. **export** - Export to .vital, .json, text summary
7. **Session** - Undo/redo, history, status (built into REPL)

### State Model
- Session object holds current preset + undo/redo stacks
- Modified flag tracks unsaved changes
- Session can persist to JSON file

### Output Format
- All commands support `--json` flag for machine-readable output
- Human mode uses the unified REPL skin (tables, colors, status blocks)
- REPL is default when invoked without subcommand
