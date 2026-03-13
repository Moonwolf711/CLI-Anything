# cli-anything-ableton

A stateful CLI harness for **Ableton Live** -- edit `.als` project files from the
command line and control running Ableton instances via OSC.

## Prerequisites

- **Python 3.10+**
- **Ableton Live 11 or 12** (Suite, Standard, or Intro)
  - Windows: `C:\ProgramData\Ableton\Live 12 Suite\`
  - macOS: `/Applications/Ableton Live 12 Suite.app`
- **OSC bridge** (optional, for live control)

## Installation

```bash
cd CLI-Anything/ableton/agent-harness
pip install -e .
```

Verify:

```bash
cli-anything-ableton --help
```

## Quick Start

```bash
# Interactive REPL
cli-anything-ableton

# Create a new project
cli-anything-ableton project new -o my_song.als

# Open and inspect
cli-anything-ableton --project my_song.als project info
cli-anything-ableton --project my_song.als track list

# Add tracks, clips, notes
cli-anything-ableton --project my_song.als -s track add midi "Bass"
cli-anything-ableton --project my_song.als -s clip add-midi 0 0 -n "Bass Line" -l 8
cli-anything-ableton --project my_song.als -s note add 0 0 -p 36 -t 0.0 -d 0.5 -v 100

# JSON output (for agents)
cli-anything-ableton --json --project my_song.als project info
```

## Command Groups

| Group | Commands |
|-------|----------|
| `project` | new, open, save, save-as, info, list-recent |
| `track` | list, add, remove, rename, info, volume, pan, mute, solo, arm |
| `clip` | list, add-midi, add-audio, remove, info, rename, move, duplicate |
| `note` | list, add, remove, quantize |
| `device` | list, add, remove, info, set-param, toggle, list-available |
| `transport` | get, set-tempo, set-time-sig, loop |
| `export` | als, xml-dump, midi |
| `session` | status, undo, redo, history, save, load |
| `osc` | connect, status, send, play, stop, record |
| `install-check` | Find Ableton installation |
| `repl` | Enter interactive mode |

## Track Commands

```bash
cli-anything-ableton track list
cli-anything-ableton track add midi "Synth Lead"
cli-anything-ableton track add audio "Vocals"
cli-anything-ableton track add return "Reverb Bus"
cli-anything-ableton track remove 2
cli-anything-ableton track rename 0 "Bass"
cli-anything-ableton track info 0
cli-anything-ableton track volume 0 0.85
cli-anything-ableton track pan 0 -0.5
cli-anything-ableton track mute 0
cli-anything-ableton track solo 1
```

## Clip Commands

```bash
cli-anything-ableton clip list
cli-anything-ableton clip list -t 0
cli-anything-ableton clip add-midi 0 0 -n "Intro" -l 4
cli-anything-ableton clip add-audio 1 0
cli-anything-ableton clip remove 0 0
cli-anything-ableton clip info 0 0
cli-anything-ableton clip rename 0 0 "Chorus"
cli-anything-ableton clip duplicate 0 0 1
cli-anything-ableton clip move 0 0 2
```

## Note Commands

```bash
cli-anything-ableton note list 0 0
cli-anything-ableton note add 0 0 -p 60 -t 0.0 -d 0.5 -v 100
cli-anything-ableton note add 0 0 -p 64 -t 1.0 -d 0.5 -v 80
cli-anything-ableton note remove 0 0 -p 60
cli-anything-ableton note quantize 0 0 -g 0.25 --strength 0.8
```

## Transport Commands

```bash
cli-anything-ableton transport get
cli-anything-ableton transport set-tempo 140
cli-anything-ableton transport set-time-sig 3 4
cli-anything-ableton transport loop --on --start 0 --length 16
```

## Export Commands

```bash
cli-anything-ableton export als output.als
cli-anything-ableton export xml-dump debug.xml
cli-anything-ableton export xml-dump          # stdout
cli-anything-ableton export midi clip.mid 0 0 --overwrite
```

## Session (Undo/Redo)

Every mutation creates an automatic undo checkpoint (up to 50 levels).

```bash
cli-anything-ableton session status
cli-anything-ableton session undo
cli-anything-ableton session redo
cli-anything-ableton session history
cli-anything-ableton session save
cli-anything-ableton session load <session_id>
```

## OSC Live Control

```bash
cli-anything-ableton osc connect -p 9876
cli-anything-ableton osc play
cli-anything-ableton osc stop
cli-anything-ableton osc send /live/song/set/tempo 140
```

## Architecture

The CLI operates in two modes:

1. **Offline mode** (primary) -- Direct `.als` XML manipulation. The `.als` format
   is gzip-compressed XML. The CLI parses, modifies, and re-compresses without
   needing Ableton running.

2. **Live mode** (OSC) -- Sends OSC messages to a running Ableton instance for
   transport control, scene launching, etc.

**Note:** Ableton does not support headless audio rendering. To render audio,
open the `.als` in Ableton's GUI and use File > Export Audio/Video.

## Running Tests

```bash
pip install -e ".[dev]"
python -m pytest cli_anything/ableton/tests/ -v --tb=short
```

## File Layout

```
cli_anything/ableton/
  ableton_cli.py          # Click CLI + REPL
  __main__.py             # python -m support
  core/
    session.py            # Stateful session (undo/redo)
    project.py            # Project operations
    track.py              # Track CRUD + mixer
    clip.py               # Clip CRUD + notes
    device.py             # Device CRUD + params
    scene.py              # Scene management
    transport.py          # Tempo, time-sig, loop, OSC
    export.py             # ALS/XML/MIDI export
  utils/
    als_xml.py            # .als gzip XML I/O
    ableton_backend.py    # Installation finder + OSC
    repl_skin.py          # Branded REPL UI
  tests/
    test_core.py          # Unit tests
    test_full_e2e.py      # End-to-end tests
```
