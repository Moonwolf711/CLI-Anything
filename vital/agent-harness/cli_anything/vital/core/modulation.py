"""Vital modulation matrix management.

Handles adding, removing, listing, and modifying modulation routings.
Vital supports up to 64 modulation connections, each defined by:
- source: the modulation source (LFO, envelope, macro, etc.)
- destination: the parameter being modulated
- amount: modulation depth (0.0 to 1.0)
- power: modulation curve shape
- bipolar: whether modulation is bipolar
- stereo: whether modulation differs between L/R channels
- bypass: whether the modulation is bypassed

Modulation routings are stored in the preset as:
  "modulations": [{"source": "lfo_1", "destination": "osc_1_level", ...}, ...]
and the per-slot parameters modulation_N_amount, modulation_N_power, etc.
"""

from typing import Optional

from cli_anything.vital.core.parameters import MODULATION_SOURCES, PARAM_REGISTRY


def list_modulations(preset: dict) -> list[dict]:
    """List all active modulation routings in a preset.

    Args:
        preset: Loaded Vital preset dict.

    Returns:
        List of modulation routing dicts with index, source, destination, amount.
    """
    modulations = preset.get("modulations", [])
    settings = preset.get("settings", {})
    results = []

    for i, mod in enumerate(modulations):
        slot = i + 1
        amount = settings.get(f"modulation_{slot}_amount", mod.get("line_mapping", {}).get("amount", 0))
        # Also try the modulation's own amount field
        if amount == 0:
            line = mod.get("line_mapping", {})
            if "points" in line:
                # Complex mapping, just note it
                amount = "complex"

        results.append({
            "index": slot,
            "source": mod.get("source", "unknown"),
            "destination": mod.get("destination", "unknown"),
            "amount": settings.get(f"modulation_{slot}_amount", 0),
            "power": settings.get(f"modulation_{slot}_power", 0),
            "bipolar": settings.get(f"modulation_{slot}_bipolar", 0) > 0,
            "stereo": settings.get(f"modulation_{slot}_stereo", 0) > 0,
            "bypass": settings.get(f"modulation_{slot}_bypass", 0) > 0,
        })

    return results


def add_modulation(preset: dict, source: str, destination: str,
                   amount: float = 0.5, bipolar: bool = False,
                   stereo: bool = False) -> tuple[bool, int, str]:
    """Add a new modulation routing.

    Args:
        preset: Preset dict to modify (in-place).
        source: Modulation source name (e.g., "lfo_1", "env_2").
        destination: Target parameter name (e.g., "osc_1_level").
        amount: Modulation amount (0.0 to 1.0).
        bipolar: Whether modulation is bipolar.
        stereo: Whether modulation differs per channel.

    Returns:
        (success, slot_index, error_message) tuple.
    """
    # Validate source
    if source not in MODULATION_SOURCES:
        return False, 0, f"Unknown modulation source: {source}. Valid: {', '.join(MODULATION_SOURCES[:10])}..."

    # Validate destination exists as a known parameter
    if destination not in PARAM_REGISTRY:
        return False, 0, f"Unknown destination parameter: {destination}"

    modulations = preset.setdefault("modulations", [])

    if len(modulations) >= 64:
        return False, 0, "Maximum 64 modulation routings reached"

    # Add the routing
    mod_entry = {
        "source": source,
        "destination": destination,
    }
    modulations.append(mod_entry)

    slot = len(modulations)
    settings = preset.setdefault("settings", {})
    settings[f"modulation_{slot}_amount"] = amount
    settings[f"modulation_{slot}_power"] = 0.0
    settings[f"modulation_{slot}_bipolar"] = 1.0 if bipolar else 0.0
    settings[f"modulation_{slot}_stereo"] = 1.0 if stereo else 0.0
    settings[f"modulation_{slot}_bypass"] = 0.0

    return True, slot, ""


def remove_modulation(preset: dict, index: int) -> tuple[bool, str]:
    """Remove a modulation routing by slot index.

    Args:
        preset: Preset dict to modify (in-place).
        index: 1-based slot index.

    Returns:
        (success, error_message) tuple.
    """
    modulations = preset.get("modulations", [])
    if index < 1 or index > len(modulations):
        return False, f"Invalid modulation index: {index} (have {len(modulations)} routings)"

    # Remove the routing
    removed = modulations.pop(index - 1)

    # Clean up settings for removed slot and shift remaining
    settings = preset.get("settings", {})
    total = len(modulations) + 1  # +1 because we already removed

    # Shift all slots after the removed one down by 1
    for i in range(index, total):
        for suffix in ["amount", "power", "bipolar", "stereo", "bypass"]:
            next_key = f"modulation_{i + 1}_{suffix}"
            curr_key = f"modulation_{i}_{suffix}"
            if next_key in settings:
                settings[curr_key] = settings[next_key]
            elif curr_key in settings:
                del settings[curr_key]

    # Clean up the last slot (now empty)
    for suffix in ["amount", "power", "bipolar", "stereo", "bypass"]:
        last_key = f"modulation_{total}_{suffix}"
        settings.pop(last_key, None)

    return True, ""


def update_modulation(preset: dict, index: int,
                      amount: Optional[float] = None,
                      power: Optional[float] = None,
                      bipolar: Optional[bool] = None,
                      stereo: Optional[bool] = None,
                      bypass: Optional[bool] = None) -> tuple[bool, str]:
    """Update properties of an existing modulation routing.

    Args:
        preset: Preset dict to modify (in-place).
        index: 1-based slot index.
        amount: New amount (if provided).
        power: New power curve (if provided).
        bipolar: New bipolar state (if provided).
        stereo: New stereo state (if provided).
        bypass: New bypass state (if provided).

    Returns:
        (success, error_message) tuple.
    """
    modulations = preset.get("modulations", [])
    if index < 1 or index > len(modulations):
        return False, f"Invalid modulation index: {index}"

    settings = preset.setdefault("settings", {})

    if amount is not None:
        settings[f"modulation_{index}_amount"] = max(0.0, min(1.0, amount))
    if power is not None:
        settings[f"modulation_{index}_power"] = max(-10.0, min(10.0, power))
    if bipolar is not None:
        settings[f"modulation_{index}_bipolar"] = 1.0 if bipolar else 0.0
    if stereo is not None:
        settings[f"modulation_{index}_stereo"] = 1.0 if stereo else 0.0
    if bypass is not None:
        settings[f"modulation_{index}_bypass"] = 1.0 if bypass else 0.0

    return True, ""


def list_sources() -> list[str]:
    """List all available modulation sources."""
    return list(MODULATION_SOURCES)


def list_destinations() -> list[str]:
    """List all parameters that can be modulation destinations."""
    return sorted(PARAM_REGISTRY.keys())
