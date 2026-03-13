#!/usr/bin/env python3
"""Example: Batch audit a Serum preset library.

This script demonstrates how an AI agent would use the Serum CLI
to audit a preset library -- scanning, finding duplicates, and
reporting statistics.

Usage:
    python examples/batch_audit.py [preset_dir]
"""

import json
import sys
from pathlib import Path

from cli_anything.serum.core.fxp import dump_params, read_fxp
from cli_anything.serum.core.preset import (
    find_duplicates,
    find_preset_dirs,
    scan_presets,
    search_presets,
)


def main():
    # Use provided dir or auto-detect
    if len(sys.argv) > 1:
        preset_dir = sys.argv[1]
    else:
        dirs = find_preset_dirs()
        available = [d for d in dirs if d["exists"] and d["version"] == 1]
        if not available:
            print("No Serum preset directories found.")
            sys.exit(1)
        preset_dir = available[0]["path"]
        print(f"Auto-detected: {preset_dir}")

    print(f"\nScanning: {preset_dir}")
    print("=" * 60)

    # Scan all presets
    presets = scan_presets(root=preset_dir, pattern="*.fxp")
    print(f"Total presets: {len(presets)}")

    # Search by common categories
    categories = ["bass", "lead", "pad", "pluck", "fx", "arp", "sub"]
    print(f"\nCategory distribution:")
    for cat in categories:
        matches = search_presets(cat, root=preset_dir)
        if matches:
            print(f"  {cat:10s}: {len(matches)} presets")

    # Find duplicates
    dupes = find_duplicates(root=preset_dir)
    total_dupes = sum(len(g) - 1 for g in dupes)
    print(f"\nDuplicate analysis:")
    print(f"  Groups: {len(dupes)}")
    print(f"  Redundant files: {total_dupes}")

    # Sample a preset and show its non-default params
    if presets:
        sample = presets[0]
        print(f"\nSample preset: {sample['name']}")
        try:
            fxp = read_fxp(sample["path"])
            params = dump_params(fxp["params"], named_only=True)
            non_default = [p for p in params if not p.get("is_default")]
            print(f"  Non-default parameters: {len(non_default)}")
            for p in non_default[:5]:
                print(f"    [{p['index']:3d}] {p['name']:25s} = {p['value']:.4f}")
        except Exception as exc:
            print(f"  Parse error: {exc}")

    # JSON summary for agent consumption
    summary = {
        "directory": preset_dir,
        "total_presets": len(presets),
        "duplicate_groups": len(dupes),
        "redundant_files": total_dupes,
    }
    print(f"\n--- JSON Summary ---")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
