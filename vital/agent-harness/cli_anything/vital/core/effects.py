"""Vital effects chain management.

Controls the 9 effects in Vital: chorus, compressor, delay, distortion,
EQ, filter FX, flanger, phaser, and reverb.
"""

from typing import Optional

from cli_anything.vital.core.parameters import (
    CHORUS_PARAMS, DELAY_PARAMS, DISTORTION_PARAMS, REVERB_PARAMS,
    PHASER_PARAMS, FLANGER_PARAMS, COMPRESSOR_PARAMS, EQ_PARAMS,
    EFFECT_NAMES, PARAM_REGISTRY,
)


# Map effect names to their parameter dicts
_EFFECT_PARAM_GROUPS = {
    "chorus": CHORUS_PARAMS,
    "delay": DELAY_PARAMS,
    "distortion": DISTORTION_PARAMS,
    "reverb": REVERB_PARAMS,
    "phaser": PHASER_PARAMS,
    "flanger": FLANGER_PARAMS,
    "compressor": COMPRESSOR_PARAMS,
    "eq": EQ_PARAMS,
}


def list_effects(preset: dict) -> list[dict]:
    """List all effects and their enabled/disabled status.

    Args:
        preset: Loaded Vital preset dict.

    Returns:
        List of effect info dicts.
    """
    settings = preset.get("settings", {})
    results = []

    for fx in EFFECT_NAMES:
        if fx == "filter_fx":
            on_key = "filter_fx_on"
            info = {
                "name": fx,
                "enabled": settings.get(on_key, 0) > 0,
                "on_key": on_key,
            }
        else:
            on_key = f"{fx}_on"
            info = {
                "name": fx,
                "enabled": settings.get(on_key, 0) > 0,
                "on_key": on_key,
            }

            # Include key parameters for each effect
            if fx in _EFFECT_PARAM_GROUPS:
                key_params = {}
                for pname, pdef in _EFFECT_PARAM_GROUPS[fx].items():
                    if pname != on_key:
                        key_params[pname] = settings.get(pname, pdef.default_val)
                info["parameters"] = key_params

        results.append(info)

    return results


def enable_effect(preset: dict, effect_name: str) -> tuple[bool, str]:
    """Enable an effect.

    Args:
        preset: Preset dict to modify (in-place).
        effect_name: Effect name (chorus, delay, etc.).

    Returns:
        (success, error_message) tuple.
    """
    effect_name = effect_name.lower()
    if effect_name not in EFFECT_NAMES:
        return False, f"Unknown effect: {effect_name}. Valid: {', '.join(EFFECT_NAMES)}"

    settings = preset.setdefault("settings", {})
    if effect_name == "filter_fx":
        settings["filter_fx_on"] = 1.0
    else:
        settings[f"{effect_name}_on"] = 1.0

    return True, ""


def disable_effect(preset: dict, effect_name: str) -> tuple[bool, str]:
    """Disable an effect.

    Args:
        preset: Preset dict to modify (in-place).
        effect_name: Effect name.

    Returns:
        (success, error_message) tuple.
    """
    effect_name = effect_name.lower()
    if effect_name not in EFFECT_NAMES:
        return False, f"Unknown effect: {effect_name}. Valid: {', '.join(EFFECT_NAMES)}"

    settings = preset.setdefault("settings", {})
    if effect_name == "filter_fx":
        settings["filter_fx_on"] = 0.0
    else:
        settings[f"{effect_name}_on"] = 0.0

    return True, ""


def toggle_effect(preset: dict, effect_name: str) -> tuple[bool, bool, str]:
    """Toggle an effect on/off.

    Args:
        preset: Preset dict to modify (in-place).
        effect_name: Effect name.

    Returns:
        (success, new_state, error_message) tuple.
    """
    effect_name = effect_name.lower()
    if effect_name not in EFFECT_NAMES:
        return False, False, f"Unknown effect: {effect_name}"

    settings = preset.setdefault("settings", {})
    if effect_name == "filter_fx":
        on_key = "filter_fx_on"
    else:
        on_key = f"{effect_name}_on"

    currently_on = settings.get(on_key, 0) > 0
    settings[on_key] = 0.0 if currently_on else 1.0
    new_state = not currently_on

    return True, new_state, ""


def get_effect_params(preset: dict, effect_name: str) -> tuple[bool, dict, str]:
    """Get all parameters for a specific effect.

    Args:
        preset: Loaded preset dict.
        effect_name: Effect name.

    Returns:
        (success, params_dict, error_message) tuple.
    """
    effect_name = effect_name.lower()
    if effect_name not in EFFECT_NAMES:
        return False, {}, f"Unknown effect: {effect_name}"

    settings = preset.get("settings", {})
    prefix = effect_name + "_" if effect_name != "filter_fx" else "filter_fx_"

    params = {}
    for key, value in settings.items():
        if key.startswith(prefix):
            pdef = PARAM_REGISTRY.get(key)
            params[key] = {
                "value": value,
                "description": pdef.description if pdef else "",
                "min": pdef.min_val if pdef else None,
                "max": pdef.max_val if pdef else None,
            }

    # Also include params from registry that might not be in settings yet
    if effect_name in _EFFECT_PARAM_GROUPS:
        for pname, pdef in _EFFECT_PARAM_GROUPS[effect_name].items():
            if pname not in params:
                params[pname] = {
                    "value": pdef.default_val,
                    "description": pdef.description,
                    "min": pdef.min_val,
                    "max": pdef.max_val,
                }

    return True, params, ""


def set_effect_param(preset: dict, effect_name: str,
                     param_suffix: str, value: float) -> tuple[bool, str]:
    """Set a specific effect parameter.

    Args:
        preset: Preset dict to modify (in-place).
        effect_name: Effect name (e.g., "chorus").
        param_suffix: Parameter suffix (e.g., "dry_wet" for chorus_dry_wet).
        value: New value.

    Returns:
        (success, error_message) tuple.
    """
    effect_name = effect_name.lower()
    if effect_name not in EFFECT_NAMES:
        return False, f"Unknown effect: {effect_name}"

    full_name = f"{effect_name}_{param_suffix}"
    pdef = PARAM_REGISTRY.get(full_name)
    if pdef is None:
        return False, f"Unknown parameter: {full_name}"

    if value < pdef.min_val or value > pdef.max_val:
        return False, f"Value {value} out of range [{pdef.min_val}, {pdef.max_val}]"

    settings = preset.setdefault("settings", {})
    settings[full_name] = value
    return True, ""


def configure_effect(preset: dict, effect_name: str,
                     params: dict[str, float]) -> tuple[int, list[str]]:
    """Configure multiple effect parameters at once.

    Args:
        preset: Preset dict to modify (in-place).
        effect_name: Effect name.
        params: Dict of param_suffix -> value.

    Returns:
        (success_count, error_messages) tuple.
    """
    success = 0
    errors = []
    for suffix, value in params.items():
        ok, msg = set_effect_param(preset, effect_name, suffix, value)
        if ok:
            success += 1
        else:
            errors.append(msg)
    return success, errors
