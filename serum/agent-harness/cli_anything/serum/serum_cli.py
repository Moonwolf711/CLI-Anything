"""cli-anything-serum -- CLI harness for Xfer Records Serum synthesizer.

Provides preset file management, binary FXP parsing, parameter extraction
and modification, wavetable management, and library organization.

Works with:
  - Serum 1 .fxp files (CcnK + FPCh + zlib-compressed float32[512])
  - Serum 2 .SerumPreset files (XferJson + CBOR + Zstandard)
  - Wavetable .wav files

Usage:
  cli-anything-serum                    # Enter interactive REPL
  cli-anything-serum preset list        # List all presets
  cli-anything-serum preset info X.fxp  # Inspect a preset
  cli-anything-serum param dump X.fxp   # Dump all 512 parameters
  cli-anything-serum --json preset list # JSON output
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

import click

from cli_anything.serum.core.fxp import (
    PARAM_MAP,
    SERUM_PARAM_COUNT,
    diff_params,
    dump_params,
    get_param,
    read_fxp,
    set_param,
    validate_fxp,
    write_fxp,
)
from cli_anything.serum.core.preset import (
    duplicate_preset,
    find_duplicates,
    find_preset_dirs,
    organize_by_category,
    preset_info,
    scan_presets,
    scan_wavetables,
    search_presets,
    wavetable_info,
)
from cli_anything.serum.core.session import Session
from cli_anything.serum.utils.repl_skin import ReplSkin

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

_session = Session()
_skin = ReplSkin("serum", version="1.0.0")

# Pass --json flag through Click context
pass_json = click.make_pass_decorator(dict, ensure=True)


def _output(data: Any, ctx: click.Context) -> None:
    """Output data as JSON or human-readable, based on --json flag."""
    use_json = ctx.obj.get("json", False) if ctx.obj else False
    if use_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        # Pretty-print dicts/lists
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    click.echo(f"  {k}: {json.dumps(v, indent=4, default=str)}")
                else:
                    click.echo(f"  {k}: {v}")
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    line = "  " + " | ".join(
                        f"{k}={v}" for k, v in item.items()
                        if k != "params"
                    )
                    click.echo(line)
                else:
                    click.echo(f"  {item}")
        else:
            click.echo(str(data))


# ---------------------------------------------------------------------------
# Main CLI group
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--json", "use_json", is_flag=True, default=False,
              help="Output in JSON format for machine consumption.")
@click.version_option("1.0.0", prog_name="cli-anything-serum")
@click.pass_context
def cli(ctx: click.Context, use_json: bool) -> None:
    """CLI harness for Xfer Records Serum synthesizer.

    Manage presets, parse FXP binaries, modify parameters, and organize
    your Serum preset library from the command line.
    """
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# ---------------------------------------------------------------------------
# PRESET commands
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def preset(ctx: click.Context) -> None:
    """Preset file operations (list, search, info, create, duplicate)."""
    pass


@preset.command("list")
@click.option("-d", "--dir", "directory", default=None,
              help="Directory to scan (default: all known Serum dirs).")
@click.option("-p", "--pattern", default="*.fxp",
              help="Glob pattern (default: *.fxp, use *.SerumPreset for v2).")
@click.option("--limit", default=0, type=int,
              help="Max results to show (0 = all).")
@click.pass_context
def preset_list(ctx: click.Context, directory: str | None,
                pattern: str, limit: int) -> None:
    """List presets in Serum preset directories."""
    results = scan_presets(root=directory, pattern=pattern)
    if limit > 0:
        results = results[:limit]
    _output(results, ctx)
    if not ctx.obj.get("json"):
        click.echo(f"\n  Total: {len(results)} presets")


@preset.command("search")
@click.argument("query")
@click.option("-d", "--dir", "directory", default=None,
              help="Directory to search.")
@click.option("-p", "--pattern", default="*.fxp",
              help="Glob pattern.")
@click.pass_context
def preset_search(ctx: click.Context, query: str,
                  directory: str | None, pattern: str) -> None:
    """Search presets by name (case-insensitive substring match)."""
    results = search_presets(query, root=directory, pattern=pattern)
    _output(results, ctx)
    if not ctx.obj.get("json"):
        click.echo(f"\n  Found: {len(results)} matches for '{query}'")


@preset.command("info")
@click.argument("path")
@click.pass_context
def preset_info_cmd(ctx: click.Context, path: str) -> None:
    """Show detailed info about a preset file."""
    try:
        info = preset_info(path)
        _output(info, ctx)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


@preset.command("open")
@click.argument("path")
@click.pass_context
def preset_open(ctx: click.Context, path: str) -> None:
    """Load a .fxp preset into the session for editing."""
    try:
        fxp = read_fxp(path)
        _session.set_preset(fxp, path)
        _output({
            "loaded": True,
            "name": fxp["name"],
            "path": path,
            "param_count": fxp["param_count"],
        }, ctx)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


@preset.command("create")
@click.argument("path")
@click.option("-n", "--name", default="Init Patch",
              help="Program name for the preset.")
@click.option("--overwrite", is_flag=True, default=False,
              help="Overwrite if file exists.")
@click.pass_context
def preset_create(ctx: click.Context, path: str, name: str,
                  overwrite: bool) -> None:
    """Create a new Serum 1 .fxp preset with default (init) parameters."""
    try:
        out = write_fxp(path, name, overwrite=overwrite)
        # Also load into session
        fxp = read_fxp(out)
        _session.set_preset(fxp, out)
        _output({
            "created": True,
            "path": out,
            "name": name,
        }, ctx)
    except (FileExistsError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


@preset.command("save")
@click.option("-o", "--output", "output_path", default=None,
              help="Save to a different path (Save As).")
@click.option("--overwrite", is_flag=True, default=False,
              help="Overwrite if file exists.")
@click.pass_context
def preset_save(ctx: click.Context, output_path: str | None,
                overwrite: bool) -> None:
    """Save the current session preset back to an .fxp file."""
    try:
        p = _session.get_preset()
        save_path = output_path or _session.preset_path
        if not save_path:
            click.echo("Error: No path specified. Use -o <path>.", err=True)
            ctx.exit(1)
            return

        out = write_fxp(
            save_path,
            p["name"],
            params=p["params"],
            overwrite=overwrite,
        )
        _session.preset_path = out
        _session._modified = False
        _output({"saved": True, "path": out}, ctx)
    except (RuntimeError, FileExistsError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


@preset.command("duplicate")
@click.argument("source")
@click.option("-n", "--name", default=None,
              help="New preset name (stem only).")
@click.option("-o", "--output", "dest", default=None,
              help="Destination path.")
@click.pass_context
def preset_duplicate_cmd(ctx: click.Context, source: str,
                         name: str | None, dest: str | None) -> None:
    """Duplicate a preset file."""
    try:
        out = duplicate_preset(source, dest=dest, new_name=name)
        _output({"duplicated": True, "source": source, "dest": out}, ctx)
    except (FileNotFoundError, OSError) as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


@preset.command("validate")
@click.argument("path")
@click.pass_context
def preset_validate(ctx: click.Context, path: str) -> None:
    """Validate an .fxp file structure and report issues."""
    result = validate_fxp(path)
    _output(result, ctx)


@preset.command("dirs")
@click.pass_context
def preset_dirs(ctx: click.Context) -> None:
    """Show known Serum preset directories and their status."""
    dirs = find_preset_dirs()
    _output(dirs, ctx)


# ---------------------------------------------------------------------------
# PARAM commands
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def param(ctx: click.Context) -> None:
    """Parameter operations (read, set, dump, diff)."""
    pass


@param.command("get")
@click.argument("path")
@click.argument("name_or_index")
@click.pass_context
def param_get(ctx: click.Context, path: str, name_or_index: str) -> None:
    """Get a parameter value from an .fxp file by name or index."""
    try:
        fxp = read_fxp(path)
        info = get_param(fxp["params"], name_or_index)
        _output(info, ctx)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


@param.command("set")
@click.argument("name_or_index")
@click.argument("value", type=float)
@click.pass_context
def param_set(ctx: click.Context, name_or_index: str, value: float) -> None:
    """Set a parameter in the currently loaded preset.

    Requires a preset loaded via 'preset open' or 'preset create'.
    """
    try:
        p = _session.get_preset()
        _session.snapshot(f"set {name_or_index} = {value}")
        p["params"] = set_param(p["params"], name_or_index, value)
        info = get_param(p["params"], name_or_index)
        _output(info, ctx)
    except (RuntimeError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


@param.command("dump")
@click.argument("path")
@click.option("--named-only", is_flag=True, default=False,
              help="Only show parameters with known names.")
@click.option("--non-default", is_flag=True, default=False,
              help="Only show parameters that differ from defaults.")
@click.pass_context
def param_dump(ctx: click.Context, path: str, named_only: bool,
               non_default: bool) -> None:
    """Dump all parameters from an .fxp preset file."""
    try:
        fxp = read_fxp(path)
        params = dump_params(fxp["params"], named_only=named_only)
        if non_default:
            params = [p for p in params if not p.get("is_default", True)]
        _output(params, ctx)
        if not ctx.obj.get("json"):
            click.echo(f"\n  Total: {len(params)} parameters")
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


@param.command("diff")
@click.argument("path_a")
@click.argument("path_b")
@click.pass_context
def param_diff(ctx: click.Context, path_a: str, path_b: str) -> None:
    """Compare parameters between two .fxp presets."""
    try:
        a = read_fxp(path_a)
        b = read_fxp(path_b)
        diffs = diff_params(a["params"], b["params"])
        _output(diffs, ctx)
        if not ctx.obj.get("json"):
            click.echo(f"\n  {len(diffs)} parameter differences")
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


@param.command("names")
@click.pass_context
def param_names(ctx: click.Context) -> None:
    """List all known parameter names and their indices."""
    names = []
    for idx in sorted(PARAM_MAP.keys()):
        pname, desc, pmin, pmax, pdefault = PARAM_MAP[idx]
        names.append({
            "index": idx,
            "name": pname,
            "description": desc,
            "min": pmin,
            "max": pmax,
            "default": pdefault,
        })
    _output(names, ctx)
    if not ctx.obj.get("json"):
        click.echo(f"\n  {len(names)} named parameters")


# ---------------------------------------------------------------------------
# WAVETABLE commands
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def wavetable(ctx: click.Context) -> None:
    """Wavetable file operations (list, info)."""
    pass


@wavetable.command("list")
@click.option("-d", "--dir", "directory", default=None,
              help="Directory to scan.")
@click.option("--limit", default=0, type=int,
              help="Max results (0 = all).")
@click.pass_context
def wavetable_list(ctx: click.Context, directory: str | None,
                   limit: int) -> None:
    """List wavetable .wav files."""
    results = scan_wavetables(root=directory)
    if limit > 0:
        results = results[:limit]
    _output(results, ctx)
    if not ctx.obj.get("json"):
        click.echo(f"\n  Total: {len(results)} wavetables")


@wavetable.command("info")
@click.argument("path")
@click.pass_context
def wavetable_info_cmd(ctx: click.Context, path: str) -> None:
    """Show WAV header info for a wavetable file."""
    try:
        info = wavetable_info(path)
        _output(info, ctx)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


# ---------------------------------------------------------------------------
# LIBRARY commands
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def library(ctx: click.Context) -> None:
    """Library management (scan, duplicates, organize, batch rename)."""
    pass


@library.command("scan")
@click.pass_context
def library_scan(ctx: click.Context) -> None:
    """Scan all known Serum directories and report stats."""
    from cli_anything.serum.utils.serum_backend import find_serum_installation

    install = find_serum_installation()
    dirs = find_preset_dirs()

    report = {
        "installation": install,
        "preset_dirs": dirs,
        "total_fxp": sum(d["preset_count"] for d in dirs if d["version"] == 1),
        "total_serum2": sum(d["preset_count"] for d in dirs if d["version"] == 2),
    }
    _output(report, ctx)


@library.command("duplicates")
@click.option("-d", "--dir", "directory", default=None,
              help="Directory to scan.")
@click.option("-p", "--pattern", default="*.fxp",
              help="Glob pattern.")
@click.pass_context
def library_duplicates(ctx: click.Context, directory: str | None,
                       pattern: str) -> None:
    """Find duplicate presets by content hash."""
    groups = find_duplicates(root=directory, pattern=pattern)
    _output(groups, ctx)
    if not ctx.obj.get("json"):
        total_dupes = sum(len(g) - 1 for g in groups)
        click.echo(
            f"\n  {len(groups)} duplicate groups, "
            f"{total_dupes} redundant files"
        )


@library.command("organize")
@click.argument("source_dir")
@click.argument("dest_dir")
@click.option("--dry-run/--execute", default=True,
              help="Dry run by default; use --execute to actually copy.")
@click.pass_context
def library_organize(ctx: click.Context, source_dir: str, dest_dir: str,
                     dry_run: bool) -> None:
    """Organize presets into category folders based on name prefixes.

    Common naming: BA=Bass, LD=Lead, PD=Pad, PL=Pluck, FX=Effects, etc.
    """
    actions = organize_by_category(source_dir, dest_dir, dry_run=dry_run)
    _output(actions, ctx)
    if not ctx.obj.get("json"):
        categories = set(a["category"] for a in actions)
        click.echo(
            f"\n  {len(actions)} presets -> {len(categories)} categories"
            f" ({'DRY RUN' if dry_run else 'EXECUTED'})"
        )


@library.command("batch-rename")
@click.argument("directory")
@click.option("--prefix", default=None, help="Add prefix to all names.")
@click.option("--replace", nargs=2, default=None,
              help="Replace substring: --replace OLD NEW")
@click.option("--dry-run/--execute", default=True,
              help="Dry run by default.")
@click.pass_context
def library_batch_rename(ctx: click.Context, directory: str,
                         prefix: str | None, replace: tuple | None,
                         dry_run: bool) -> None:
    """Batch rename preset files in a directory."""
    d = Path(directory)
    if not d.is_dir():
        click.echo(f"Error: Not a directory: {directory}", err=True)
        ctx.exit(1)
        return

    actions = []
    for p in sorted(d.glob("*.fxp")):
        new_name = p.stem
        if prefix:
            new_name = f"{prefix}{new_name}"
        if replace and len(replace) == 2:
            new_name = new_name.replace(replace[0], replace[1])
        new_name += p.suffix

        if new_name != p.name:
            new_path = p.parent / new_name
            actions.append({
                "old": str(p),
                "new": str(new_path),
                "old_name": p.name,
                "new_name": new_name,
            })
            if not dry_run:
                p.rename(new_path)

    _output(actions, ctx)
    if not ctx.obj.get("json"):
        click.echo(
            f"\n  {len(actions)} renames"
            f" ({'DRY RUN' if dry_run else 'EXECUTED'})"
        )


# ---------------------------------------------------------------------------
# SESSION commands
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def session(ctx: click.Context) -> None:
    """Session management (status, undo, redo, history, save, load)."""
    pass


@session.command("status")
@click.pass_context
def session_status(ctx: click.Context) -> None:
    """Show current session status."""
    _output(_session.status(), ctx)


@session.command("undo")
@click.pass_context
def session_undo(ctx: click.Context) -> None:
    """Undo the last parameter change."""
    try:
        desc = _session.undo()
        _output({"undone": True, "description": desc}, ctx)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


@session.command("redo")
@click.pass_context
def session_redo(ctx: click.Context) -> None:
    """Redo the last undone change."""
    try:
        desc = _session.redo()
        _output({"redone": True, "description": desc}, ctx)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


@session.command("history")
@click.pass_context
def session_history(ctx: click.Context) -> None:
    """Show undo history."""
    history = _session.list_history()
    _output(history, ctx)
    if not ctx.obj.get("json"):
        click.echo(f"\n  {len(history)} entries")


@session.command("save")
@click.option("-o", "--output", "path", default=None,
              help="Session save path.")
@click.pass_context
def session_save(ctx: click.Context, path: str | None) -> None:
    """Save session workspace to a JSON file."""
    try:
        out = _session.save_session(path)
        _output({"saved": True, "path": out}, ctx)
    except (RuntimeError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


@session.command("load")
@click.argument("path")
@click.pass_context
def session_load(ctx: click.Context, path: str) -> None:
    """Load a previously saved session."""
    try:
        _session.load_session(path)
        _output({
            "loaded": True,
            "path": path,
            "preset_name": (
                _session.preset.get("name") if _session.preset else None
            ),
        }, ctx)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        click.echo(f"Error: {exc}", err=True)
        ctx.exit(1)


# ---------------------------------------------------------------------------
# INSTALL-CHECK command
# ---------------------------------------------------------------------------

@cli.command("install-check")
@click.pass_context
def install_check(ctx: click.Context) -> None:
    """Check Serum installation status and show diagnostics."""
    from cli_anything.serum.utils.serum_backend import find_serum_installation

    info = find_serum_installation()
    _output(info, ctx)


# ---------------------------------------------------------------------------
# REPL command
# ---------------------------------------------------------------------------

REPL_COMMANDS = {
    "preset list":       "List presets in known directories",
    "preset search Q":   "Search presets by name",
    "preset info PATH":  "Show preset details",
    "preset open PATH":  "Load preset into session",
    "preset create PATH": "Create new init preset",
    "preset save":       "Save current preset to disk",
    "preset duplicate SRC": "Duplicate a preset file",
    "preset validate PATH": "Validate .fxp structure",
    "preset dirs":       "Show known preset directories",
    "param get PATH IDX": "Get a parameter by name/index",
    "param set IDX VAL": "Set a parameter (session)",
    "param dump PATH":   "Dump all 512 parameters",
    "param diff A B":    "Compare two presets",
    "param names":       "List all known parameter names",
    "wavetable list":    "List wavetable .wav files",
    "wavetable info PATH": "Show wavetable WAV info",
    "library scan":      "Scan all Serum directories",
    "library duplicates": "Find duplicate presets",
    "library organize SRC DST": "Organize by category",
    "library batch-rename DIR": "Batch rename presets",
    "session status":    "Show session state",
    "session undo":      "Undo last change",
    "session redo":      "Redo last undone change",
    "session history":   "Show undo history",
    "session save":      "Save session workspace",
    "session load PATH": "Load saved session",
    "install-check":     "Check Serum installation",
    "help":              "Show this help",
    "quit / exit":       "Exit the REPL",
}


@cli.command("repl")
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Enter interactive REPL mode (default when no subcommand given)."""
    _skin.print_banner()

    pt_session = _skin.create_prompt_session()

    while True:
        try:
            preset_name = ""
            if _session.has_preset():
                preset_name = _session.preset.get("name", "untitled")

            line = _skin.get_input(
                pt_session,
                project_name=preset_name,
                modified=_session.modified,
            )
        except (EOFError, KeyboardInterrupt):
            _skin.print_goodbye()
            break

        if not line:
            continue

        cmd = line.strip()
        if cmd in ("quit", "exit", "q"):
            _skin.print_goodbye()
            break

        if cmd == "help":
            _skin.help(REPL_COMMANDS)
            continue

        # Parse the line as CLI args and dispatch
        try:
            args = shlex.split(cmd)
        except ValueError as exc:
            _skin.error(f"Parse error: {exc}")
            continue

        # Inject --json if the context has it
        if ctx.obj.get("json"):
            args = ["--json"] + args

        try:
            cli.main(args=args, standalone_mode=False, **{"parent": ctx})
        except SystemExit:
            pass
        except click.exceptions.UsageError as exc:
            _skin.error(str(exc))
        except Exception as exc:
            _skin.error(f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point."""
    cli(obj={})


if __name__ == "__main__":
    main()
