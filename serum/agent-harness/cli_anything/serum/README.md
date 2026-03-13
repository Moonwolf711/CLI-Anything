# cli-anything-serum

CLI harness for **Xfer Records Serum** synthesizer -- manage presets, parse
FXP binaries, modify parameters, and organize your preset library from the
command line or an interactive REPL.

## Requirements

- **Python** 3.10+
- **Xfer Records Serum** (1 or 2) installed with preset files accessible
  - Serum 1 presets: `.fxp` format
  - Serum 2 presets: `.SerumPreset` format (requires `cbor2` + `zstandard`)

Serum is a proprietary wavetable synthesizer. Purchase from
[xferrecords.com](https://xferrecords.com/products/serum).

> **Note:** This CLI operates on preset *files*, not the plugin directly.
> Most commands work even without the VST installed, as long as preset files
> are accessible.

## Installation

```bash
cd serum/agent-harness
pip install -e .

# For Serum 2 .SerumPreset support:
pip install -e ".[serum2]"

# Verify
cli-anything-serum --version
cli-anything-serum --help
```

## Quick Start

```bash
# Enter interactive REPL (default)
cli-anything-serum

# List all presets
cli-anything-serum preset list

# Search presets
cli-anything-serum preset search "bass"

# Inspect a preset
cli-anything-serum preset info "path/to/preset.fxp"

# Dump all 512 parameters
cli-anything-serum param dump "path/to/preset.fxp"

# JSON output (for scripting/agents)
cli-anything-serum --json preset list
cli-anything-serum --json param dump "path/to/preset.fxp" --named-only
```

## Command Groups

### `preset` -- Preset File Operations
| Command | Description |
|---------|-------------|
| `preset list` | List presets in known directories |
| `preset search <query>` | Search by name (case-insensitive) |
| `preset info <path>` | Show detailed preset info |
| `preset open <path>` | Load .fxp into session for editing |
| `preset create <path>` | Create new init preset |
| `preset save` | Save current session to disk |
| `preset duplicate <src>` | Duplicate a preset file |
| `preset validate <path>` | Validate .fxp structure |
| `preset dirs` | Show known preset directories |

### `param` -- Parameter Operations
| Command | Description |
|---------|-------------|
| `param get <path> <name>` | Read a single parameter |
| `param set <name> <value>` | Set parameter in session |
| `param dump <path>` | Dump all 512 parameters |
| `param diff <a> <b>` | Compare two presets |
| `param names` | List all known param names |

### `wavetable` -- Wavetable Operations
| Command | Description |
|---------|-------------|
| `wavetable list` | List wavetable .wav files |
| `wavetable info <path>` | Show WAV header info |

### `library` -- Library Management
| Command | Description |
|---------|-------------|
| `library scan` | Scan all Serum directories |
| `library duplicates` | Find duplicate presets |
| `library organize <src> <dst>` | Organize by category |
| `library batch-rename <dir>` | Batch rename presets |

### `session` -- Session Management
| Command | Description |
|---------|-------------|
| `session status` | Show session state |
| `session undo` | Undo last change |
| `session redo` | Redo last undone change |
| `session history` | Show undo history |
| `session save` | Save session workspace |
| `session load <path>` | Load saved session |

## FXP Binary Format

Serum 1 `.fxp` files use the VST FXP container format:

```
CcnK       4B  magic
size       4B  big-endian uint32
FPCh       4B  chunk type
version    4B  big-endian uint32 (1)
fxID       4B  "XfsX" (Xfer Serum)
fxVersion  4B  big-endian uint32 (1)
numProgs   4B  big-endian uint32 (1)
prgName   28B  null-padded ASCII
chunkSize  4B  big-endian uint32
chunk     var  zlib-compressed float32[512]
```

Each preset contains 512 little-endian float32 parameters covering
oscillators, filters, envelopes, LFOs, effects, and global settings.

## Running Tests

```bash
cd serum/agent-harness
pip install -e ".[dev]"
pytest cli_anything/serum/tests/ -v -s
```
