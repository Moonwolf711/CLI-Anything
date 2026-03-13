# cli-anything-vital

CLI harness for the **Vital** wavetable synthesizer. Provides full command-line
access to create, edit, inspect, and manage Vital preset files (`.vital` JSON).

## Installation

```bash
cd agent-harness
pip install -e .
```

## Usage

### Interactive REPL (default)
```bash
cli-anything-vital
```

### One-shot commands
```bash
cli-anything-vital preset new --name "My Bass" --author "Me" --style "Bass"
cli-anything-vital preset open path/to/preset.vital
cli-anything-vital param get volume
cli-anything-vital param set volume 0.8
cli-anything-vital osc info 1
cli-anything-vital fx enable reverb
cli-anything-vital mod add lfo_1 filter_1_cutoff --amount 0.7
cli-anything-vital export output.vital
```

### JSON output
```bash
cli-anything-vital --json preset info
cli-anything-vital --json param get volume
```

## Command Groups

| Group     | Commands                                          |
|-----------|---------------------------------------------------|
| `preset`  | new, open, save, save-as, info, list, search, duplicate, validate, dirs, diff |
| `param`   | get, set, dump, reset, list-names                 |
| `osc`     | info, set                                         |
| `filter`  | info, set                                         |
| `env`     | info, set                                         |
| `lfo`     | info, set                                         |
| `fx`      | info, set, enable, disable, toggle                |
| `mod`     | list, add, remove, sources                        |
| `session` | status, undo, redo, history, save, load           |
| `export`  | Export to vital/json/summary format               |
| `install-check` | Detect Vital installation                  |

## Architecture

```
cli_anything/vital/
    __init__.py          # Package version
    __main__.py          # python -m entry
    vital_cli.py         # Click CLI + REPL
    core/
        parameters.py    # 900+ param definitions
        preset.py        # Create/load/save/diff presets
        modulation.py    # Modulation routing
        effects.py       # Effects chain
        wavetable.py     # Wavetable management
        export.py        # Export formats
        session.py       # Undo/redo session
    utils/
        vital_backend.py # Find Vital installation
        repl_skin.py     # Terminal UI branding
    tests/
        test_core.py     # Unit tests
        test_full_e2e.py # End-to-end tests
```

## Running Tests

```bash
pip install pytest
pytest cli_anything/vital/tests/ -v --tb=short
```
