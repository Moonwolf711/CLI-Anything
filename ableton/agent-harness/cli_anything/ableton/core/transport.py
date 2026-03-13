"""Transport operations for Ableton Live projects.

Handles tempo, time signature, loop, and transport state.
For offline (.als file) mode, these modify the project's transport settings.
For live (OSC) mode, these control a running Ableton instance.
"""

from typing import Optional

from ..utils import als_xml
from ..utils.ableton_backend import OscBridge
from .session import Session


def get_transport(session: Session) -> dict:
    """Get current transport settings.

    Args:
        session: The active session.

    Returns:
        Dict with transport info.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    transport = als_xml.get_transport(session.root)

    return {
        "tempo": float(als_xml.get_value(transport, "Tempo", "120")),
        "time_signature": {
            "numerator": int(als_xml.get_value(transport, "TimeSignatureNumerator", "4")),
            "denominator": int(als_xml.get_value(transport, "TimeSignatureDenominator", "4")),
        },
        "loop": {
            "enabled": als_xml.get_value(transport, "LoopOn", "false") == "true",
            "start": float(als_xml.get_value(transport, "LoopStart", "0")),
            "length": float(als_xml.get_value(transport, "LoopLength", "16")),
        },
        "position": float(als_xml.get_value(transport, "CurrentTime", "0")),
    }


def set_tempo(session: Session, tempo: float) -> dict:
    """Set the project tempo.

    Args:
        session: The active session.
        tempo: Tempo in BPM (20-999).

    Returns:
        Dict with result.
    """
    if not 20 <= tempo <= 999:
        raise ValueError(f"Tempo must be 20-999 BPM, got {tempo}")

    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()
    transport = als_xml.get_transport(session.root)
    als_xml.set_value(transport, "Tempo", str(tempo))

    return {"status": "set", "tempo": tempo}


def set_time_signature(session: Session, numerator: int, denominator: int) -> dict:
    """Set the project time signature.

    Args:
        session: The active session.
        numerator: Beats per bar (1-32).
        denominator: Beat value (1, 2, 4, 8, 16).

    Returns:
        Dict with result.
    """
    if not 1 <= numerator <= 32:
        raise ValueError(f"Numerator must be 1-32, got {numerator}")
    if denominator not in (1, 2, 4, 8, 16):
        raise ValueError(f"Denominator must be 1, 2, 4, 8, or 16, got {denominator}")

    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()
    transport = als_xml.get_transport(session.root)
    als_xml.set_value(transport, "TimeSignatureNumerator", str(numerator))
    als_xml.set_value(transport, "TimeSignatureDenominator", str(denominator))

    return {
        "status": "set",
        "time_signature": f"{numerator}/{denominator}",
    }


def set_loop(
    session: Session,
    enabled: Optional[bool] = None,
    start: Optional[float] = None,
    length: Optional[float] = None,
) -> dict:
    """Configure loop settings.

    Args:
        session: The active session.
        enabled: Enable/disable loop (None = don't change).
        start: Loop start position in beats (None = don't change).
        length: Loop length in beats (None = don't change).

    Returns:
        Dict with result.
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    session.checkpoint()
    transport = als_xml.get_transport(session.root)

    if enabled is not None:
        als_xml.set_value(transport, "LoopOn", "true" if enabled else "false")
    if start is not None:
        if start < 0:
            raise ValueError(f"Loop start must be >= 0, got {start}")
        als_xml.set_value(transport, "LoopStart", str(start))
    if length is not None:
        if length <= 0:
            raise ValueError(f"Loop length must be > 0, got {length}")
        als_xml.set_value(transport, "LoopLength", str(length))

    return get_transport(session)


# ── OSC transport controls ──────────────────────────────────────────

def osc_play(bridge: OscBridge) -> dict:
    """Send play command via OSC.

    Args:
        bridge: Connected OscBridge.

    Returns:
        Dict with result.
    """
    return bridge.send("/live/song/start_playing")


def osc_stop(bridge: OscBridge) -> dict:
    """Send stop command via OSC.

    Args:
        bridge: Connected OscBridge.

    Returns:
        Dict with result.
    """
    return bridge.send("/live/song/stop_playing")


def osc_record(bridge: OscBridge) -> dict:
    """Toggle record via OSC.

    Args:
        bridge: Connected OscBridge.

    Returns:
        Dict with result.
    """
    return bridge.send("/live/song/record_mode")


def osc_set_tempo(bridge: OscBridge, tempo: float) -> dict:
    """Set tempo via OSC.

    Args:
        bridge: Connected OscBridge.
        tempo: Tempo in BPM.

    Returns:
        Dict with result.
    """
    if not 20 <= tempo <= 999:
        raise ValueError(f"Tempo must be 20-999 BPM, got {tempo}")
    return bridge.send("/live/song/set/tempo", tempo)


def osc_fire_scene(bridge: OscBridge, index: int) -> dict:
    """Fire (launch) a scene via OSC.

    Args:
        bridge: Connected OscBridge.
        index: Scene index.

    Returns:
        Dict with result.
    """
    return bridge.send("/live/song/fire_scene", index)
