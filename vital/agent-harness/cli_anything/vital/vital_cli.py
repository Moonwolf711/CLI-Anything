"""cli-anything-vital: Full CLI harness for the Vital wavetable synthesizer."""

import json
import os
import sys

import click

from cli_anything.vital import __version__
from cli_anything.vital.core.session import Session
from cli_anything.vital.core.preset import (
    create_preset, load_preset, save_preset, preset_info,
    get_param_value, set_param_value, set_params_bulk,
    list_presets, search_presets, compare_presets,
)
from cli_anything.vital.core.parameters import (
    PARAM_REGISTRY, get_param, validate_param_value,
    list_params_by_group, search_params, get_groups,
    MODULATION_SOURCES, EFFECT_NAMES, FILTER_MODEL_NAMES,
)
from cli_anything.vital.core.modulation import (
    list_modulations, add_modulation, remove_modulation,
    update_modulation, list_sources, list_destinations,
)
from cli_anything.vital.core.effects import (
    list_effects, enable_effect, disable_effect, toggle_effect,
    get_effect_params, set_effect_param, configure_effect,
)
from cli_anything.vital.core.wavetable import (
    list_wavetables, get_wavetable_frame, set_wavetable_frame,
    create_basic_wavetable, set_wavetable,
)
from cli_anything.vital.core.export import export_preset, export_settings_only
from cli_anything.vital.utils.vital_backend import (
    find_vital, get_config_dir, get_presets_dir, get_install_info,
    validate_preset_file,
)


_session = Session()


def _output(data, as_json=False):
    """Print output, optionally as JSON."""
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        if isinstance(data, dict):
            for k, v in data.items():
                click.echo(f"  {k}: {v}")
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    parts = [f"{k}={v}" for k, v in item.items()]
                    click.echo(f"  {', '.join(parts)}")
                else:
                    click.echo(f"  {item}")
        else:
            click.echo(str(data))


def _require_preset(ctx):
    """Ensure a preset is loaded in the session, or abort."""
    if not _session.has_preset:
        click.echo("Error: No preset loaded. Use 'preset open <path>' or 'preset new' first.", err=True)
        ctx.exit(1)


