"""Vital synth parameter registry.

Comprehensive catalog of every Vital parameter with name, min, max,
default value, and human-readable description. This serves as the
ground truth for parameter validation, preset creation, and CLI help.

Architecture:
- 3 oscillators (osc_1, osc_2, osc_3)
- 2 filters (filter_1, filter_2) + 1 filter FX (filter_fx)
- 6 envelopes (env_1 through env_6)
- 8 LFOs (lfo_1 through lfo_8)
- 4 random LFOs (random_1 through random_4)
- 64 modulation slots (modulation_1 through modulation_64)
- 4 macro controls
- Effects: chorus, compressor, delay, distortion, EQ, flanger, phaser, reverb
- Sub oscillator, sample player
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ParamDef:
    """Definition of a single Vital parameter."""
    name: str
    min_val: float
    max_val: float
    default_val: float
    description: str
    group: str
    value_type: str = "float"  # float, int, bool, enum


# ── Global parameters ────────────────────────────────────────────────

GLOBAL_PARAMS: dict[str, ParamDef] = {
    "beats_per_minute": ParamDef("beats_per_minute", 20.0, 300.0, 120.0, "BPM for tempo-synced parameters", "global"),
    "bypass": ParamDef("bypass", 0.0, 1.0, 0.0, "Master bypass", "global", "bool"),
    "legato": ParamDef("legato", 0.0, 1.0, 0.0, "Legato mode", "global", "bool"),
    "macro_control_1": ParamDef("macro_control_1", 0.0, 1.0, 0.0, "Macro control 1", "global"),
    "macro_control_2": ParamDef("macro_control_2", 0.0, 1.0, 0.0, "Macro control 2", "global"),
    "macro_control_3": ParamDef("macro_control_3", 0.0, 1.0, 0.0, "Macro control 3", "global"),
    "macro_control_4": ParamDef("macro_control_4", 0.0, 1.0, 0.0, "Macro control 4", "global"),
    "pitch_bend_range": ParamDef("pitch_bend_range", 0.0, 48.0, 2.0, "Pitch bend range in semitones", "global"),
    "polyphony": ParamDef("polyphony", 1.0, 32.0, 8.0, "Maximum polyphony", "global", "int"),
    "voice_tune": ParamDef("voice_tune", -1.0, 1.0, 0.0, "Voice fine tune", "global"),
    "voice_transpose": ParamDef("voice_transpose", -48.0, 48.0, 0.0, "Voice transpose in semitones", "global", "int"),
    "voice_amplitude": ParamDef("voice_amplitude", 0.0, 2.0, 1.0, "Voice amplitude", "global"),
    "voice_priority": ParamDef("voice_priority", 0.0, 3.0, 0.0, "Voice priority (newest/oldest/highest/lowest)", "global", "enum"),
    "voice_override": ParamDef("voice_override", 0.0, 1.0, 0.0, "Voice override mode", "global", "bool"),
    "stereo_routing": ParamDef("stereo_routing", 0.0, 1.0, 0.0, "Stereo routing", "global"),
    "stereo_mode": ParamDef("stereo_mode", 0.0, 1.0, 0.0, "Stereo mode", "global", "enum"),
    "portamento_time": ParamDef("portamento_time", 0.0, 10.0, 0.0, "Portamento/glide time", "global"),
    "portamento_slope": ParamDef("portamento_slope", -10.0, 10.0, 0.0, "Portamento slope", "global"),
    "portamento_force": ParamDef("portamento_force", 0.0, 1.0, 0.0, "Force portamento (always glide)", "global", "bool"),
    "portamento_scale": ParamDef("portamento_scale", 0.0, 1.0, 0.0, "Portamento scale mode", "global", "bool"),
    "velocity_track": ParamDef("velocity_track", 0.0, 1.0, 0.5, "Velocity tracking amount", "global"),
    "volume": ParamDef("volume", 0.0, 1.0, 0.7, "Master volume", "global"),
    "oversampling": ParamDef("oversampling", 0.0, 3.0, 0.0, "Oversampling (1x/2x/4x/8x)", "global", "enum"),
    "pitch_wheel": ParamDef("pitch_wheel", -1.0, 1.0, 0.0, "Pitch wheel position", "global"),
    "mod_wheel": ParamDef("mod_wheel", 0.0, 1.0, 0.0, "Mod wheel position", "global"),
    "mpe_enabled": ParamDef("mpe_enabled", 0.0, 1.0, 0.0, "MPE mode enabled", "global", "bool"),
    "view_spectrogram": ParamDef("view_spectrogram", 0.0, 1.0, 0.0, "Show spectrogram view", "global", "bool"),
    "effect_chain_order": ParamDef("effect_chain_order", 0.0, 1e9, 0.0, "Effect chain ordering bitmask", "global"),
}

# ── Oscillator parameter templates (osc_1, osc_2, osc_3) ────────────

_OSC_TEMPLATE: dict[str, tuple] = {
    # suffix: (min, max, default, description, value_type)
    "on": (0.0, 1.0, 1.0, "Oscillator enabled", "bool"),
    "transpose": (-48.0, 48.0, 0.0, "Transpose in semitones", "int"),
    "transpose_quantize": (0.0, 1.0, 0.0, "Quantize transpose to semitones", "bool"),
    "tune": (-1.0, 1.0, 0.0, "Fine tune in cents", "float"),
    "pan": (-1.0, 1.0, 0.0, "Pan position", "float"),
    "level": (0.0, 1.0, 0.7, "Oscillator level", "float"),
    "midi_track": (0.0, 1.0, 1.0, "MIDI keyboard tracking", "bool"),
    "stack_style": (0.0, 10.0, 0.0, "Unison stack style", "enum"),
    "unison_detune": (0.0, 100.0, 2.2, "Unison detune amount", "float"),
    "unison_voices": (1.0, 16.0, 1.0, "Number of unison voices", "int"),
    "unison_blend": (0.0, 1.0, 0.0, "Unison blend", "float"),
    "detune_power": (0.0, 1.0, 0.5, "Detune power curve", "float"),
    "detune_range": (0.0, 48.0, 2.0, "Detune range in semitones", "float"),
    "smooth_interpolation": (0.0, 1.0, 0.0, "Smooth wavetable interpolation", "bool"),
    "spectral_unison": (1.0, 16.0, 1.0, "Spectral unison voices", "int"),
    "wave_frame": (0.0, 256.0, 0.0, "Wavetable frame position", "float"),
    "frame_spread": (0.0, 256.0, 0.0, "Frame spread across unison", "float"),
    "stereo_spread": (0.0, 1.0, 0.0, "Stereo spread of unison", "float"),
    "phase": (0.0, 1.0, 0.0, "Oscillator phase offset", "float"),
    "random_phase": (0.0, 1.0, 1.0, "Randomize phase on note on", "bool"),
    "distortion_type": (0.0, 12.0, 0.0, "Wavetable distortion type", "enum"),
    "distortion_amount": (0.0, 1.0, 0.0, "Wavetable distortion amount", "float"),
    "distortion_phase": (0.0, 1.0, 0.5, "Wavetable distortion phase", "float"),
    "distortion_spread": (0.0, 1.0, 0.0, "Distortion spread across unison", "float"),
    "spectral_morph_type": (0.0, 12.0, 0.0, "Spectral morph type", "enum"),
    "spectral_morph_amount": (0.0, 1.0, 0.0, "Spectral morph amount", "float"),
    "spectral_morph_spread": (0.0, 1.0, 0.0, "Spectral morph spread across unison", "float"),
    "destination": (0.0, 4.0, 0.0, "Output destination routing", "enum"),
    "view_2d": (0.0, 1.0, 0.0, "Show 2D wavetable view", "bool"),
}

# ── Filter parameter templates (filter_1, filter_2, filter_fx) ───────

_FILTER_TEMPLATE: dict[str, tuple] = {
    "on": (0.0, 1.0, 0.0, "Filter enabled", "bool"),
    "cutoff": (8.0, 136.0, 60.0, "Cutoff frequency (MIDI note)", "float"),
    "resonance": (0.0, 1.0, 0.2, "Resonance", "float"),
    "drive": (0.0, 1.0, 0.0, "Filter drive", "float"),
    "blend": (0.0, 2.0, 0.0, "Filter blend", "float"),
    "blend_transpose": (-48.0, 48.0, 0.0, "Blend transpose", "float"),
    "mix": (0.0, 1.0, 1.0, "Filter mix (dry/wet)", "float"),
    "style": (0.0, 13.0, 0.0, "Filter style", "enum"),
    "model": (0.0, 7.0, 0.0, "Filter model (analog/dirty/ladder/digital/diode/formant/comb/phase)", "enum"),
    "keytrack": (0.0, 1.0, 0.0, "Keyboard tracking amount", "float"),
    "formant_x": (0.0, 1.0, 0.5, "Formant X position", "float"),
    "formant_y": (0.0, 1.0, 0.5, "Formant Y position", "float"),
    "formant_transpose": (-12.0, 12.0, 0.0, "Formant transpose", "float"),
    "formant_resonance": (0.0, 1.0, 0.5, "Formant resonance", "float"),
    "formant_spread": (0.0, 1.0, 0.0, "Formant spread", "float"),
}

_FILTER_ROUTING: dict[str, tuple] = {
    "osc1_input": (0.0, 1.0, 0.0, "OSC1 input to this filter", "float"),
    "osc2_input": (0.0, 1.0, 0.0, "OSC2 input to this filter", "float"),
    "osc3_input": (0.0, 1.0, 0.0, "OSC3 input to this filter", "float"),
    "sample_input": (0.0, 1.0, 0.0, "Sample input to this filter", "float"),
    "filter_input": (0.0, 1.0, 0.0, "Other filter input to this filter", "float"),
}

# ── Envelope parameter templates (env_1 through env_6) ───────────────

_ENV_TEMPLATE: dict[str, tuple] = {
    "delay": (0.0, 4.0, 0.0, "Envelope delay time", "float"),
    "attack": (0.0, 4.0, 0.01, "Attack time", "float"),
    "hold": (0.0, 4.0, 0.0, "Hold time", "float"),
    "decay": (0.0, 4.0, 0.5, "Decay time", "float"),
    "sustain": (0.0, 1.0, 0.7, "Sustain level", "float"),
    "release": (0.0, 4.0, 0.3, "Release time", "float"),
    "attack_power": (-10.0, 10.0, 0.0, "Attack curve shape", "float"),
    "decay_power": (-10.0, 10.0, 0.0, "Decay curve shape", "float"),
    "release_power": (-10.0, 10.0, 0.0, "Release curve shape", "float"),
}

# ── LFO parameter templates (lfo_1 through lfo_8) ───────────────────

_LFO_TEMPLATE: dict[str, tuple] = {
    "phase": (0.0, 1.0, 0.0, "LFO phase offset", "float"),
    "frequency": (0.0, 20.0, 2.0, "LFO frequency in Hz", "float"),
    "sync": (0.0, 3.0, 0.0, "LFO sync mode", "enum"),
    "sync_type": (0.0, 3.0, 0.0, "LFO sync type", "enum"),
    "tempo": (0.0, 12.0, 7.0, "LFO tempo division", "enum"),
    "fade_time": (0.0, 8.0, 0.0, "LFO fade-in time", "float"),
    "smooth_mode": (0.0, 2.0, 0.0, "LFO smooth mode", "enum"),
    "smooth_time": (0.0, 1.0, 0.0, "LFO smooth time", "float"),
    "delay_time": (0.0, 4.0, 0.0, "LFO delay time", "float"),
    "stereo": (0.0, 1.0, 0.0, "LFO stereo phase offset", "float"),
    "keytrack_transpose": (-48.0, 48.0, 0.0, "LFO keytrack transpose", "float"),
    "keytrack_tune": (-1.0, 1.0, 0.0, "LFO keytrack tune", "float"),
}

# ── Random LFO templates (random_1 through random_4) ────────────────

_RANDOM_LFO_TEMPLATE: dict[str, tuple] = {
    "style": (0.0, 3.0, 0.0, "Random LFO style", "enum"),
    "frequency": (0.0, 20.0, 2.0, "Random LFO frequency", "float"),
    "sync": (0.0, 3.0, 0.0, "Random LFO sync mode", "enum"),
    "sync_type": (0.0, 3.0, 0.0, "Random LFO sync type", "enum"),
    "tempo": (0.0, 12.0, 7.0, "Random LFO tempo division", "enum"),
    "stereo": (0.0, 1.0, 0.0, "Random LFO stereo offset", "float"),
    "keytrack_transpose": (-48.0, 48.0, 0.0, "Random keytrack transpose", "float"),
    "keytrack_tune": (-1.0, 1.0, 0.0, "Random keytrack tune", "float"),
}

# ── Sub oscillator ───────────────────────────────────────────────────

SUB_PARAMS: dict[str, ParamDef] = {
    "sub_on": ParamDef("sub_on", 0.0, 1.0, 0.0, "Sub oscillator enabled", "sub", "bool"),
    "sub_direct_out": ParamDef("sub_direct_out", 0.0, 1.0, 0.0, "Sub direct output (bypass filters)", "sub", "bool"),
    "sub_transpose": ParamDef("sub_transpose", -48.0, 48.0, 0.0, "Sub transpose in semitones", "sub", "int"),
    "sub_transpose_quantize": ParamDef("sub_transpose_quantize", 0.0, 1.0, 0.0, "Sub quantize transpose", "sub", "bool"),
    "sub_tune": ParamDef("sub_tune", -1.0, 1.0, 0.0, "Sub fine tune", "sub"),
    "sub_level": ParamDef("sub_level", 0.0, 1.0, 0.7, "Sub oscillator level", "sub"),
    "sub_pan": ParamDef("sub_pan", -1.0, 1.0, 0.0, "Sub pan position", "sub"),
    "sub_waveform": ParamDef("sub_waveform", 0.0, 3.0, 0.0, "Sub waveform (sine/tri/saw/square)", "sub", "enum"),
}

# ── Sample player ────────────────────────────────────────────────────

SAMPLE_PARAMS: dict[str, ParamDef] = {
    "sample_on": ParamDef("sample_on", 0.0, 1.0, 0.0, "Sample player enabled", "sample", "bool"),
    "sample_random_phase": ParamDef("sample_random_phase", 0.0, 1.0, 0.0, "Sample random phase", "sample", "bool"),
    "sample_keytrack": ParamDef("sample_keytrack", 0.0, 1.0, 1.0, "Sample keyboard tracking", "bool"),
    "sample_loop": ParamDef("sample_loop", 0.0, 1.0, 0.0, "Sample loop", "sample", "bool"),
    "sample_bounce": ParamDef("sample_bounce", 0.0, 1.0, 0.0, "Sample bounce/pingpong", "sample", "bool"),
    "sample_transpose": ParamDef("sample_transpose", -48.0, 48.0, 0.0, "Sample transpose", "sample", "int"),
    "sample_transpose_quantize": ParamDef("sample_transpose_quantize", 0.0, 1.0, 0.0, "Sample quantize transpose", "sample", "bool"),
    "sample_tune": ParamDef("sample_tune", -1.0, 1.0, 0.0, "Sample fine tune", "sample"),
    "sample_level": ParamDef("sample_level", 0.0, 1.0, 0.7, "Sample level", "sample"),
    "sample_destination": ParamDef("sample_destination", 0.0, 4.0, 0.0, "Sample output destination", "sample", "enum"),
    "sample_pan": ParamDef("sample_pan", -1.0, 1.0, 0.0, "Sample pan position", "sample"),
}

# ── Effects ──────────────────────────────────────────────────────────

CHORUS_PARAMS: dict[str, ParamDef] = {
    "chorus_on": ParamDef("chorus_on", 0.0, 1.0, 0.0, "Chorus enabled", "chorus", "bool"),
    "chorus_dry_wet": ParamDef("chorus_dry_wet", 0.0, 1.0, 0.5, "Chorus dry/wet mix", "chorus"),
    "chorus_feedback": ParamDef("chorus_feedback", -1.0, 1.0, 0.0, "Chorus feedback", "chorus"),
    "chorus_cutoff": ParamDef("chorus_cutoff", 8.0, 136.0, 60.0, "Chorus filter cutoff", "chorus"),
    "chorus_spread": ParamDef("chorus_spread", 0.0, 1.0, 1.0, "Chorus stereo spread", "chorus"),
    "chorus_voices": ParamDef("chorus_voices", 1.0, 4.0, 2.0, "Chorus voices count", "chorus", "int"),
    "chorus_frequency": ParamDef("chorus_frequency", 0.0, 20.0, 2.0, "Chorus modulation frequency", "chorus"),
    "chorus_sync": ParamDef("chorus_sync", 0.0, 3.0, 0.0, "Chorus sync mode", "chorus", "enum"),
    "chorus_tempo": ParamDef("chorus_tempo", 0.0, 12.0, 7.0, "Chorus tempo division", "chorus", "enum"),
    "chorus_mod_depth": ParamDef("chorus_mod_depth", 0.0, 1.0, 0.5, "Chorus modulation depth", "chorus"),
    "chorus_delay_1": ParamDef("chorus_delay_1", -6.0, 6.0, -3.0, "Chorus delay 1", "chorus"),
    "chorus_delay_2": ParamDef("chorus_delay_2", -6.0, 6.0, 3.0, "Chorus delay 2", "chorus"),
}

DELAY_PARAMS: dict[str, ParamDef] = {
    "delay_on": ParamDef("delay_on", 0.0, 1.0, 0.0, "Delay enabled", "delay", "bool"),
    "delay_dry_wet": ParamDef("delay_dry_wet", 0.0, 1.0, 0.3, "Delay dry/wet mix", "delay"),
    "delay_feedback": ParamDef("delay_feedback", 0.0, 1.0, 0.3, "Delay feedback", "delay"),
    "delay_frequency": ParamDef("delay_frequency", 0.0, 20.0, 2.0, "Delay frequency", "delay"),
    "delay_aux_frequency": ParamDef("delay_aux_frequency", 0.0, 20.0, 2.0, "Delay aux frequency", "delay"),
    "delay_style": ParamDef("delay_style", 0.0, 3.0, 0.0, "Delay style (stereo/pingpong/mid-side)", "delay", "enum"),
    "delay_filter_cutoff": ParamDef("delay_filter_cutoff", 8.0, 136.0, 60.0, "Delay filter cutoff", "delay"),
    "delay_filter_spread": ParamDef("delay_filter_spread", 0.0, 1.0, 0.0, "Delay filter spread", "delay"),
    "delay_sync": ParamDef("delay_sync", 0.0, 3.0, 1.0, "Delay sync mode", "delay", "enum"),
    "delay_tempo": ParamDef("delay_tempo", 0.0, 12.0, 7.0, "Delay tempo division", "delay", "enum"),
    "delay_aux_sync": ParamDef("delay_aux_sync", 0.0, 3.0, 1.0, "Delay aux sync mode", "delay", "enum"),
    "delay_aux_tempo": ParamDef("delay_aux_tempo", 0.0, 12.0, 7.0, "Delay aux tempo division", "delay", "enum"),
}

DISTORTION_PARAMS: dict[str, ParamDef] = {
    "distortion_on": ParamDef("distortion_on", 0.0, 1.0, 0.0, "Distortion enabled", "distortion", "bool"),
    "distortion_type": ParamDef("distortion_type", 0.0, 12.0, 0.0, "Distortion type", "distortion", "enum"),
    "distortion_drive": ParamDef("distortion_drive", 0.0, 1.0, 0.3, "Distortion drive", "distortion"),
    "distortion_mix": ParamDef("distortion_mix", 0.0, 1.0, 0.5, "Distortion mix", "distortion"),
    "distortion_filter_order": ParamDef("distortion_filter_order", 0.0, 3.0, 0.0, "Distortion filter order", "distortion", "enum"),
    "distortion_filter_cutoff": ParamDef("distortion_filter_cutoff", 8.0, 136.0, 60.0, "Distortion filter cutoff", "distortion"),
    "distortion_filter_resonance": ParamDef("distortion_filter_resonance", 0.0, 1.0, 0.0, "Distortion filter resonance", "distortion"),
    "distortion_filter_blend": ParamDef("distortion_filter_blend", 0.0, 2.0, 0.0, "Distortion filter blend", "distortion"),
}

REVERB_PARAMS: dict[str, ParamDef] = {
    "reverb_on": ParamDef("reverb_on", 0.0, 1.0, 0.0, "Reverb enabled", "reverb", "bool"),
    "reverb_dry_wet": ParamDef("reverb_dry_wet", 0.0, 1.0, 0.3, "Reverb dry/wet mix", "reverb"),
    "reverb_decay_time": ParamDef("reverb_decay_time", 0.0, 1.0, 0.5, "Reverb decay time", "reverb"),
    "reverb_size": ParamDef("reverb_size", 0.0, 1.0, 0.5, "Reverb size", "reverb"),
    "reverb_delay": ParamDef("reverb_delay", 0.0, 0.3, 0.0, "Reverb pre-delay", "reverb"),
    "reverb_pre_low_cutoff": ParamDef("reverb_pre_low_cutoff", 8.0, 136.0, 20.0, "Reverb pre-EQ low cutoff", "reverb"),
    "reverb_pre_high_cutoff": ParamDef("reverb_pre_high_cutoff", 8.0, 136.0, 110.0, "Reverb pre-EQ high cutoff", "reverb"),
    "reverb_low_shelf_cutoff": ParamDef("reverb_low_shelf_cutoff", 8.0, 136.0, 30.0, "Reverb low shelf cutoff", "reverb"),
    "reverb_low_shelf_gain": ParamDef("reverb_low_shelf_gain", -6.0, 6.0, 0.0, "Reverb low shelf gain", "reverb"),
    "reverb_high_shelf_cutoff": ParamDef("reverb_high_shelf_cutoff", 8.0, 136.0, 100.0, "Reverb high shelf cutoff", "reverb"),
    "reverb_high_shelf_gain": ParamDef("reverb_high_shelf_gain", -6.0, 6.0, 0.0, "Reverb high shelf gain", "reverb"),
    "reverb_chorus_amount": ParamDef("reverb_chorus_amount", 0.0, 1.0, 0.0, "Reverb chorus amount", "reverb"),
    "reverb_chorus_frequency": ParamDef("reverb_chorus_frequency", 0.0, 20.0, 2.0, "Reverb chorus frequency", "reverb"),
}

PHASER_PARAMS: dict[str, ParamDef] = {
    "phaser_on": ParamDef("phaser_on", 0.0, 1.0, 0.0, "Phaser enabled", "phaser", "bool"),
    "phaser_dry_wet": ParamDef("phaser_dry_wet", 0.0, 1.0, 0.5, "Phaser dry/wet mix", "phaser"),
    "phaser_feedback": ParamDef("phaser_feedback", -1.0, 1.0, 0.0, "Phaser feedback", "phaser"),
    "phaser_frequency": ParamDef("phaser_frequency", 0.0, 20.0, 2.0, "Phaser modulation frequency", "phaser"),
    "phaser_sync": ParamDef("phaser_sync", 0.0, 3.0, 0.0, "Phaser sync mode", "phaser", "enum"),
    "phaser_tempo": ParamDef("phaser_tempo", 0.0, 12.0, 7.0, "Phaser tempo division", "phaser", "enum"),
    "phaser_center": ParamDef("phaser_center", 8.0, 136.0, 80.0, "Phaser center frequency", "phaser"),
    "phaser_blend": ParamDef("phaser_blend", 0.0, 2.0, 0.0, "Phaser blend", "phaser"),
    "phaser_mod_depth": ParamDef("phaser_mod_depth", 0.0, 48.0, 24.0, "Phaser modulation depth", "phaser"),
    "phaser_phase_offset": ParamDef("phaser_phase_offset", 0.0, 1.0, 0.333, "Phaser stereo phase offset", "phaser"),
}

FLANGER_PARAMS: dict[str, ParamDef] = {
    "flanger_on": ParamDef("flanger_on", 0.0, 1.0, 0.0, "Flanger enabled", "flanger", "bool"),
    "flanger_dry_wet": ParamDef("flanger_dry_wet", 0.0, 1.0, 0.5, "Flanger dry/wet mix", "flanger"),
    "flanger_feedback": ParamDef("flanger_feedback", -1.0, 1.0, 0.0, "Flanger feedback", "flanger"),
    "flanger_frequency": ParamDef("flanger_frequency", 0.0, 20.0, 2.0, "Flanger modulation frequency", "flanger"),
    "flanger_sync": ParamDef("flanger_sync", 0.0, 3.0, 0.0, "Flanger sync mode", "flanger", "enum"),
    "flanger_tempo": ParamDef("flanger_tempo", 0.0, 12.0, 7.0, "Flanger tempo division", "flanger", "enum"),
    "flanger_center": ParamDef("flanger_center", 8.0, 136.0, 40.0, "Flanger center frequency", "flanger"),
    "flanger_mod_depth": ParamDef("flanger_mod_depth", 0.0, 48.0, 12.0, "Flanger modulation depth", "flanger"),
    "flanger_phase_offset": ParamDef("flanger_phase_offset", 0.0, 1.0, 0.5, "Flanger stereo phase offset", "flanger"),
}

COMPRESSOR_PARAMS: dict[str, ParamDef] = {
    "compressor_on": ParamDef("compressor_on", 0.0, 1.0, 0.0, "Compressor enabled", "compressor", "bool"),
    "compressor_attack": ParamDef("compressor_attack", 0.0, 1.0, 0.2, "Compressor attack", "compressor"),
    "compressor_release": ParamDef("compressor_release", 0.0, 1.0, 0.3, "Compressor release", "compressor"),
    "compressor_mix": ParamDef("compressor_mix", 0.0, 1.0, 1.0, "Compressor mix", "compressor"),
    "compressor_enabled_bands": ParamDef("compressor_enabled_bands", 0.0, 7.0, 0.0, "Compressor enabled bands bitmask", "compressor", "int"),
    "compressor_low_gain": ParamDef("compressor_low_gain", -24.0, 24.0, 0.0, "Compressor low band gain", "compressor"),
    "compressor_band_gain": ParamDef("compressor_band_gain", -24.0, 24.0, 0.0, "Compressor mid band gain", "compressor"),
    "compressor_high_gain": ParamDef("compressor_high_gain", -24.0, 24.0, 0.0, "Compressor high band gain", "compressor"),
    "compressor_low_upper_threshold": ParamDef("compressor_low_upper_threshold", -80.0, 0.0, 0.0, "Compressor low upper threshold", "compressor"),
    "compressor_band_upper_threshold": ParamDef("compressor_band_upper_threshold", -80.0, 0.0, 0.0, "Compressor mid upper threshold", "compressor"),
    "compressor_high_upper_threshold": ParamDef("compressor_high_upper_threshold", -80.0, 0.0, 0.0, "Compressor high upper threshold", "compressor"),
    "compressor_low_lower_threshold": ParamDef("compressor_low_lower_threshold", -80.0, 0.0, -80.0, "Compressor low lower threshold", "compressor"),
    "compressor_band_lower_threshold": ParamDef("compressor_band_lower_threshold", -80.0, 0.0, -80.0, "Compressor mid lower threshold", "compressor"),
    "compressor_high_lower_threshold": ParamDef("compressor_high_lower_threshold", -80.0, 0.0, -80.0, "Compressor high lower threshold", "compressor"),
    "compressor_low_upper_ratio": ParamDef("compressor_low_upper_ratio", 0.0, 1.0, 1.0, "Compressor low upper ratio", "compressor"),
    "compressor_band_upper_ratio": ParamDef("compressor_band_upper_ratio", 0.0, 1.0, 1.0, "Compressor mid upper ratio", "compressor"),
    "compressor_high_upper_ratio": ParamDef("compressor_high_upper_ratio", 0.0, 1.0, 1.0, "Compressor high upper ratio", "compressor"),
    "compressor_low_lower_ratio": ParamDef("compressor_low_lower_ratio", 0.0, 1.0, 1.0, "Compressor low lower ratio", "compressor"),
    "compressor_band_lower_ratio": ParamDef("compressor_band_lower_ratio", 0.0, 1.0, 1.0, "Compressor mid lower ratio", "compressor"),
    "compressor_high_lower_ratio": ParamDef("compressor_high_lower_ratio", 0.0, 1.0, 1.0, "Compressor high lower ratio", "compressor"),
}

EQ_PARAMS: dict[str, ParamDef] = {
    "eq_on": ParamDef("eq_on", 0.0, 1.0, 0.0, "EQ enabled", "eq", "bool"),
    "eq_low_mode": ParamDef("eq_low_mode", 0.0, 3.0, 0.0, "EQ low band mode", "eq", "enum"),
    "eq_low_cutoff": ParamDef("eq_low_cutoff", 8.0, 136.0, 30.0, "EQ low band cutoff", "eq"),
    "eq_low_gain": ParamDef("eq_low_gain", -15.0, 15.0, 0.0, "EQ low band gain", "eq"),
    "eq_low_resonance": ParamDef("eq_low_resonance", 0.0, 1.0, 0.7, "EQ low band resonance", "eq"),
    "eq_band_mode": ParamDef("eq_band_mode", 0.0, 3.0, 0.0, "EQ mid band mode", "eq", "enum"),
    "eq_band_cutoff": ParamDef("eq_band_cutoff", 8.0, 136.0, 60.0, "EQ mid band cutoff", "eq"),
    "eq_band_gain": ParamDef("eq_band_gain", -15.0, 15.0, 0.0, "EQ mid band gain", "eq"),
    "eq_band_resonance": ParamDef("eq_band_resonance", 0.0, 1.0, 0.7, "EQ mid band resonance", "eq"),
    "eq_high_mode": ParamDef("eq_high_mode", 0.0, 3.0, 0.0, "EQ high band mode", "eq", "enum"),
    "eq_high_cutoff": ParamDef("eq_high_cutoff", 8.0, 136.0, 100.0, "EQ high band cutoff", "eq"),
    "eq_high_gain": ParamDef("eq_high_gain", -15.0, 15.0, 0.0, "EQ high band gain", "eq"),
    "eq_high_resonance": ParamDef("eq_high_resonance", 0.0, 1.0, 0.7, "EQ high band resonance", "eq"),
}

# ── Modulation slot template (modulation_1 through modulation_64) ────

_MOD_TEMPLATE: dict[str, tuple] = {
    "amount": (0.0, 1.0, 0.0, "Modulation amount", "float"),
    "power": (-10.0, 10.0, 0.0, "Modulation power curve", "float"),
    "bipolar": (0.0, 1.0, 0.0, "Bipolar modulation", "bool"),
    "stereo": (0.0, 1.0, 0.0, "Stereo modulation", "bool"),
    "bypass": (0.0, 1.0, 0.0, "Bypass modulation", "bool"),
}

# ── Modulation sources and destinations ──────────────────────────────

MODULATION_SOURCES = [
    "env_1", "env_2", "env_3", "env_4", "env_5", "env_6",
    "lfo_1", "lfo_2", "lfo_3", "lfo_4", "lfo_5", "lfo_6", "lfo_7", "lfo_8",
    "random_1", "random_2", "random_3", "random_4",
    "velocity", "aftertouch", "mod_wheel", "pitch_wheel", "note",
    "stereo", "random", "macro_control_1", "macro_control_2",
    "macro_control_3", "macro_control_4",
]

EFFECT_NAMES = [
    "chorus", "compressor", "delay", "distortion", "eq",
    "filter_fx", "flanger", "phaser", "reverb",
]

FILTER_MODEL_NAMES = {
    0: "analog", 1: "dirty", 2: "ladder", 3: "digital",
    4: "diode", 5: "formant", 6: "comb", 7: "phase",
}


def _expand_indexed(prefix: str, index: int, template: dict, group: str,
                    extra: dict = None) -> dict[str, ParamDef]:
    """Expand a parameter template into concrete indexed parameters."""
    result = {}
    name_prefix = f"{prefix}_{index}"
    combined = dict(template)
    if extra:
        combined.update(extra)
    for suffix, (mn, mx, dv, desc, vt) in combined.items():
        full_name = f"{name_prefix}_{suffix}"
        result[full_name] = ParamDef(full_name, mn, mx, dv, desc, group, vt)
    return result


def build_full_registry() -> dict[str, ParamDef]:
    """Build the complete parameter registry with all indexed parameters."""
    reg: dict[str, ParamDef] = {}

    # Global
    reg.update(GLOBAL_PARAMS)

    # Oscillators 1-3
    for i in range(1, 4):
        reg.update(_expand_indexed("osc", i, _OSC_TEMPLATE, f"osc_{i}"))

    # Filters 1-2 (with routing inputs)
    for i in range(1, 3):
        reg.update(_expand_indexed("filter", i, _FILTER_TEMPLATE, f"filter_{i}",
                                   extra=_FILTER_ROUTING))

    # Filter FX
    reg.update(_expand_indexed("filter", "fx", _FILTER_TEMPLATE, "filter_fx"))

    # Envelopes 1-6
    for i in range(1, 7):
        reg.update(_expand_indexed("env", i, _ENV_TEMPLATE, f"env_{i}"))

    # LFOs 1-8
    for i in range(1, 9):
        reg.update(_expand_indexed("lfo", i, _LFO_TEMPLATE, f"lfo_{i}"))

    # Random LFOs 1-4
    for i in range(1, 5):
        reg.update(_expand_indexed("random", i, _RANDOM_LFO_TEMPLATE, f"random_{i}"))

    # Sub oscillator
    reg.update(SUB_PARAMS)

    # Sample player
    reg.update(SAMPLE_PARAMS)

    # Effects
    reg.update(CHORUS_PARAMS)
    reg.update(DELAY_PARAMS)
    reg.update(DISTORTION_PARAMS)
    reg.update(REVERB_PARAMS)
    reg.update(PHASER_PARAMS)
    reg.update(FLANGER_PARAMS)
    reg.update(COMPRESSOR_PARAMS)
    reg.update(EQ_PARAMS)

    # Modulation slots 1-64
    for i in range(1, 65):
        reg.update(_expand_indexed("modulation", i, _MOD_TEMPLATE, f"modulation_{i}"))

    return reg


# Singleton registry instance
PARAM_REGISTRY: dict[str, ParamDef] = build_full_registry()


def get_param(name: str) -> Optional[ParamDef]:
    """Look up a parameter definition by name."""
    return PARAM_REGISTRY.get(name)


def validate_param_value(name: str, value: float) -> tuple[bool, str]:
    """Validate a parameter value against its definition.

    Returns:
        (is_valid, error_message) tuple.
    """
    pdef = get_param(name)
    if pdef is None:
        return False, f"Unknown parameter: {name}"
    if value < pdef.min_val or value > pdef.max_val:
        return False, (f"Value {value} out of range [{pdef.min_val}, {pdef.max_val}] "
                       f"for parameter {name}")
    return True, ""


def list_params_by_group(group: str) -> list[ParamDef]:
    """List all parameters in a given group."""
    return [p for p in PARAM_REGISTRY.values() if p.group == group]


def search_params(query: str) -> list[ParamDef]:
    """Search parameters by name substring."""
    q = query.lower()
    return [p for p in PARAM_REGISTRY.values() if q in p.name.lower() or q in p.description.lower()]


def get_groups() -> list[str]:
    """Get all unique parameter group names."""
    return sorted(set(p.group for p in PARAM_REGISTRY.values()))
