# Ableton Live CLI Harness - Software-Specific SOP

## Phase 1: Codebase Analysis

### Backend Engine
Ableton Live 12 Suite is a professional DAW (Digital Audio Workstation). Unlike
open-source software, it has no public source code. However, it exposes several
control surfaces:

1. **MIDI Remote Scripts** - Python 2/3 scripts running inside Live via the
   `_Framework/` API (ControlSurface, Song, Track, Device, etc.)
2. **.als Project Files** - Gzip-compressed XML documents containing the full
   project state (tracks, clips, devices, automation, routing)
3. **OSC Bridge** - External control via Open Sound Control protocol
4. **Max for Live** - M4L devices that expose Live's API to Max patches

### Data Model
- `.als` files: gzip-compressed XML with Ableton's schema
- Root element: `<Ableton>` with `MajorVersion`, `MinorVersion`, `Creator`
- Key child: `<LiveSet>` containing all project data
- Under LiveSet: `<Tracks>`, `<Scenes>`, `<Transport>`, `<MasterTrack>`,
  `<PreHearTrack>`, `<SendsPre>`, `<ViewStates>`, etc.

### Track Types
- `<MidiTrack>` - MIDI instrument tracks
- `<AudioTrack>` - Audio recording/playback tracks
- `<ReturnTrack>` - Send/Return effect buses
- `<GroupTrack>` - Track groups (folders)

### Clip Structure
- `<MainSequencer>` → `<ClipSlotList>` → `<ClipSlot>` → `<ClipSlot>` (value)
- MIDI clips contain `<Notes>` → `<KeyTracks>` → `<MidiKey>` + `<MidiNoteEvent>`
- Audio clips contain `<AudioClip>` with sample references

### Device Chain
- `<DeviceChain>` → `<MainSequencer>` + `<Mixer>` + `<DeviceChain>`
- Devices live under `<Devices>` and can be native or VST/AU plugins
- Parameters are `<AutomatableRangedValue>` elements

### Existing CLI Tools
- No official CLI for Ableton Live
- `python-osc` library for OSC communication
- The user has an existing OSC bridge at 127.0.0.1:9876/9877

### Installation Path
- Windows: `C:\ProgramData\Ableton\Live 12 Suite\`
- MIDI Remote Scripts: `C:\ProgramData\Ableton\Live 12 Suite\Resources\MIDI Remote Scripts\`
- User Library: `%APPDATA%\Ableton\Live 12\`

## Phase 2: Architecture

### Command Groups

1. **project** - Open, info, create, save .als files
2. **track** - Add, remove, rename, volume, pan, mute, solo, arm
3. **clip** - List, create MIDI clips, set notes, quantize, duplicate
4. **device** - List, add, remove, set parameters
5. **scene** - List, create, delete, rename, fire
6. **transport** - Play, stop, record, tempo, time signature, loop
7. **export** - Render audio, export MIDI
8. **osc** - Connect, send, status (live control bridge)
9. **session** - Undo, redo, history, status

### State Model
- Session stores: open project path, parsed XML tree, undo/redo stacks
- Sessions persist as JSON to `~/.cli-anything-ableton/sessions/`
- Project state = in-memory lxml Element tree of the .als XML

### Interaction Models
- **One-shot CLI**: `cli-anything-ableton project info my_song.als`
- **REPL**: `cli-anything-ableton` (no args) enters interactive mode
- **JSON output**: `--json` flag for all commands
- **OSC live mode**: `cli-anything-ableton osc connect` for real-time control

## Backend Integration

The "real software" here is Ableton Live itself. Since Ableton has no headless
CLI mode, the backend integration works differently than other CLI-Anything tools:

1. **Offline mode (primary)**: Direct .als XML manipulation for project editing
2. **Live mode (OSC)**: Send OSC messages to a running Ableton instance
3. **Rendering**: Ableton does not support headless rendering. Export commands
   generate the project file; the user renders within Ableton's GUI.

This is documented clearly: the CLI is a structured editor for .als project
files and a remote control interface for live Ableton instances via OSC.