@click.group(invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, default=False, help="Output as JSON.")
@click.version_option(__version__, prog_name="cli-anything-vital")
@click.pass_context
def cli(ctx, as_json):
    """cli-anything-vital -- CLI harness for the Vital wavetable synthesizer."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# -- preset group -------------------------------------------------------

@cli.group()
@click.pass_context
def preset(ctx):
    """Preset management: create, open, save, list, search, diff."""


@preset.command("new")
@click.option("--name", default="Init", help="Preset name.")
@click.option("--author", default="", help="Author name.")
@click.option("--style", default="", help="Preset style/category.")
@click.option("--comments", default="", help="Preset comments.")
@click.pass_context
def preset_new(ctx, name, author, style, comments):
    """Create a new default preset."""
    p = create_preset(name=name, author=author, comments=comments, style=style)
    _session.load_preset(p)
    info = preset_info(p)
    if ctx.obj.get("json"):
        _output(info, as_json=True)
    else:
        click.echo(f"Created new preset: {name}")
        click.echo(f"  Oscillators: {info['active_oscillators']} active")
        click.echo(f"  Parameters: {info['param_count']}")


@preset.command("open")
@click.argument("path", type=click.Path(exists=True))
@click.pass_context
def preset_open(ctx, path):
    """Open a .vital preset file."""
    p = load_preset(path)
    _session.load_preset(p, path=os.path.abspath(path))
    info = preset_info(p)
    if ctx.obj.get("json"):
        _output(info, as_json=True)
    else:
        click.echo(f"Loaded: {info['preset_name']}")
        click.echo(f"  Author: {info['author']}, Style: {info['preset_style']}")
        click.echo(f"  Osc: {info['active_oscillators']}, Filters: {info['active_filters']}, Effects: {info['active_effects']}")


@preset.command("save")
@click.option("--overwrite", is_flag=True, help="Overwrite existing file.")
@click.pass_context
def preset_save(ctx, overwrite):
    """Save the current preset to its original path."""
    _require_preset(ctx)
    path = _session.preset_path
    if not path:
        click.echo("Error: No file path. Use 'preset save-as <path>'.", err=True)
        ctx.exit(1)
    result = save_preset(_session.preset, path, overwrite=True)
    _session.modified = False
    click.echo(f"Saved: {result['path']} ({result['file_size']} bytes)")


@preset.command("save-as")
@click.argument("path")
@click.option("--overwrite", is_flag=True, help="Overwrite existing file.")
@click.pass_context
def preset_save_as(ctx, path, overwrite):
    """Save the current preset to a new path."""
    _require_preset(ctx)
    result = save_preset(_session.preset, path, overwrite=overwrite)
    _session.preset_path = result["path"]
    _session.modified = False
    click.echo(f"Saved: {result['path']} ({result['file_size']} bytes)")


@preset.command("info")
@click.pass_context
def preset_info_cmd(ctx):
    """Show information about the current preset."""
    _require_preset(ctx)
    info = preset_info(_session.preset)
    if ctx.obj.get("json"):
        _output(info, as_json=True)
    else:
        click.echo(f"  Name:         {info['preset_name']}")
        click.echo(f"  Author:       {info['author']}")
        click.echo(f"  Style:        {info['preset_style']}")
        click.echo(f"  Parameters:   {info['param_count']}")
        click.echo(f"  Oscillators:  {info['active_oscillators']}")
        click.echo(f"  Filters:      {info['active_filters']}")
        click.echo(f"  Effects:      {info['active_effects']}")
        click.echo(f"  Modulations:  {info['modulation_count']}")
        click.echo(f"  Polyphony:    {info['polyphony']}")


@preset.command("list")
@click.argument("directory", required=False)
@click.option("--no-recurse", is_flag=True, help="Don't search recursively.")
@click.pass_context
def preset_list(ctx, directory, no_recurse):
    """List preset files in a directory."""
    if not directory:
        directory = get_presets_dir()
    if not directory:
        click.echo("Error: No directory and Vital presets dir not found.", err=True)
        ctx.exit(1)
    results = list_presets(directory, recursive=not no_recurse)
    if ctx.obj.get("json"):
        _output(results, as_json=True)
    else:
        click.echo(f"Found {len(results)} presets:")
        for p in results:
            click.echo(f"  {p['preset_name']:30s}  {p['author']:20s}  {p['preset_style']}")


@preset.command("search")
@click.argument("query")
@click.argument("directory", required=False)
@click.pass_context
def preset_search(ctx, query, directory):
    """Search presets by name, author, or style."""
    if not directory:
        directory = get_presets_dir()
    if not directory:
        click.echo("Error: No directory and Vital presets dir not found.", err=True)
        ctx.exit(1)
    results = search_presets(directory, query)
    if ctx.obj.get("json"):
        _output(results, as_json=True)
    else:
        for p in results:
            click.echo(f"  {p['preset_name']:30s}  {p['author']:20s}  {p['preset_style']}")


@preset.command("duplicate")
@click.argument("path", type=click.Path(exists=True))
@click.argument("new_name")
@click.pass_context
def preset_duplicate(ctx, path, new_name):
    """Duplicate a preset with a new name."""
    p = load_preset(path)
    p["preset_name"] = new_name
    out_path = os.path.join(os.path.dirname(os.path.abspath(path)), f"{new_name}.vital")
    result = save_preset(p, out_path)
    click.echo(f"Duplicated to: {result['path']}")


@preset.command("validate")
@click.argument("path", type=click.Path(exists=True))
@click.pass_context
def preset_validate(ctx, path):
    """Validate a .vital preset file."""
    valid, msg = validate_preset_file(path)
    if ctx.obj.get("json"):
        _output({"valid": valid, "message": msg}, as_json=True)
    else:
        click.echo(f"{'Valid' if valid else 'Invalid'}: {msg if not valid else path}")


@preset.command("dirs")
@click.pass_context
def preset_dirs(ctx):
    """Show Vital preset directories."""
    info = get_install_info()
    dirs = {"config_dir": info.get("config_dir", ""),
            "data_dir": info.get("data_dir", ""),
            "presets_dir": info.get("presets_dir", "")}
    if ctx.obj.get("json"):
        _output(dirs, as_json=True)
    else:
        for label, p in dirs.items():
            exists = os.path.isdir(p) if p else False
            click.echo(f"  {label:12s}  {p or '(not found)'}  {'[exists]' if exists else ''}")


@preset.command("diff")
@click.argument("path_a", type=click.Path(exists=True))
@click.argument("path_b", type=click.Path(exists=True))
@click.pass_context
def preset_diff(ctx, path_a, path_b):
    """Compare two presets and show differences."""
    a = load_preset(path_a)
    b = load_preset(path_b)
    diffs = compare_presets(a, b)
    if ctx.obj.get("json"):
        _output(diffs, as_json=True)
    else:
        click.echo(f"Total differences: {diffs['total_diffs']}")
        for k, v in list(diffs["settings_diffs"].items())[:30]:
            click.echo(f"  {k}: {v['a']} -> {v['b']}")


# -- param group ---------------------------------------------------------

@cli.group()
@click.pass_context
def param(ctx):
    """Parameter operations: get, set, dump, diff, reset, list."""


@param.command("get")
@click.argument("name")
@click.pass_context
def param_get(ctx, name):
    """Get a parameter value."""
    _require_preset(ctx)
    found, value, msg = get_param_value(_session.preset, name)
    if not found:
        click.echo(f"Error: {msg}", err=True)
        ctx.exit(1)
    pdef = get_param(name)
    if ctx.obj.get("json"):
        result = {"name": name, "value": value}
        if pdef:
            result.update({"min": pdef.min_val, "max": pdef.max_val,
                           "default": pdef.default_val, "description": pdef.description})
        _output(result, as_json=True)
    else:
        desc = f" ({pdef.description})" if pdef else ""
        click.echo(f"  {name} = {value}{desc}")
        if pdef:
            click.echo(f"    range: [{pdef.min_val}, {pdef.max_val}], default: {pdef.default_val}")


@param.command("set")
@click.argument("name")
@click.argument("value", type=float)
@click.pass_context
def param_set(ctx, name, value):
    """Set a parameter value."""
    _require_preset(ctx)
    _session.set_param(name, value, description=f"set {name} = {value}")
    ok, msg = validate_param_value(name, value)
    if not ok:
        click.echo(f"Warning: {msg}", err=True)
    click.echo(f"  {name} = {value}")


@param.command("dump")
@click.option("--group", default=None, help="Filter by parameter group.")
@click.option("--non-default", is_flag=True, help="Only show non-default values.")
@click.pass_context
def param_dump(ctx, group, non_default):
    """Dump all parameter values."""
    _require_preset(ctx)
    settings = _session.preset.get("settings", {})
    items = []
    for name, value in sorted(settings.items()):
        pdef = get_param(name)
        if group and pdef and pdef.group != group:
            continue
        if non_default and pdef and value == pdef.default_val:
            continue
        items.append({"name": name, "value": value,
                       "default": pdef.default_val if pdef else None,
                       "group": pdef.group if pdef else "unknown"})
    if ctx.obj.get("json"):
        _output(items, as_json=True)
    else:
        for item in items:
            marker = " *" if item["default"] is not None and item["value"] != item["default"] else ""
            click.echo(f"  {item['name']:40s} = {item['value']}{marker}")


@param.command("reset")
@click.argument("name")
@click.pass_context
def param_reset(ctx, name):
    """Reset a parameter to its default value."""
    _require_preset(ctx)
    pdef = get_param(name)
    if not pdef:
        click.echo(f"Error: Unknown parameter: {name}", err=True)
        ctx.exit(1)
    _session.set_param(name, pdef.default_val, description=f"reset {name}")
    click.echo(f"  {name} reset to {pdef.default_val}")


@param.command("list-names")
@click.option("--group", default=None, help="Filter by group.")
@click.option("--search", "query", default=None, help="Search by name/description.")
@click.pass_context
def param_list_names(ctx, group, query):
    """List available parameter names."""
    if query:
        results = search_params(query)
    elif group:
        results = list_params_by_group(group)
    else:
        results = list(PARAM_REGISTRY.values())
    if ctx.obj.get("json"):
        _output([{"name": p.name, "group": p.group, "description": p.description}
                 for p in results], as_json=True)
    else:
        click.echo(f"  {len(results)} parameters:")
        for p in results[:50]:
            click.echo(f"    {p.name:40s}  [{p.group}]  {p.description}")
        if len(results) > 50:
            click.echo(f"    ... and {len(results) - 50} more (use --search to filter)")


# -- osc group -----------------------------------------------------------

@cli.group()
@click.pass_context
def osc(ctx):
    """Oscillator operations: info, set."""


@osc.command("info")
@click.argument("num", type=click.IntRange(1, 3), default=1)
@click.pass_context
def osc_info(ctx, num):
    """Show oscillator settings (1, 2, or 3)."""
    _require_preset(ctx)
    settings = _session.preset.get("settings", {})
    prefix = f"osc_{num}"
    on = settings.get(f"{prefix}_on", 0) > 0
    data = {"oscillator": num, "enabled": on,
            "level": settings.get(f"{prefix}_level", 0.7),
            "pan": settings.get(f"{prefix}_pan", 0.0),
            "transpose": int(settings.get(f"{prefix}_transpose", 0)),
            "tune": settings.get(f"{prefix}_tune", 0.0),
            "unison_voices": int(settings.get(f"{prefix}_unison_voices", 1)),
            "unison_detune": settings.get(f"{prefix}_unison_detune", 2.2),
            "wave_frame": int(settings.get(f"{prefix}_wave_frame", 0))}
    if ctx.obj.get("json"):
        _output(data, as_json=True)
    else:
        click.echo(f"  Oscillator {num}: {'ON' if on else 'OFF'}")
        for k, v in data.items():
            if k not in ("oscillator", "enabled"):
                click.echo(f"    {k:25s} = {v}")


@osc.command("set")
@click.argument("num", type=click.IntRange(1, 3))
@click.argument("param_name")
@click.argument("value", type=float)
@click.pass_context
def osc_set(ctx, num, param_name, value):
    """Set an oscillator parameter. E.g.: osc set 1 level 0.8"""
    _require_preset(ctx)
    full_name = f"osc_{num}_{param_name}"
    pdef = get_param(full_name)
    if not pdef:
        click.echo(f"Error: Unknown parameter: {full_name}", err=True)
        ctx.exit(1)
    _session.set_param(full_name, value)
    click.echo(f"  {full_name} = {value}")


# -- filter group --------------------------------------------------------

@cli.group("filter")
@click.pass_context
def filter_cmd(ctx):
    """Filter operations: info, set."""


@filter_cmd.command("info")
@click.argument("num", type=click.IntRange(1, 2), default=1)
@click.pass_context
def filter_info(ctx, num):
    """Show filter settings (1 or 2)."""
    _require_preset(ctx)
    settings = _session.preset.get("settings", {})
    prefix = f"filter_{num}"
    on = settings.get(f"{prefix}_on", 0) > 0
    model_num = int(settings.get(f"{prefix}_model", 0))
    data = {"filter": num, "enabled": on,
            "cutoff": settings.get(f"{prefix}_cutoff", 60.0),
            "resonance": settings.get(f"{prefix}_resonance", 0.2),
            "drive": settings.get(f"{prefix}_drive", 0.0),
            "model": FILTER_MODEL_NAMES.get(model_num, str(model_num))}
    if ctx.obj.get("json"):
        _output(data, as_json=True)
    else:
        click.echo(f"  Filter {num}: {'ON' if on else 'OFF'}")
        for k, v in data.items():
            if k != "filter":
                click.echo(f"    {k:15s} = {v}")


@filter_cmd.command("set")
@click.argument("num", type=click.IntRange(1, 2))
@click.argument("param_name")
@click.argument("value", type=float)
@click.pass_context
def filter_set(ctx, num, param_name, value):
    """Set a filter parameter. E.g.: filter set 1 cutoff 80.0"""
    _require_preset(ctx)
    full_name = f"filter_{num}_{param_name}"
    pdef = get_param(full_name)
    if not pdef:
        click.echo(f"Error: Unknown parameter: {full_name}", err=True)
        ctx.exit(1)
    _session.set_param(full_name, value)
    click.echo(f"  {full_name} = {value}")


# -- env group -----------------------------------------------------------

@cli.group()
@click.pass_context
def env(ctx):
    """Envelope operations: info, set."""


@env.command("info")
@click.argument("num", type=click.IntRange(1, 6), default=1)
@click.pass_context
def env_info(ctx, num):
    """Show envelope ADSR (1-6)."""
    _require_preset(ctx)
    settings = _session.preset.get("settings", {})
    prefix = f"env_{num}"
    a = settings.get(f"{prefix}_attack", 0.01)
    d = settings.get(f"{prefix}_decay", 0.5)
    s = settings.get(f"{prefix}_sustain", 0.7)
    r = settings.get(f"{prefix}_release", 0.3)
    data = {"envelope": num, "attack": a, "decay": d, "sustain": s, "release": r}
    if ctx.obj.get("json"):
        _output(data, as_json=True)
    else:
        click.echo(f"  Envelope {num}: A={a}  D={d}  S={s}  R={r}")


@env.command("set")
@click.argument("num", type=click.IntRange(1, 6))
@click.argument("param_name")
@click.argument("value", type=float)
@click.pass_context
def env_set(ctx, num, param_name, value):
    """Set an envelope parameter. E.g.: env set 1 attack 0.05"""
    _require_preset(ctx)
    full_name = f"env_{num}_{param_name}"
    pdef = get_param(full_name)
    if not pdef:
        click.echo(f"Error: Unknown parameter: {full_name}", err=True)
        ctx.exit(1)
    _session.set_param(full_name, value)
    click.echo(f"  {full_name} = {value}")


# -- lfo group -----------------------------------------------------------

@cli.group()
@click.pass_context
def lfo(ctx):
    """LFO operations: info, set."""


@lfo.command("info")
@click.argument("num", type=click.IntRange(1, 8), default=1)
@click.pass_context
def lfo_info(ctx, num):
    """Show LFO settings (1-8)."""
    _require_preset(ctx)
    settings = _session.preset.get("settings", {})
    prefix = f"lfo_{num}"
    data = {"lfo": num,
            "frequency": settings.get(f"{prefix}_frequency", 2.0),
            "phase": settings.get(f"{prefix}_phase", 0.0),
            "sync": int(settings.get(f"{prefix}_sync", 0)),
            "tempo": int(settings.get(f"{prefix}_tempo", 7))}
    if ctx.obj.get("json"):
        _output(data, as_json=True)
    else:
        click.echo(f"  LFO {num}:")
        for k, v in data.items():
            if k != "lfo":
                click.echo(f"    {k:15s} = {v}")


@lfo.command("set")
@click.argument("num", type=click.IntRange(1, 8))
@click.argument("param_name")
@click.argument("value", type=float)
@click.pass_context
def lfo_set(ctx, num, param_name, value):
    """Set an LFO parameter. E.g.: lfo set 1 frequency 4.0"""
    _require_preset(ctx)
    full_name = f"lfo_{num}_{param_name}"
    pdef = get_param(full_name)
    if not pdef:
        click.echo(f"Error: Unknown parameter: {full_name}", err=True)
        ctx.exit(1)
    _session.set_param(full_name, value)
    click.echo(f"  {full_name} = {value}")


# -- fx group ------------------------------------------------------------

@cli.group()
@click.pass_context
def fx(ctx):
    """Effects operations: info, set, enable, disable, toggle."""


@fx.command("info")
@click.argument("effect_name", required=False)
@click.pass_context
def fx_info(ctx, effect_name):
    """Show effects status, or details for a specific effect."""
    _require_preset(ctx)
    if effect_name:
        ok, params, msg = get_effect_params(_session.preset, effect_name)
        if not ok:
            click.echo(f"Error: {msg}", err=True)
            ctx.exit(1)
        if ctx.obj.get("json"):
            _output(params, as_json=True)
        else:
            for pname, pinfo in sorted(params.items()):
                click.echo(f"  {pname:35s} = {pinfo['value']}")
    else:
        effects = list_effects(_session.preset)
        if ctx.obj.get("json"):
            _output(effects, as_json=True)
        else:
            for e in effects:
                click.echo(f"  {e['name']:14s} {'ON' if e['enabled'] else 'OFF'}")


@fx.command("set")
@click.argument("effect_name")
@click.argument("param_suffix")
@click.argument("value", type=float)
@click.pass_context
def fx_set(ctx, effect_name, param_suffix, value):
    """Set an effect parameter. E.g.: fx set reverb dry_wet 0.5"""
    _require_preset(ctx)
    _session._push_undo(f"set {effect_name}_{param_suffix} = {value}")
    ok, msg = set_effect_param(_session.preset, effect_name, param_suffix, value)
    if not ok:
        click.echo(f"Error: {msg}", err=True)
        ctx.exit(1)
    _session.modified = True
    click.echo(f"  {effect_name}_{param_suffix} = {value}")


@fx.command("enable")
@click.argument("effect_name")
@click.pass_context
def fx_enable(ctx, effect_name):
    """Enable an effect."""
    _require_preset(ctx)
    _session._push_undo(f"enable {effect_name}")
    ok, msg = enable_effect(_session.preset, effect_name)
    if not ok:
        click.echo(f"Error: {msg}", err=True)
        ctx.exit(1)
    _session.modified = True
    click.echo(f"  {effect_name}: ON")


@fx.command("disable")
@click.argument("effect_name")
@click.pass_context
def fx_disable(ctx, effect_name):
    """Disable an effect."""
    _require_preset(ctx)
    _session._push_undo(f"disable {effect_name}")
    ok, msg = disable_effect(_session.preset, effect_name)
    if not ok:
        click.echo(f"Error: {msg}", err=True)
        ctx.exit(1)
    _session.modified = True
    click.echo(f"  {effect_name}: OFF")


@fx.command("toggle")
@click.argument("effect_name")
@click.pass_context
def fx_toggle(ctx, effect_name):
    """Toggle an effect on/off."""
    _require_preset(ctx)
    _session._push_undo(f"toggle {effect_name}")
    ok, new_state, msg = toggle_effect(_session.preset, effect_name)
    if not ok:
        click.echo(f"Error: {msg}", err=True)
        ctx.exit(1)
    _session.modified = True
    click.echo(f"  {effect_name}: {'ON' if new_state else 'OFF'}")


# -- mod group -----------------------------------------------------------

@cli.group()
@click.pass_context
def mod(ctx):
    """Modulation routing: list, add, remove."""


@mod.command("list")
@click.pass_context
def mod_list(ctx):
    """List all modulation routings."""
    _require_preset(ctx)
    mods = list_modulations(_session.preset)
    if ctx.obj.get("json"):
        _output(mods, as_json=True)
    else:
        if not mods:
            click.echo("  No modulation routings.")
        else:
            for m in mods:
                click.echo(f"  {m['index']:2d}. {m['source']:20s} -> "
                            f"{m['destination']:30s}  amt={m['amount']}")


@mod.command("add")
@click.argument("source")
@click.argument("destination")
@click.option("--amount", type=float, default=0.5, help="Modulation amount.")
@click.option("--bipolar", is_flag=True, help="Bipolar modulation.")
@click.option("--stereo", is_flag=True, help="Stereo modulation.")
@click.pass_context
def mod_add(ctx, source, destination, amount, bipolar, stereo):
    """Add a modulation routing."""
    _require_preset(ctx)
    _session._push_undo(f"add mod {source} -> {destination}")
    ok, slot, msg = add_modulation(_session.preset, source, destination,
                                   amount=amount, bipolar=bipolar, stereo=stereo)
    if not ok:
        click.echo(f"Error: {msg}", err=True)
        ctx.exit(1)
    _session.modified = True
    click.echo(f"  Added slot {slot}: {source} -> {destination} (amt={amount})")


@mod.command("remove")
@click.argument("index", type=int)
@click.pass_context
def mod_remove(ctx, index):
    """Remove a modulation routing by slot index."""
    _require_preset(ctx)
    _session._push_undo(f"remove mod slot {index}")
    ok, msg = remove_modulation(_session.preset, index)
    if not ok:
        click.echo(f"Error: {msg}", err=True)
        ctx.exit(1)
    _session.modified = True
    click.echo(f"  Removed modulation slot {index}")


@mod.command("sources")
@click.pass_context
def mod_sources(ctx):
    """List available modulation sources."""
    sources = list_sources()
    if ctx.obj.get("json"):
        _output(sources, as_json=True)
    else:
        for s in sources:
            click.echo(f"    {s}")


# -- session group -------------------------------------------------------

@cli.group("session")
@click.pass_context
def session_cmd(ctx):
    """Session management: status, undo, redo, history."""


@session_cmd.command("status")
@click.pass_context
def session_status(ctx):
    """Show current session status."""
    status = _session.status()
    if ctx.obj.get("json"):
        _output(status, as_json=True)
    else:
        for k, v in status.items():
            click.echo(f"  {k:18s} = {v}")


@session_cmd.command("undo")
@click.pass_context
def session_undo(ctx):
    """Undo the last action."""
    ok, desc = _session.undo()
    click.echo(f"  {'Undone' if ok else 'Cannot undo'}: {desc}")


@session_cmd.command("redo")
@click.pass_context
def session_redo(ctx):
    """Redo the last undone action."""
    ok, desc = _session.redo()
    click.echo(f"  {'Redone' if ok else 'Cannot redo'}: {desc}")


@session_cmd.command("history")
@click.option("--limit", type=int, default=20, help="Number of entries.")
@click.pass_context
def session_history(ctx, limit):
    """Show session action history."""
    history = _session.get_history(limit)
    if ctx.obj.get("json"):
        _output(history, as_json=True)
    else:
        if not history:
            click.echo("  No history.")
        else:
            for entry in history:
                click.echo(f"    {entry.get('action', '?'):15s}  {entry.get('details', {})}")


@session_cmd.command("save")
@click.option("--path", default=None, help="Session file path.")
@click.pass_context
def session_save(ctx, path):
    """Save session state to disk."""
    saved = _session.save_session(path)
    click.echo(f"  Session saved: {saved}")


@session_cmd.command("load")
@click.option("--path", default=None, help="Session file path.")
@click.pass_context
def session_load(ctx, path):
    """Load session state from disk."""
    ok = _session.restore_session(path)
    click.echo("  Session restored." if ok else "  No saved session found.")


# -- install-check -------------------------------------------------------

@cli.command("install-check")
@click.pass_context
def install_check(ctx):
    """Find Vital installation and show details."""
    info = get_install_info()
    if ctx.obj.get("json"):
        _output(info, as_json=True)
    else:
        click.echo("  Vital Installation:")
        click.echo(f"    Installed:    {info['installed']}")
        click.echo(f"    VST3:         {info.get('vst3') or 'not found'}")
        click.echo(f"    CLAP:         {info.get('clap') or 'not found'}")
        click.echo(f"    Standalone:   {info.get('standalone') or 'not found'}")
        click.echo(f"    Config dir:   {info['config_dir']}")
        click.echo(f"    Presets dir:  {info.get('presets_dir') or 'not found'}")


# -- export --------------------------------------------------------------

@cli.command("export")
@click.argument("path")
@click.option("--format", "fmt", type=click.Choice(["vital", "json", "summary"]),
              default="vital", help="Export format.")
@click.option("--overwrite", is_flag=True, help="Overwrite existing file.")
@click.pass_context
def export_cmd(ctx, path, fmt, overwrite):
    """Export the current preset."""
    _require_preset(ctx)
    result = export_preset(_session.preset, path, fmt=fmt, overwrite=overwrite)
    if ctx.obj.get("json"):
        _output(result, as_json=True)
    else:
        click.echo(f"  Exported: {result['path']} ({result.get('file_size', '?')} bytes)")


# -- REPL ----------------------------------------------------------------

@cli.command("repl")
@click.pass_context
def repl(ctx):
    """Start interactive REPL mode."""
    from cli_anything.vital.utils.repl_skin import ReplSkin

    skin = ReplSkin("vital", version=__version__)
    skin.print_banner()
    pt_session = skin.create_prompt_session()

    while True:
        try:
            project = _session.preset_name if _session.has_preset else ""
            modified = _session.modified
            line = skin.get_input(pt_session, project_name=project, modified=modified)
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not line:
            continue

        parts = line.strip().split()
        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            if _session.modified:
                skin.warning("Unsaved changes. 'preset save' first, or 'quit!' to force.")
                continue
            skin.print_goodbye()
            break

        if cmd in ("quit!", "exit!", "q!"):
            skin.print_goodbye()
            break

        if cmd == "help":
            skin.help({
                "preset new/open/save/save-as/info/list/search/diff/validate/dirs": "Preset management",
                "param get/set/dump/reset/list-names": "Parameter operations",
                "osc info/set <num>": "Oscillator controls",
                "filter info/set <num>": "Filter controls",
                "env info/set <num>": "Envelope ADSR",
                "lfo info/set <num>": "LFO controls",
                "fx info/set/enable/disable/toggle": "Effects chain",
                "mod list/add/remove/sources": "Modulation routing",
                "session status/undo/redo/history/save/load": "Session management",
                "install-check": "Find Vital installation",
                "export <path>": "Export preset",
                "quit / exit": "Exit REPL",
            })
            continue

        try:
            cli.main(args=parts, standalone_mode=False,
                     **(ctx.parent.params if ctx.parent else {}))
        except SystemExit:
            pass
        except click.UsageError as e:
            skin.error(str(e))
        except click.exceptions.MissingParameter as e:
            skin.error(str(e))
        except (FileNotFoundError, FileExistsError, ValueError) as e:
            skin.error(str(e))
        except Exception as e:
            skin.error(f"{type(e).__name__}: {e}")


def main():
    """CLI entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
