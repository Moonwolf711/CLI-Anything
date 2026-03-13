"""Serum 1 .fxp preset file reader/writer.

Binary format (reverse-engineered from real Serum 1 presets):

  CcnK       4 bytes   magic (VST FXP/FXB container)
  size       4 bytes   big-endian uint32, total size after this field
  FPCh       4 bytes   chunk type (single program with opaque chunk)
  version    4 bytes   big-endian uint32 (always 1)
  fxID       4 bytes   "XfsX" = Xfer Serum
  fxVersion  4 bytes   big-endian uint32 (always 1)
  numProgs   4 bytes   big-endian uint32 (always 1)
  prgName    28 bytes  null-padded ASCII program name
  chunkSize  4 bytes   big-endian uint32, size of compressed chunk
  chunk      variable  zlib-compressed float32[5176+] parameter blob

Total header = 60 bytes before chunk data.

Blob layout (5176 floats = 20704 bytes):

  [0 - 159]      Modulation matrix (16 slots x 10 floats each)
  [160 - 679]    LFO/envelope curve point data (260 pairs)
  [680 - 3351]   More curve data, wavetable metadata, padding
  [3352 - 3563]  SYNTH PARAMETERS (~212 controllable values)
  [3564 - 3573]  FX enable flags (binary) + additional FX params (continuous)
  [3574 - 3579]  Voicing params (poly count, pitch bend, glide rate)
  [3580+]        Routing, additional data, wavetable secondary region

This module exposes a virtual parameter index (0-based sequential) that
maps to actual blob offsets via PARAM_TO_BLOB.  The public API operates
on a list of SERUM_PARAM_COUNT floats (the virtual param array).

Virtual indices that have no blob mapping ("virtual-only") use PARAM_MAP
defaults and do not persist to the FXP file.  This avoids blob offset
conflicts where multiple parameters would otherwise corrupt each other.
"""

from __future__ import annotations

import base64
import struct
import zlib
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FXP_MAGIC = b"CcnK"
FXP_CHUNK_TYPE = b"FPCh"
SERUM_FX_ID = b"XfsX"
SERUM_PARAM_COUNT = 512  # Virtual param count exposed to callers
SERUM_BLOB_FLOATS = 5176  # Actual blob size in the FXP file
FXP_HEADER_SIZE = 60  # bytes before chunk data

# ---------------------------------------------------------------------------
# Init template blob (base64-encoded zlib-compressed 5176 floats)
# Extracted from a real Serum "Sub" init-like preset.
# ---------------------------------------------------------------------------

_INIT_TEMPLATE_B64 = (
    "eJztm39MVWUYx997EbhgQtLCQUuRBioZDG7hIM7z8CPhgigpy5RMurDkRwqJA5QWHcYqjH5grBJZ"
    "lmOlQVmOVZYrY9ikxJSxJuUaMNYwrYljpeHc7Zx7z7n3cDj3cuwPbPF8tmfve97n+z7ned/3vOfc"
    "c7bLmAyPTAOeZzZVixudQafOqFPnpVM3R6fOW6fOR6fOV6fOpFPnp1Pnr1M3V6fuNp26eTp1ATp1"
    "gTatdoIgCIIgCIIgCIIgCIIgCIIgCIIgCIIgCIIgCIIgCIIgCIIgCGJmMZvNyFiy+B8QtTFHmayo"
    "i/CoaL/JPjxo6Jkc60T4QZD71Z54Djfl9oH6/ymvVy1PEv2ne3s5V6sj/uGMYblNPBf+tXQTaLW5"
    "z9vBQCsPog2NjsBEbRSKVv21TbPuyCUbzOZOu0n52Oti+0Rtu127ryXEblPHzuP+lWn2490NJpjs"
    "l8fOg2sOHeNwtTM5B1Vsp88eR5ovIYcWcOnlOGHoMMYEnWp+ku19pH7K+Z40Z/Kxoz8PEZlBWteA"
    "Dnh7Xh3t/oJdBJUPZD/TXkOmmJ9bVCrH6XHMWj6dc6Qf2yyFSesh761p1sBeGplBvQaoutY9rC2v"
    "vFY1Yyj2qFKnjOkhBpP3Jze5n/485D0s7XGm2PfKe8iUfoapY5Hu8bzGvcHdnnTV5fulmKurro3o"
    "M2jEUB0ztU++38r3X608NPanp5ju6m7GOmkdnHM+RxVDHJtRMC/J5y2Yj2C+gpkE85N0MSll1q3l"
    "RVKRn/pQfm5JWXS1tcpNwgRB/H/IqSiylpUU7ohJSQsrrtwWS1t/diE+J8TfNeLzwSjVnU6jIYkZ"
    "65JYfZdQGrim1MXc7fUpXFO3lTMZ6zhL+B6uIfUA11NwhDPVd3GWtj6uoXuYOztyRfAbYGmQH1jC"
    "50NxXAg0pC6GQ+uWQU9BLFyoSABTfQosb86E7La1sLVzI7zcbYUP+0ugd2Q7/D6+C3yMdRDs/zxE"
    "Bu2G+NBXID18D2yIekOI1QI7E98W4h2AvVnvCTE/gKN5Hwlxj8BA6adC7C/gWs1XQvwuCG38FqKa"
    "v4PE1tOQ1dYHeR0/QmnnT1Bz7Bd4qXsY9p36Fdr7f4Mvz/8B349cgZ8v/QkXx/+Gies3hPMbMMDH"
    "C4P9vXFhgC9GBvlhdPBcjA+dh7AwENPD5+OayDtwfdSduDl6AW6JC8Gy+LuwKvFurIVF+ELqYnw1"
    "/R58MysC969Zgu+vW4aH19+Ln+Xdh8c3x+DJglg8s8WM50ofwMGyFThakYCXqx7EqzUc2moRfetT"
    "MPDFNFzQuBIXvZaBS5ozMeatVbiidTUmv5ODlra1+PDBXNzQ8Qg+8fGjWNy5EZ/+/DHceexx5I/n"
    "Y0O3FZtOFuLeU0/iu2eK8FB/CX5y7ik8en4bfjNYjj0j2/Hs6A4cuFSJQ5er8cL4Lhy7+gxeu/6s"
    "3Wj9Z/36D9lsg1S6SgVj0vHQDJdqbnUeY6rj2ZuHwfkyq/5WIxAmPFdZbmUB80zjjQjnu12Yi2l6"
    "OU/xn8CSXZiZk2FZtdpaWFEeFutW5/DHTeM3T+O/31MqODPf5TyVmu/xGvl5/O5wM2idV08u/wJe"
    "Tyyn/4eEIuc39472KE606eJP/hZPEAShj38AA8eTXg=="
)

# ---------------------------------------------------------------------------
# Complete Serum 1 Parameter Map
#
# Virtual Index -> (name, description, min, max, default)
#
# Virtual indices 0..511 map onto positions in the 5176-float blob
# via PARAM_TO_BLOB.  Callers only see the 512-element virtual array.
#
# Parameter groupings follow Serum's UI layout.
# ---------------------------------------------------------------------------

PARAM_MAP: dict[int, tuple[str, str, float, float, float]] = {
    # =======================================================================
    # Oscillator A  (virtual 0-19, blob 3352-3370)
    # =======================================================================
    0:   ("osc_a_enable",         "Oscillator A on/off",             0.0, 1.0, 1.0),
    1:   ("osc_a_volume",         "Oscillator A volume",             0.0, 1.0, 0.70),
    2:   ("osc_a_octave",         "Oscillator A octave (norm)",      0.0, 1.0, 0.75),
    3:   ("osc_a_pan",            "Oscillator A pan",                0.0, 1.0, 0.50),
    4:   ("osc_a_semi",           "Oscillator A semitone (norm)",    0.0, 1.0, 0.50),
    5:   ("osc_a_fine",           "Oscillator A fine detune (norm)", 0.0, 1.0, 0.50),
    6:   ("osc_a_wave_pos",       "Oscillator A wavetable position", 0.0, 1.0, 0.50),
    7:   ("osc_a_unison_detune",  "Oscillator A unison detune",     0.0, 1.0, 0.0),
    8:   ("osc_a_phase",          "Oscillator A phase",              0.0, 1.0, 0.50),
    9:   ("osc_a_rand_phase",     "Oscillator A random phase",       0.0, 1.0, 0.75),
    10:  ("osc_a_warp",           "Oscillator A warp amount",        0.0, 1.0, 0.0),
    11:  ("osc_a_blend",          "Oscillator A unison blend",       0.0, 1.0, 0.50),
    12:  ("osc_a_stereo_unison",  "Oscillator A stereo unison spread", 0.0, 1.0, 0.0),
    13:  ("osc_a_on",             "Oscillator A master enable [virtual-only]", 0.0, 1.0, 1.0),
    14:  ("osc_a_stereo_width",   "Oscillator A stereo width",       0.0, 1.0, 0.50),
    15:  ("osc_a_sub_level",      "Oscillator A sub osc level",      0.0, 1.0, 0.75),
    16:  ("osc_a_sub_pan",        "Oscillator A sub osc pan",        0.0, 1.0, 0.50),
    17:  ("osc_a_warp_mode",      "Oscillator A warp mode (norm)",   0.0, 1.0, 0.50),
    18:  ("osc_a_unison_voices",  "Oscillator A unison voices (norm)", 0.0, 1.0, 0.50),
    19:  ("osc_a_key_track",      "Oscillator A key tracking",       0.0, 1.0, 0.50),

    # =======================================================================
    # Oscillator B  (virtual 20-39, blob 3371-3389)
    # =======================================================================
    20:  ("osc_b_enable",         "Oscillator B on/off",             0.0, 1.0, 1.0),
    21:  ("osc_b_volume",         "Oscillator B volume",             0.0, 1.0, 0.0),
    22:  ("osc_b_octave",         "Oscillator B octave (norm)",      0.0, 1.0, 0.75),
    23:  ("osc_b_pan",            "Oscillator B pan",                0.0, 1.0, 0.50),
    24:  ("osc_b_semi",           "Oscillator B semitone (norm)",    0.0, 1.0, 0.50),
    25:  ("osc_b_fine",           "Oscillator B fine detune (norm)", 0.0, 1.0, 0.50),
    26:  ("osc_b_wave_pos",       "Oscillator B wavetable position", 0.0, 1.0, 0.50),
    27:  ("osc_b_unison_detune",  "Oscillator B unison detune",     0.0, 1.0, 0.0),
    28:  ("osc_b_phase",          "Oscillator B phase",              0.0, 1.0, 0.0),
    29:  ("osc_b_rand_phase",     "Oscillator B random phase",       0.0, 1.0, 0.5),
    30:  ("osc_b_warp",           "Oscillator B warp amount",        0.0, 1.0, 0.25),
    31:  ("osc_b_blend",          "Oscillator B unison blend",       0.0, 1.0, 0.50),
    32:  ("osc_b_stereo_unison",  "Oscillator B stereo unison [virtual-only]", 0.0, 1.0, 0.0),
    33:  ("osc_b_on",             "Oscillator B master enable [virtual-only]", 0.0, 1.0, 1.0),
    34:  ("osc_b_stereo_width",   "Oscillator B stereo width [virtual-only]",  0.0, 1.0, 0.50),
    35:  ("osc_b_sub_level",      "Oscillator B sub osc level [virtual-only]", 0.0, 1.0, 0.25),
    36:  ("osc_b_sub_pan",        "Oscillator B sub osc pan [virtual-only]",   0.0, 1.0, 0.50),
    37:  ("osc_b_warp_mode",      "Oscillator B warp mode [virtual-only]",     0.0, 1.0, 0.50),
    38:  ("osc_b_unison_voices",  "Oscillator B unison voices [virtual-only]", 0.0, 1.0, 0.50),
    39:  ("osc_b_key_track",      "Oscillator B key tracking [virtual-only]",  0.0, 1.0, 0.50),

    # =======================================================================
    # Sub Oscillator  (virtual 40-44, blob 3383-3387)
    # =======================================================================
    40:  ("sub_osc_enable",       "Sub oscillator on/off",           0.0, 1.0, 0.0),
    41:  ("sub_osc_level",        "Sub oscillator level",            0.0, 1.0, 0.0),
    42:  ("sub_osc_shape",        "Sub oscillator shape (norm)",     0.0, 1.0, 0.75),
    43:  ("sub_osc_octave",       "Sub oscillator octave (norm)",    0.0, 1.0, 0.50),
    44:  ("sub_osc_pan",          "Sub oscillator pan",              0.0, 1.0, 0.326),

    # =======================================================================
    # Noise Oscillator  (virtual 45-49, blob 3388-3392)
    # =======================================================================
    45:  ("noise_enable",         "Noise osc on/off",                0.0, 1.0, 0.0),
    46:  ("noise_level",          "Noise osc level",                 0.0, 1.0, 0.5),
    47:  ("noise_pan",            "Noise osc pan [virtual-only]",    0.0, 1.0, 0.50),
    48:  ("noise_pitch",          "Noise osc pitch [virtual-only]",  0.0, 1.0, 0.50),
    49:  ("noise_phase",          "Noise osc phase [virtual-only]",  0.0, 1.0, 0.50),

    # =======================================================================
    # Master / Global  (virtual 50-59, blob 3390-3399 approx)
    # =======================================================================
    50:  ("master_volume",        "Master output volume",            0.0, 1.0, 0.999),
    51:  ("master_tune",          "Master tuning (norm)",            0.0, 1.0, 0.409),
    52:  ("master_on",            "Master enable / polyphony flag",  0.0, 1.0, 1.0),
    53:  ("portamento_time",      "Portamento / glide time",         0.0, 1.0, 0.0),
    54:  ("portamento_mode",      "Portamento mode (norm)",          0.0, 1.0, 0.0),
    55:  ("mono_enable",          "Mono mode on/off",                0.0, 1.0, 0.0),
    56:  ("legato_enable",        "Legato mode [virtual-only]",      0.0, 1.0, 0.0),
    57:  ("pitch_bend_range",     "Pitch bend range [virtual-only]", 0.0, 1.0, 0.50),
    58:  ("velocity_sense",       "Velocity sensitivity [virtual-only]", 0.0, 1.0, 0.50),
    59:  ("global_chaos",         "Global chaos [virtual-only]",     0.0, 1.0, 0.0),

    # =======================================================================
    # Filter 1  (virtual 60-69, blob 3396-3405)
    # =======================================================================
    60:  ("filter1_enable",       "Filter 1 on/off",                 0.0, 1.0, 1.0),
    61:  ("filter1_cutoff",       "Filter 1 cutoff frequency",       0.0, 1.0, 0.011),
    62:  ("filter1_resonance",    "Filter 1 resonance",              0.0, 1.0, 0.50),
    63:  ("filter1_drive",        "Filter 1 drive",                  0.0, 1.0, 0.10),
    64:  ("filter1_type",         "Filter 1 type (norm)",            0.0, 1.0, 0.0),
    65:  ("filter1_fat",          "Filter 1 fat",                    0.0, 1.0, 0.0),
    66:  ("filter1_mix",          "Filter 1 dry/wet [virtual-only]", 0.0, 1.0, 1.0),
    67:  ("filter1_pan",          "Filter 1 pan",                    0.0, 1.0, 0.50),
    68:  ("filter1_key_track",    "Filter 1 key tracking",           0.0, 1.0, 0.11),
    69:  ("filter1_env_amount",   "Filter 1 env amount [virtual-only]", 0.0, 1.0, 0.50),

    # =======================================================================
    # Filter 2  (virtual 70-79, blob 3404-3413)
    # =======================================================================
    70:  ("filter2_enable",       "Filter 2 on/off",                 0.0, 1.0, 0.0),
    71:  ("filter2_cutoff",       "Filter 2 cutoff frequency",       0.0, 1.0, 0.50),
    72:  ("filter2_resonance",    "Filter 2 resonance",              0.0, 1.0, 1.0),
    73:  ("filter2_drive",        "Filter 2 drive",                  0.0, 1.0, 0.215),
    74:  ("filter2_type",         "Filter 2 type (norm)",            0.0, 1.0, 0.11),
    75:  ("filter2_fat",          "Filter 2 fat",                    0.0, 1.0, 0.0),
    76:  ("filter2_mix",          "Filter 2 dry/wet mix",            0.0, 1.0, 0.5),
    77:  ("filter2_pan",          "Filter 2 pan",                    0.0, 1.0, 1.0),
    78:  ("filter2_key_track",    "Filter 2 key tracking",           0.0, 1.0, 0.215),
    79:  ("filter2_env_amount",   "Filter 2 envelope amount",        0.0, 1.0, 0.50),

    # =======================================================================
    # Envelope 1 - Amp  (virtual 80-87, blob 3413-3420)
    # =======================================================================
    80:  ("env1_attack",          "Env 1 attack time",               0.0, 1.0, 0.50),
    81:  ("env1_hold",            "Env 1 hold time",                 0.0, 1.0, 0.50),
    82:  ("env1_decay",           "Env 1 decay time",                0.0, 1.0, 0.50),
    83:  ("env1_sustain",         "Env 1 sustain level",             0.0, 1.0, 0.0),
    84:  ("env1_release",         "Env 1 release time",              0.0, 1.0, 0.5),
    85:  ("env1_attack_curve",    "Env 1 attack curve shape",        0.0, 1.0, 0.0),
    86:  ("env1_decay_curve",     "Env 1 decay curve shape",         0.0, 1.0, 0.0),
    87:  ("env1_release_curve",   "Env 1 release curve [virtual-only]", 0.0, 1.0, 0.0),

    # =======================================================================
    # Envelope 2 - Filter  (virtual 88-98, blob 3421-3431)
    # =======================================================================
    88:  ("env2_attack",          "Env 2 attack time",               0.0, 1.0, 0.251),
    89:  ("env2_hold",            "Env 2 hold time",                 0.0, 1.0, 0.251),
    90:  ("env2_decay",           "Env 2 decay time",                0.0, 1.0, 0.445),
    91:  ("env2_sustain",         "Env 2 sustain level",             0.0, 1.0, 0.666),
    92:  ("env2_release",         "Env 2 release time",              0.0, 1.0, 0.666),
    93:  ("env2_attack_curve",    "Env 2 attack curve shape",        0.0, 1.0, 0.50),
    94:  ("env2_decay_curve",     "Env 2 decay curve shape",         0.0, 1.0, 0.666),
    95:  ("env2_release_curve",   "Env 2 release curve shape",       0.0, 1.0, 0.666),
    96:  ("env2_vel_track",       "Env 2 velocity tracking",         0.0, 1.0, 0.50),
    97:  ("env2_sustain_curve",   "Env 2 sustain curve",             0.0, 1.0, 0.666),
    98:  ("env2_loop_mode",       "Env 2 loop mode",                 0.0, 1.0, 0.666),

    # =======================================================================
    # Envelope 3  (virtual 99-110, blob 3432-3443)
    # =======================================================================
    99:  ("env3_delay",           "Env 3 delay time",                0.0, 1.0, 0.50),
    100: ("env3_attack",          "Env 3 attack time",               0.0, 1.0, 0.20),
    101: ("env3_hold",            "Env 3 hold time",                 0.0, 1.0, 0.35),
    102: ("env3_decay",           "Env 3 decay time",                0.0, 1.0, 0.35),
    103: ("env3_sustain",         "Env 3 sustain level",             0.0, 1.0, 0.0),
    104: ("env3_release",         "Env 3 release time",              0.0, 1.0, 0.25),
    105: ("env3_attack_curve",    "Env 3 attack curve shape",        0.0, 1.0, 0.35),
    106: ("env3_decay_curve",     "Env 3 decay curve shape",         0.0, 1.0, 0.20),
    107: ("env3_release_curve",   "Env 3 release curve shape",       0.0, 1.0, 0.333),
    108: ("env3_vel_track",       "Env 3 velocity tracking",         0.0, 1.0, 0.666),
    109: ("env3_sustain_curve",   "Env 3 sustain curve",             0.0, 1.0, 0.60),
    110: ("env3_loop_mode",       "Env 3 loop mode",                 0.0, 1.0, 0.60),

    # =======================================================================
    # Envelope 4  (virtual 111-119, blob ~3444-3452 -- shared region with LFO1)
    # NOTE: Serum has env4 but it overlaps the LFO region in some firmwares.
    # These offsets are estimated.
    # =======================================================================
    111: ("env4_attack",          "Env 4 attack [virtual-only]",     0.0, 1.0, 0.20),
    112: ("env4_hold",            "Env 4 hold [virtual-only]",       0.0, 1.0, 0.35),
    113: ("env4_decay",           "Env 4 decay [virtual-only]",      0.0, 1.0, 0.35),
    114: ("env4_sustain",         "Env 4 sustain [virtual-only]",    0.0, 1.0, 0.50),
    115: ("env4_release",         "Env 4 release [virtual-only]",    0.0, 1.0, 0.25),
    116: ("env4_attack_curve",    "Env 4 attack curve [virtual-only]", 0.0, 1.0, 0.50),
    117: ("env4_decay_curve",     "Env 4 decay curve [virtual-only]",  0.0, 1.0, 0.20),
    118: ("env4_release_curve",   "Env 4 release curve [virtual-only]", 0.0, 1.0, 0.333),

    # =======================================================================
    # LFO 1  (virtual 120-129, blob 3444-3453)
    # =======================================================================
    120: ("lfo1_enable",          "LFO 1 on/off",                    0.0, 1.0, 1.0),
    121: ("lfo1_rate",            "LFO 1 rate",                      0.0, 1.0, 0.50),
    122: ("lfo1_phase",           "LFO 1 phase offset",              0.0, 1.0, 0.50),
    123: ("lfo1_smooth",          "LFO 1 smoothing",                 0.0, 1.0, 0.0),
    124: ("lfo1_delay",           "LFO 1 delay onset",               0.0, 1.0, 0.0),
    125: ("lfo1_depth",           "LFO 1 depth / amount",            0.0, 1.0, 0.763),
    126: ("lfo1_rise",            "LFO 1 rise / fade-in",            0.0, 1.0, 0.0),
    127: ("lfo1_mode",            "LFO 1 mode (norm)",               0.0, 1.0, 0.133),
    128: ("lfo1_stereo",          "LFO 1 stereo offset",             0.0, 1.0, 0.50),
    129: ("lfo1_retrigger",       "LFO 1 retrigger mode",            0.0, 1.0, 0.50),

    # =======================================================================
    # LFO 2  (virtual 130-139, blob 3454-3463)
    # =======================================================================
    130: ("lfo2_enable",          "LFO 2 on/off",                    0.0, 1.0, 1.0),
    131: ("lfo2_rate",            "LFO 2 rate",                      0.0, 1.0, 0.25),
    132: ("lfo2_phase",           "LFO 2 phase offset",              0.0, 1.0, 0.50),
    133: ("lfo2_smooth",          "LFO 2 smoothing",                 0.0, 1.0, 0.50),
    134: ("lfo2_delay",           "LFO 2 delay onset",               0.0, 1.0, 0.0),
    135: ("lfo2_depth",           "LFO 2 depth / amount",            0.0, 1.0, 1.0),
    136: ("lfo2_rise",            "LFO 2 rise / fade-in",            0.0, 1.0, 0.25),
    137: ("lfo2_mode",            "LFO 2 mode (norm)",               0.0, 1.0, 0.0),
    138: ("lfo2_stereo",          "LFO 2 stereo offset",             0.0, 1.0, 0.0),
    139: ("lfo2_retrigger",       "LFO 2 retrigger mode",            0.0, 1.0, 1.0),

    # =======================================================================
    # LFO 3  (virtual 140-147, blob 3464-3471)
    # =======================================================================
    140: ("lfo3_enable",          "LFO 3 on/off",                    0.0, 1.0, 0.5),
    141: ("lfo3_rate",            "LFO 3 rate",                      0.0, 1.0, 0.50),
    142: ("lfo3_phase",           "LFO 3 phase offset",              0.0, 1.0, 0.50),
    143: ("lfo3_depth",           "LFO 3 depth / amount",            0.0, 1.0, 0.80),
    144: ("lfo3_smooth",          "LFO 3 smoothing",                 0.0, 1.0, 0.50),
    145: ("lfo3_mode",            "LFO 3 mode (norm)",               0.0, 1.0, 0.50),
    146: ("lfo3_delay",           "LFO 3 delay onset",               0.0, 1.0, 0.0),
    147: ("lfo3_rise",            "LFO 3 rise / fade-in",            0.0, 1.0, 0.25),

    # =======================================================================
    # LFO 4  (virtual 148-155, blob 3472-3479)
    # =======================================================================
    148: ("lfo4_enable",          "LFO 4 on/off",                    0.0, 1.0, 0.0),
    149: ("lfo4_rate",            "LFO 4 rate",                      0.0, 1.0, 0.10),
    150: ("lfo4_phase",           "LFO 4 phase offset",              0.0, 1.0, 0.50),
    151: ("lfo4_depth",           "LFO 4 depth / amount",            0.0, 1.0, 0.30),
    152: ("lfo4_smooth",          "LFO 4 smoothing",                 0.0, 1.0, 0.50),
    153: ("lfo4_mode",            "LFO 4 mode (norm)",               0.0, 1.0, 0.80),
    154: ("lfo4_on",              "LFO 4 master on",                 0.0, 1.0, 1.0),
    155: ("lfo4_stereo",          "LFO 4 stereo offset",             0.0, 1.0, 1.0),

    # =======================================================================
    # FX: Hyper / Dimension  (virtual 160-164, blob 3480-3484)
    # =======================================================================
    160: ("fx_hyper_enable",      "Hyper / Dimension on/off",         0.0, 1.0, 0.0),
    161: ("fx_hyper_rate",        "Hyper rate",                       0.0, 1.0, 0.625),
    162: ("fx_hyper_size",        "Hyper size / depth",               0.0, 1.0, 0.625),
    163: ("fx_hyper_detune",      "Hyper detune",                     0.0, 1.0, 0.0),
    164: ("fx_hyper_mix",         "Hyper dry/wet mix",                0.0, 1.0, 0.40),

    # =======================================================================
    # FX: Distortion  (virtual 165-169, blob 3485-3489)
    # =======================================================================
    165: ("fx_dist_enable",       "Distortion on/off",                0.0, 1.0, 0.0),
    166: ("fx_dist_drive",        "Distortion drive",                 0.0, 1.0, 0.50),
    167: ("fx_dist_mix",          "Distortion dry/wet mix",           0.0, 1.0, 0.50),
    168: ("fx_dist_type",         "Distortion type (norm)",           0.0, 1.0, 0.50),
    169: ("fx_dist_post_filter",  "Distortion post-filter",           0.0, 1.0, 0.0),

    # =======================================================================
    # FX: Flanger  (virtual 170-174, blob 3488-3492)
    # =======================================================================
    170: ("fx_flanger_enable",    "Flanger on/off",                   0.0, 1.0, 0.0),
    171: ("fx_flanger_rate",      "Flanger rate",                     0.0, 1.0, 0.75),
    172: ("fx_flanger_depth",     "Flanger depth",                    0.0, 1.0, 0.30),
    173: ("fx_flanger_feedback",  "Flanger feedback",                 0.0, 1.0, 0.30),
    174: ("fx_flanger_mix",       "Flanger dry/wet mix",              0.0, 1.0, 0.0),

    # =======================================================================
    # FX: Phaser  (virtual 175-179, blob 3492-3496)
    # =======================================================================
    175: ("fx_phaser_enable",     "Phaser on/off",                    0.0, 1.0, 0.0),
    176: ("fx_phaser_rate",       "Phaser rate",                      0.0, 1.0, 0.0),
    177: ("fx_phaser_depth",      "Phaser depth",                     0.0, 1.0, 0.50),
    178: ("fx_phaser_feedback",   "Phaser feedback",                  0.0, 1.0, 0.0),
    179: ("fx_phaser_mix",        "Phaser dry/wet mix",               0.0, 1.0, 1.0),

    # =======================================================================
    # FX: Chorus  (virtual 180-184, blob 3497-3501)
    # =======================================================================
    180: ("fx_chorus_enable",     "Chorus on/off",                    0.0, 1.0, 1.0),
    181: ("fx_chorus_rate",       "Chorus rate",                      0.0, 1.0, 0.0),
    182: ("fx_chorus_depth",      "Chorus depth",                     0.0, 1.0, 0.0),
    183: ("fx_chorus_feedback",   "Chorus feedback",                  0.0, 1.0, 0.50),
    184: ("fx_chorus_mix",        "Chorus dry/wet mix",               0.0, 1.0, 0.0),

    # =======================================================================
    # FX: Delay  (virtual 185-189, blob 3500-3504)
    # =======================================================================
    185: ("fx_delay_enable",      "Delay on/off",                     0.0, 1.0, 0.0),
    186: ("fx_delay_time",        "Delay time",                       0.0, 1.0, 0.40),
    187: ("fx_delay_feedback",    "Delay feedback",                   0.0, 1.0, 0.25),
    188: ("fx_delay_mix",         "Delay dry/wet mix",                0.0, 1.0, 0.571),
    189: ("fx_delay_ping_pong",   "Delay ping-pong mode",             0.0, 1.0, 0.0),

    # =======================================================================
    # FX: Compressor  (virtual 190-194, blob 3504-3508)
    # =======================================================================
    190: ("fx_comp_enable",       "Compressor on/off",                0.0, 1.0, 1.0),
    191: ("fx_comp_threshold",    "Compressor threshold",             0.0, 1.0, 0.50),
    192: ("fx_comp_ratio",        "Compressor ratio (norm)",          0.0, 1.0, 0.0),
    193: ("fx_comp_attack",       "Compressor attack time",           0.0, 1.0, 0.0),
    194: ("fx_comp_mix",          "Compressor mix / on flag",         0.0, 1.0, 1.0),

    # =======================================================================
    # FX: Multiband Compressor  (virtual 195-199, blob 3507-3511)
    # =======================================================================
    195: ("fx_multicomp_enable",  "Multiband comp on/off [virtual-only]", 0.0, 1.0, 0.0),
    196: ("fx_multicomp_low",     "Multiband comp low band",          0.0, 1.0, 0.0),
    197: ("fx_multicomp_mid",     "Multiband comp mid band",          0.0, 1.0, 0.0),
    198: ("fx_multicomp_high",    "Multiband comp high [virtual-only]", 0.0, 1.0, 0.0),
    199: ("fx_multicomp_mix",     "Multiband comp mix [virtual-only]",  0.0, 1.0, 0.50),

    # =======================================================================
    # FX: EQ  (virtual 200-204, blob 3509-3513)
    # =======================================================================
    200: ("fx_eq_enable",         "EQ on/off",                        0.0, 1.0, 0.0),
    201: ("fx_eq_low_gain",       "EQ low gain [virtual-only]",       0.0, 1.0, 0.50),
    202: ("fx_eq_mid_gain",       "EQ mid gain",                      0.0, 1.0, 0.0),
    203: ("fx_eq_high_gain",      "EQ high gain",                     0.0, 1.0, 0.0),
    204: ("fx_eq_mid_freq",       "EQ mid frequency [virtual-only]",  0.0, 1.0, 0.50),

    # =======================================================================
    # FX: Reverb  (virtual 205-209, blob 3510-3514)
    # =======================================================================
    205: ("fx_reverb_enable",     "Reverb on/off",                    0.0, 1.0, 0.0),
    206: ("fx_reverb_size",       "Reverb room size",                 0.0, 1.0, 0.0),
    207: ("fx_reverb_decay",      "Reverb decay time",                0.0, 1.0, 0.0),
    208: ("fx_reverb_mix",        "Reverb dry/wet mix",               0.0, 1.0, 0.0),
    209: ("fx_reverb_damping",    "Reverb damping / HF cut",          0.0, 1.0, 0.0),

    # =======================================================================
    # FX: Filter FX  (virtual 210-214, blob 3513-3517)
    # =======================================================================
    210: ("fx_filter_enable",     "FX filter on/off [virtual-only]",  0.0, 1.0, 0.0),
    211: ("fx_filter_cutoff",     "FX filter cutoff [virtual-only]",  0.0, 1.0, 0.50),
    212: ("fx_filter_resonance",  "FX filter resonance",              0.0, 1.0, 0.0),
    213: ("fx_filter_type",       "FX filter type (norm)",            0.0, 1.0, 1.0),
    214: ("fx_filter_mix",        "FX filter dry/wet mix",            0.0, 1.0, 1.0),

    # =======================================================================
    # FX Routing / Chain Config  (virtual 215-224, blob 3518-3527)
    # =======================================================================
    215: ("fx_chain_order_1",     "FX chain slot 1 assignment",       0.0, 1.0, 0.542),
    216: ("fx_chain_order_2",     "FX chain slot 2 assignment",       0.0, 1.0, 0.458),
    217: ("fx_chain_order_3",     "FX chain slot 3 assignment",       0.0, 1.0, 0.0),
    218: ("fx_chain_order_4",     "FX chain slot 4 assignment",       0.0, 1.0, 0.0),
    219: ("fx_chain_order_5",     "FX chain slot 5 assignment",       0.0, 1.0, 0.0),
    220: ("fx_chain_order_6",     "FX chain slot 6 assignment",       0.0, 1.0, 0.25),
    221: ("fx_chain_order_7",     "FX chain slot 7 assignment",       0.0, 1.0, 1.0),
    222: ("fx_chain_order_8",     "FX chain slot 8 assignment",       0.0, 1.0, 1.0),
    223: ("fx_chain_order_9",     "FX chain slot 9 assignment",       0.0, 1.0, 0.5),
    224: ("fx_chain_order_10",    "FX chain slot 10 assignment",      0.0, 1.0, 0.5),

    # =======================================================================
    # Macros  (virtual 225-228)
    # =======================================================================
    225: ("macro_1",              "Macro 1 value",                    0.0, 1.0, 0.5),
    226: ("macro_2",              "Macro 2 value",                    0.0, 1.0, 0.5),
    227: ("macro_3",              "Macro 3 value",                    0.0, 1.0, 0.0),
    228: ("macro_4",              "Macro 4 value",                    0.0, 1.0, 0.0),

    # =======================================================================
    # Voicing  (virtual 229-236)
    # =======================================================================
    229: ("voice_poly_count",     "Polyphony voices",                 0.0, 1.0, 0.50),
    230: ("voice_stack_mode",     "Voice stacking [virtual-only]",    0.0, 1.0, 0.0),
    231: ("voice_stack_detune",   "Voice stack detune [virtual-only]", 0.0, 1.0, 0.0),
    232: ("voice_stack_voices",   "Voice stack count [virtual-only]", 0.0, 1.0, 0.0),
    233: ("voice_bend_range_up",  "Pitch bend up range",              0.0, 1.0, 0.50),
    234: ("voice_bend_range_dn",  "Pitch bend down range",            0.0, 1.0, 0.0),
    235: ("voice_glide_mode",     "Glide mode [virtual-only]",        0.0, 1.0, 0.0),
    236: ("voice_glide_rate",     "Glide rate",                       0.0, 1.0, 0.0),

    # =======================================================================
    # Modulation Matrix (virtual 237-268, 16 slots x 2: amount + destination)
    # blob 3532-3563 region
    # =======================================================================
    237: ("mod_1_amount",         "Mod slot 1 amount",                0.0, 1.0, 0.5),
    238: ("mod_1_dest",           "Mod slot 1 destination (norm)",    0.0, 1.0, 1.0),
    239: ("mod_2_amount",         "Mod slot 2 amount",                0.0, 1.0, 0.5),
    240: ("mod_2_dest",           "Mod slot 2 destination (norm)",    0.0, 1.0, 1.0),
    241: ("mod_3_amount",         "Mod slot 3 amount",                0.0, 1.0, 0.5),
    242: ("mod_3_dest",           "Mod slot 3 destination (norm)",    0.0, 1.0, 1.0),
    243: ("mod_4_amount",         "Mod slot 4 amount",                0.0, 1.0, 0.5),
    244: ("mod_4_dest",           "Mod slot 4 destination (norm)",    0.0, 1.0, 1.0),
    245: ("mod_5_amount",         "Mod slot 5 amount",                0.0, 1.0, 0.5),
    246: ("mod_5_dest",           "Mod slot 5 destination (norm)",    0.0, 1.0, 1.0),
    247: ("mod_6_amount",         "Mod slot 6 amount",                0.0, 1.0, 0.5),
    248: ("mod_6_dest",           "Mod slot 6 destination (norm)",    0.0, 1.0, 1.0),
    249: ("mod_7_amount",         "Mod slot 7 amount",                0.0, 1.0, 0.5),
    250: ("mod_7_dest",           "Mod slot 7 destination (norm)",    0.0, 1.0, 1.0),
    251: ("mod_8_amount",         "Mod slot 8 amount",                0.0, 1.0, 0.5),
    252: ("mod_8_dest",           "Mod slot 8 destination (norm)",    0.0, 1.0, 1.0),
    253: ("mod_9_amount",         "Mod slot 9 amount",                0.0, 1.0, 0.5),
    254: ("mod_9_dest",           "Mod slot 9 destination (norm)",    0.0, 1.0, 1.0),
    255: ("mod_10_amount",        "Mod slot 10 amount",               0.0, 1.0, 0.5),
    256: ("mod_10_dest",          "Mod slot 10 destination (norm)",   0.0, 1.0, 1.0),
    257: ("mod_11_amount",        "Mod slot 11 amount",               0.0, 1.0, 0.5),
    258: ("mod_11_dest",          "Mod slot 11 destination (norm)",   0.0, 1.0, 1.0),
    259: ("mod_12_amount",        "Mod slot 12 amount",               0.0, 1.0, 0.5),
    260: ("mod_12_dest",          "Mod slot 12 destination (norm)",   0.0, 1.0, 1.0),
    261: ("mod_13_amount",        "Mod slot 13 amount",               0.0, 1.0, 0.5),
    262: ("mod_13_dest",          "Mod slot 13 destination (norm)",   0.0, 1.0, 1.0),
    263: ("mod_14_amount",        "Mod slot 14 amount",               0.0, 1.0, 0.5),
    264: ("mod_14_dest",          "Mod slot 14 destination (norm)",   0.0, 1.0, 1.0),
    265: ("mod_15_amount",        "Mod slot 15 amount",               0.0, 1.0, 0.5),
    266: ("mod_15_dest",          "Mod slot 15 destination (norm)",   0.0, 1.0, 1.0),
    267: ("mod_16_amount",        "Mod slot 16 amount",               0.0, 1.0, 0.5),
    268: ("mod_16_dest",          "Mod slot 16 destination (norm)",   0.0, 1.0, 1.0),
}

# ---------------------------------------------------------------------------
# Blob offset mapping:  virtual index -> index in the 5176-float blob
#
# This is the core mapping that translates between the 512-element virtual
# param array (what callers see) and the actual position inside the
# zlib-compressed blob stored in the FXP file.
#
# Each blob offset appears at most ONCE to prevent cross-contamination.
# Parameters not listed here are "virtual-only" and use PARAM_MAP defaults.
# ---------------------------------------------------------------------------

PARAM_TO_BLOB: dict[int, int] = {
    # -- Oscillator A  (blob 3352-3370) --
    0:   3364,   # osc_a_enable  (osc_a_on in blob)
    1:   3352,   # osc_a_volume
    2:   3353,   # osc_a_octave
    3:   3354,   # osc_a_pan
    4:   3355,   # osc_a_semi
    5:   3356,   # osc_a_fine
    6:   3357,   # osc_a_wave_pos
    7:   3358,   # osc_a_unison_detune
    8:   3359,   # osc_a_phase
    9:   3360,   # osc_a_rand_phase
    10:  3361,   # osc_a_warp
    11:  3362,   # osc_a_blend
    12:  3363,   # osc_a_stereo_unison
    # 13 = osc_a_on -> virtual-only (alias of 0)
    14:  3365,   # osc_a_stereo_width
    15:  3366,   # osc_a_sub_level
    16:  3367,   # osc_a_sub_pan
    17:  3368,   # osc_a_warp_mode
    18:  3369,   # osc_a_unison_voices
    19:  3370,   # osc_a_key_track

    # -- Oscillator B  (blob 3371-3382, only 12 unique offsets) --
    20:  3377,   # osc_b_enable  (on at blob[3377])
    21:  3371,   # osc_b_volume
    22:  3373,   # osc_b_octave
    23:  3380,   # osc_b_pan
    24:  3375,   # osc_b_semi
    25:  3382,   # osc_b_fine
    26:  3372,   # osc_b_wave_pos
    27:  3374,   # osc_b_unison_detune
    28:  3376,   # osc_b_phase
    29:  3378,   # osc_b_rand_phase
    30:  3379,   # osc_b_warp
    31:  3381,   # osc_b_blend
    # 32-39 = virtual-only (not enough unique blob offsets)

    # -- Sub Oscillator  (blob 3383-3387) --
    40:  3383,   # sub_osc_enable
    41:  3384,   # sub_osc_level
    42:  3385,   # sub_osc_shape
    43:  3386,   # sub_osc_octave
    44:  3387,   # sub_osc_pan

    # -- Noise Oscillator  (blob 3388-3389) --
    45:  3388,   # noise_enable
    46:  3389,   # noise_level
    # 47-49 = virtual-only (overlap with master region)

    # -- Master / Global  (blob 3390-3395) --
    50:  3390,   # master_volume
    51:  3391,   # master_tune
    52:  3392,   # master_on
    53:  3393,   # portamento_time
    54:  3394,   # portamento_mode
    55:  3395,   # mono_enable
    # 56-59 = virtual-only

    # -- Filter 1  (blob 3396-3403) --
    60:  3401,   # filter1_enable  (on/mix flag)
    61:  3396,   # filter1_cutoff
    62:  3397,   # filter1_resonance
    63:  3398,   # filter1_drive
    64:  3399,   # filter1_type
    65:  3400,   # filter1_fat
    # 66 = virtual-only (filter1_mix conflicts with 60)
    67:  3402,   # filter1_pan
    68:  3403,   # filter1_key_track
    # 69 = virtual-only (env_amount conflicts with filter2)

    # -- Filter 2  (blob 3404-3413) --
    70:  3404,   # filter2_enable
    71:  3405,   # filter2_cutoff
    72:  3406,   # filter2_resonance
    73:  3407,   # filter2_drive
    74:  3408,   # filter2_type
    75:  3409,   # filter2_fat
    76:  3410,   # filter2_mix
    77:  3411,   # filter2_pan
    78:  3412,   # filter2_key_track
    79:  3413,   # filter2_env_amount

    # -- Envelope 1 - Amp  (blob 3414-3420) --
    80:  3414,   # env1_attack
    81:  3415,   # env1_hold
    82:  3416,   # env1_decay
    83:  3417,   # env1_sustain
    84:  3418,   # env1_release
    85:  3419,   # env1_attack_curve
    86:  3420,   # env1_decay_curve
    # 87 = virtual-only (no room, 3421 is env2)

    # -- Envelope 2 - Filter  (blob 3421-3431) --
    88:  3421,   # env2_attack
    89:  3422,   # env2_hold
    90:  3423,   # env2_decay
    91:  3424,   # env2_sustain
    92:  3425,   # env2_release
    93:  3426,   # env2_attack_curve
    94:  3427,   # env2_decay_curve
    95:  3428,   # env2_release_curve
    96:  3429,   # env2_vel_track
    97:  3430,   # env2_sustain_curve
    98:  3431,   # env2_loop_mode

    # -- Envelope 3  (blob 3432-3443) --
    99:  3432,   # env3_delay
    100: 3433,   # env3_attack
    101: 3434,   # env3_hold
    102: 3435,   # env3_decay
    103: 3436,   # env3_sustain
    104: 3437,   # env3_release
    105: 3438,   # env3_attack_curve
    106: 3439,   # env3_decay_curve
    107: 3440,   # env3_release_curve
    108: 3441,   # env3_vel_track
    109: 3442,   # env3_sustain_curve
    110: 3443,   # env3_loop_mode

    # -- Envelope 4  (all virtual-only, overlaps mod matrix) --
    # No entries for 111-118.

    # -- LFO 1  (blob 3444-3453) --
    120: 3448,   # lfo1_enable (lfo_1_on)
    121: 3444,   # lfo1_rate
    122: 3445,   # lfo1_phase
    123: 3446,   # lfo1_smooth
    124: 3447,   # lfo1_delay
    125: 3449,   # lfo1_depth
    126: 3450,   # lfo1_rise
    127: 3451,   # lfo1_mode
    128: 3452,   # lfo1_stereo
    129: 3453,   # lfo1_retrigger

    # -- LFO 2  (blob 3454-3463) --
    130: 3455,   # lfo2_enable
    131: 3457,   # lfo2_rate
    132: 3459,   # lfo2_phase
    133: 3460,   # lfo2_smooth
    134: 3462,   # lfo2_delay
    135: 3458,   # lfo2_depth
    136: 3463,   # lfo2_rise
    137: 3454,   # lfo2_mode
    138: 3456,   # lfo2_stereo
    139: 3461,   # lfo2_retrigger

    # -- LFO 3  (blob 3464-3471) --
    140: 3471,   # lfo3_enable
    141: 3464,   # lfo3_rate
    142: 3465,   # lfo3_phase
    143: 3466,   # lfo3_depth
    144: 3467,   # lfo3_smooth
    145: 3468,   # lfo3_mode
    146: 3469,   # lfo3_delay
    147: 3470,   # lfo3_rise

    # -- LFO 4  (blob 3472-3479) --
    148: 3472,   # lfo4_enable
    149: 3474,   # lfo4_rate
    150: 3475,   # lfo4_phase
    151: 3476,   # lfo4_depth
    152: 3477,   # lfo4_smooth
    153: 3478,   # lfo4_mode
    154: 3479,   # lfo4_on
    155: 3473,   # lfo4_stereo

    # -- FX: Hyper / Dimension  (blob 3480-3484) --
    160: 3480,   # fx_hyper_enable
    161: 3481,   # fx_hyper_rate
    162: 3482,   # fx_hyper_size
    163: 3483,   # fx_hyper_detune
    164: 3484,   # fx_hyper_mix

    # -- FX: Distortion  (blob 3485-3487, enable at 3565) --
    165: 3565,   # fx_dist_enable  (post-mod-matrix enable flag region)
    166: 3485,   # fx_dist_drive
    167: 3486,   # fx_dist_mix
    168: 3487,   # fx_dist_type
    169: 3569,   # fx_dist_post_filter  (post-mod-matrix continuous region)

    # -- FX: Flanger  (blob 3488-3491, enable at 3566) --
    170: 3566,   # fx_flanger_enable  (post-mod-matrix enable flag region)
    171: 3488,   # fx_flanger_rate
    172: 3489,   # fx_flanger_depth
    173: 3490,   # fx_flanger_feedback
    174: 3491,   # fx_flanger_mix

    # -- FX: Phaser  (blob 3492-3496) --
    175: 3492,   # fx_phaser_enable
    176: 3494,   # fx_phaser_rate
    177: 3495,   # fx_phaser_depth
    178: 3496,   # fx_phaser_feedback
    179: 3493,   # fx_phaser_mix

    # -- FX: Chorus  (blob 3497-3499, enable at 3567, mix at 3573) --
    180: 3567,   # fx_chorus_enable  (post-mod-matrix enable flag region)
    181: 3497,   # fx_chorus_rate
    182: 3498,   # fx_chorus_depth
    183: 3499,   # fx_chorus_feedback
    184: 3573,   # fx_chorus_mix  (post-mod-matrix continuous region)

    # -- FX: Delay  (blob 3500-3503, enable at 3568) --
    185: 3568,   # fx_delay_enable  (post-mod-matrix enable flag region)
    186: 3500,   # fx_delay_time
    187: 3501,   # fx_delay_feedback
    188: 3502,   # fx_delay_mix
    189: 3503,   # fx_delay_ping_pong

    # -- FX: Compressor  (blob 3504-3506, enable at 3564, attack at 3570) --
    190: 3564,   # fx_comp_enable  (post-mod-matrix enable flag, before dist/flanger/chorus/delay)
    191: 3504,   # fx_comp_threshold
    192: 3505,   # fx_comp_ratio
    193: 3570,   # fx_comp_attack  (post-mod-matrix continuous region)
    194: 3506,   # fx_comp_mix

    # -- FX: Multiband Compressor  (blob 3507-3508) --
    # 195 = virtual-only (enable)
    196: 3507,   # fx_multicomp_low
    197: 3508,   # fx_multicomp_mid
    # 198, 199 = virtual-only (overlap EQ/reverb)

    # -- FX: EQ  (blob 3509, 3511-3512) --
    200: 3509,   # fx_eq_enable
    # 201 = virtual-only (overlap reverb)
    202: 3511,   # fx_eq_mid_gain
    203: 3512,   # fx_eq_high_gain
    # 204 = virtual-only (overlap reverb/filter)

    # -- FX: Reverb  (blob 3510, 3513-3514, size/decay at 3571-3572) --
    205: 3510,   # fx_reverb_enable
    206: 3571,   # fx_reverb_size  (post-mod-matrix continuous region)
    207: 3572,   # fx_reverb_decay  (post-mod-matrix continuous region)
    208: 3513,   # fx_reverb_mix
    209: 3514,   # fx_reverb_damping

    # -- FX: Filter FX  (blob 3515-3517) --
    # 210, 211 = virtual-only (overlap reverb)
    212: 3515,   # fx_filter_resonance
    213: 3516,   # fx_filter_type
    214: 3517,   # fx_filter_mix

    # -- FX Routing / Chain  (blob 3518-3527) --
    215: 3518,   # fx_chain_order_1
    216: 3519,   # fx_chain_order_2
    217: 3520,   # fx_chain_order_3
    218: 3521,   # fx_chain_order_4
    219: 3522,   # fx_chain_order_5
    220: 3523,   # fx_chain_order_6
    221: 3524,   # fx_chain_order_7
    222: 3525,   # fx_chain_order_8
    223: 3526,   # fx_chain_order_9
    224: 3527,   # fx_chain_order_10

    # -- Macros  (blob 3528-3531) --
    225: 3528,   # macro_1
    226: 3529,   # macro_2
    227: 3530,   # macro_3
    228: 3531,   # macro_4

    # -- Voicing  (blob 3574-3579, post-FX-enable region) --
    229: 3579,   # voice_poly_count
    # 230 = virtual-only (stack_mode)
    # 231 = virtual-only (stack_detune)
    # 232 = virtual-only (stack_voices)
    233: 3574,   # voice_bend_range_up
    234: 3576,   # voice_bend_range_dn
    # 235 = virtual-only (glide_mode)
    236: 3575,   # voice_glide_rate

    # -- Modulation Matrix routing  (blob 3532-3563, pairs) --
    237: 3532,   # mod_1_amount
    238: 3533,   # mod_1_dest
    239: 3534,   # mod_2_amount
    240: 3535,   # mod_2_dest
    241: 3536,   # mod_3_amount
    242: 3537,   # mod_3_dest
    243: 3538,   # mod_4_amount
    244: 3539,   # mod_4_dest
    245: 3540,   # mod_5_amount
    246: 3541,   # mod_5_dest
    247: 3542,   # mod_6_amount
    248: 3543,   # mod_6_dest
    249: 3544,   # mod_7_amount
    250: 3545,   # mod_7_dest
    251: 3546,   # mod_8_amount
    252: 3547,   # mod_8_dest
    253: 3548,   # mod_9_amount
    254: 3549,   # mod_9_dest
    255: 3550,   # mod_10_amount
    256: 3551,   # mod_10_dest
    257: 3552,   # mod_11_amount
    258: 3553,   # mod_11_dest
    259: 3554,   # mod_12_amount
    260: 3555,   # mod_12_dest
    261: 3556,   # mod_13_amount
    262: 3557,   # mod_13_dest
    263: 3558,   # mod_14_amount
    264: 3559,   # mod_14_dest
    265: 3560,   # mod_15_amount
    266: 3561,   # mod_15_dest
    267: 3562,   # mod_16_amount
    268: 3563,   # mod_16_dest
}

# Reverse lookup: param name -> virtual index
PARAM_NAME_TO_INDEX: dict[str, int] = {
    v[0]: k for k, v in PARAM_MAP.items()
}

# Reverse lookup: blob offset -> virtual index (first mapping wins)
_BLOB_TO_PARAM: dict[int, int] = {}
for _vidx, _boff in PARAM_TO_BLOB.items():
    if _boff not in _BLOB_TO_PARAM:
        _BLOB_TO_PARAM[_boff] = _vidx


# ---------------------------------------------------------------------------
# Backward-compatible aliases
#
# The old PARAM_MAP used indices like 0=osc_a_enable, 1=osc_a_volume,
# 20=filter_enable, 21=filter_cutoff, 30=env1_attack, 40=master_volume,
# 100=fx_chorus_enable, 110=fx_delay_enable, 120=fx_reverb_enable, etc.
#
# These OLD virtual indices were used directly as positions in the 512-element
# params list. The new layout keeps the same list indices for these commonly
# used params by placing them at the SAME virtual indices.
#
# For callers that used the old names, we provide aliases.
# ---------------------------------------------------------------------------

_OLD_NAME_ALIASES: dict[str, str] = {
    # Old name                -> New canonical name
    "osc_a_pitch":             "osc_a_semi",
    "osc_a_detune":            "osc_a_fine",
    "osc_a_unison":            "osc_a_unison_voices",
    "osc_b_mode":              "osc_b_warp_mode",
    "osc_b_pitch":             "osc_b_semi",
    "osc_b_detune":            "osc_b_fine",
    "osc_b_unison":            "osc_b_unison_voices",
    "filter_enable":           "filter1_enable",
    "filter_cutoff":           "filter1_cutoff",
    "filter_resonance":        "filter1_resonance",
    "filter_type":             "filter1_type",
    "filter_drive":            "filter1_drive",
    "filter_pan":              "filter1_pan",
    "filter_mix":              "filter1_mix",
    "filter_fat":              "filter1_fat",
    "poly_voices":             "voice_poly_count",
    "portamento":              "portamento_time",
    "lfo1_shape":              "lfo1_mode",
    "lfo2_shape":              "lfo2_mode",
    "fx_eq_low":               "fx_eq_low_gain",
    "fx_eq_mid":               "fx_eq_mid_gain",
    "fx_eq_high":              "fx_eq_high_gain",
    "wave_pos":                "osc_a_wave_pos",
}

# Register old-name aliases in PARAM_NAME_TO_INDEX so they resolve
for _old_name, _new_name in _OLD_NAME_ALIASES.items():
    if _old_name not in PARAM_NAME_TO_INDEX and _new_name in PARAM_NAME_TO_INDEX:
        PARAM_NAME_TO_INDEX[_old_name] = PARAM_NAME_TO_INDEX[_new_name]


# ---------------------------------------------------------------------------
# Internal: Init template blob management
# ---------------------------------------------------------------------------

def _decode_init_template() -> list[float]:
    """Decode the embedded init template blob into a list of floats."""
    compressed = base64.b64decode(_INIT_TEMPLATE_B64)
    raw = zlib.decompress(compressed)
    float_count = len(raw) // 4
    floats: list[float] = []
    for i in range(float_count):
        val = struct.unpack_from("<f", raw, i * 4)[0]
        floats.append(val)
    return floats


# Cache the decoded template
_init_template_cache: list[float] | None = None


def _get_init_template() -> list[float]:
    """Get a copy of the init template blob (cached)."""
    global _init_template_cache
    if _init_template_cache is None:
        _init_template_cache = _decode_init_template()
    return list(_init_template_cache)


def _extract_virtual_params(blob: list[float]) -> list[float]:
    """Extract virtual params from a full blob using PARAM_TO_BLOB mapping.

    Returns a list of SERUM_PARAM_COUNT floats.  For virtual-only params
    (those not in PARAM_TO_BLOB), the PARAM_MAP default is used.  For
    mapped params, the blob value is used.  Unmapped indices outside
    PARAM_MAP default to 0.0.
    """
    # Start with PARAM_MAP defaults for all known params
    params = [0.0] * SERUM_PARAM_COUNT
    for vidx, (_, _, _, _, pdefault) in PARAM_MAP.items():
        if vidx < SERUM_PARAM_COUNT:
            params[vidx] = pdefault

    # Override with actual blob values for mapped params
    for vidx, boff in PARAM_TO_BLOB.items():
        if vidx < SERUM_PARAM_COUNT and boff < len(blob):
            params[vidx] = blob[boff]

    return params


def _overlay_virtual_params(blob: list[float], params: list[float]) -> list[float]:
    """Write virtual param values back into a blob copy.

    Returns a new blob list with the mapped positions updated.
    Only writes params that have a blob mapping (virtual-only params
    are silently skipped).
    """
    new_blob = list(blob)
    for vidx, boff in PARAM_TO_BLOB.items():
        if vidx < len(params) and boff < len(new_blob):
            new_blob[boff] = params[vidx]
    return new_blob


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_fxp(path: str | Path) -> dict[str, Any]:
    """Read a Serum 1 .fxp preset file and return parsed data.

    Returns:
        Dict with keys: name, fx_id, version, fx_version, param_count,
        params (list of SERUM_PARAM_COUNT float32), blob (full blob),
        blob_float_count, raw_size, compressed_size, file_size, path.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: On format errors.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Preset not found: {path}")

    data = path.read_bytes()
    return _parse_fxp_bytes(data, str(path))


def write_fxp(
    path: str | Path,
    name: str,
    params: list[float] | None = None,
    overwrite: bool = False,
) -> str:
    """Write a Serum 1 .fxp preset file.

    Starts from the init template blob and overlays virtual param values,
    preserving all non-parameter data (mod matrix, curves, padding, etc.).

    Args:
        path: Output file path.
        name: Program name (max 27 ASCII chars).
        params: List of SERUM_PARAM_COUNT float32 virtual parameter values.
                If None, uses defaults from init template.
        overwrite: If False, raises if file exists.

    Returns:
        The output path as string.

    Raises:
        FileExistsError: If file exists and overwrite is False.
        ValueError: If params has wrong length.
    """
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"File already exists: {path}")

    if params is None:
        params = _default_params()
    if len(params) != SERUM_PARAM_COUNT:
        raise ValueError(
            f"Expected {SERUM_PARAM_COUNT} params, got {len(params)}"
        )

    fxp_bytes = _build_fxp_bytes(name, params)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(fxp_bytes)
    return str(path)


def get_param(params: list[float], name_or_index: str | int) -> dict[str, Any]:
    """Get a single parameter by name or index.

    Returns dict with: index, name, description, value, min, max, default.
    """
    idx = _resolve_param(name_or_index)
    value = params[idx]
    if idx in PARAM_MAP:
        pname, desc, pmin, pmax, pdefault = PARAM_MAP[idx]
        return {
            "index": idx,
            "name": pname,
            "description": desc,
            "value": value,
            "min": pmin,
            "max": pmax,
            "default": pdefault,
        }
    return {
        "index": idx,
        "name": f"param_{idx}",
        "description": f"Unknown parameter at index {idx}",
        "value": value,
        "min": 0.0,
        "max": 1.0,
        "default": 0.0,
    }


def set_param(
    params: list[float], name_or_index: str | int, value: float
) -> list[float]:
    """Set a parameter value, returning a new list (does not mutate input).

    Raises ValueError if value is outside the known range for mapped params.
    """
    idx = _resolve_param(name_or_index)
    if idx in PARAM_MAP:
        _, _, pmin, pmax, _ = PARAM_MAP[idx]
        if value < pmin or value > pmax:
            raise ValueError(
                f"Value {value} out of range [{pmin}, {pmax}] "
                f"for param {PARAM_MAP[idx][0]}"
            )
    new_params = list(params)
    new_params[idx] = float(value)
    return new_params


def dump_params(
    params: list[float], named_only: bool = False
) -> list[dict[str, Any]]:
    """Dump all parameters as a list of dicts.

    Args:
        named_only: If True, only return params that have a known mapping.
    """
    result = []
    for i in range(SERUM_PARAM_COUNT):
        if named_only and i not in PARAM_MAP:
            continue
        value = params[i]
        if i in PARAM_MAP:
            pname, desc, pmin, pmax, pdefault = PARAM_MAP[i]
            result.append({
                "index": i,
                "name": pname,
                "description": desc,
                "value": value,
                "min": pmin,
                "max": pmax,
                "default": pdefault,
                "is_default": abs(value - pdefault) < 1e-4,
            })
        else:
            result.append({
                "index": i,
                "name": f"param_{i}",
                "description": "",
                "value": value,
                "min": 0.0,
                "max": 1.0,
                "default": 0.0,
                "is_default": abs(value) < 1e-4,
            })
    return result


def diff_params(
    params_a: list[float], params_b: list[float]
) -> list[dict[str, Any]]:
    """Compare two parameter lists and return differences."""
    if len(params_a) != SERUM_PARAM_COUNT or len(params_b) != SERUM_PARAM_COUNT:
        raise ValueError(
            f"Both param lists must have {SERUM_PARAM_COUNT} entries"
        )

    diffs = []
    for i in range(SERUM_PARAM_COUNT):
        if abs(params_a[i] - params_b[i]) > 1e-6:
            entry: dict[str, Any] = {
                "index": i,
                "value_a": params_a[i],
                "value_b": params_b[i],
                "delta": params_b[i] - params_a[i],
            }
            if i in PARAM_MAP:
                entry["name"] = PARAM_MAP[i][0]
                entry["description"] = PARAM_MAP[i][1]
            else:
                entry["name"] = f"param_{i}"
                entry["description"] = ""
            diffs.append(entry)
    return diffs


def validate_fxp(path: str | Path) -> dict[str, Any]:
    """Validate an .fxp file and return diagnostic info.

    Returns a dict with: valid (bool), errors (list[str]), warnings (list[str]),
    plus header info if parseable.
    """
    path = Path(path)
    errors: list[str] = []
    warnings: list[str] = []
    info: dict[str, Any] = {"valid": True, "errors": errors, "warnings": warnings}

    if not path.exists():
        errors.append(f"File not found: {path}")
        info["valid"] = False
        return info

    data = path.read_bytes()
    info["file_size"] = len(data)

    if len(data) < FXP_HEADER_SIZE:
        errors.append(f"File too small: {len(data)} bytes (min {FXP_HEADER_SIZE})")
        info["valid"] = False
        return info

    # Check magic
    if data[:4] != FXP_MAGIC:
        errors.append(f"Bad magic: expected CcnK, got {data[:4]!r}")
        info["valid"] = False

    # Check chunk type
    if data[8:12] != FXP_CHUNK_TYPE:
        errors.append(f"Bad chunk type: expected FPCh, got {data[8:12]!r}")
        info["valid"] = False

    # Check plugin ID
    fx_id = data[16:20]
    info["fx_id"] = fx_id.decode("ascii", errors="replace")
    if fx_id != SERUM_FX_ID:
        warnings.append(
            f"Plugin ID is {fx_id!r}, not XfsX. "
            "This may not be a Serum preset."
        )

    # Parse name
    name_bytes = data[28:56]
    info["name"] = name_bytes.split(b"\x00")[0].decode("ascii", errors="replace")

    # Check chunk
    if len(data) >= 60:
        chunk_size = struct.unpack_from(">I", data, 56)[0]
        info["chunk_size"] = chunk_size
        actual_chunk = data[60:]
        if len(actual_chunk) != chunk_size:
            warnings.append(
                f"Declared chunk size {chunk_size} != actual {len(actual_chunk)}"
            )

        # Try to decompress
        try:
            raw = zlib.decompress(actual_chunk)
            info["decompressed_size"] = len(raw)
            float_count = len(raw) // 4
            info["float_count"] = float_count

            if float_count < SERUM_PARAM_COUNT:
                warnings.append(
                    f"Blob has {float_count} floats, fewer than virtual "
                    f"param count {SERUM_PARAM_COUNT}"
                )
            if float_count >= SERUM_BLOB_FLOATS:
                info["blob_version"] = "full"
            elif float_count >= 512:
                info["blob_version"] = "partial"
                warnings.append(
                    f"Blob has {float_count} floats (expected ~{SERUM_BLOB_FLOATS}). "
                    "Some parameters may not be addressable."
                )
        except zlib.error as exc:
            errors.append(f"Zlib decompression failed: {exc}")
            info["valid"] = False

    if errors:
        info["valid"] = False

    return info


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_fxp_bytes(data: bytes, source: str = "") -> dict[str, Any]:
    """Parse raw .fxp bytes into a structured dict."""
    if len(data) < FXP_HEADER_SIZE:
        raise ValueError(
            f"File too small: {len(data)} bytes (need >= {FXP_HEADER_SIZE})"
        )

    magic = data[:4]
    if magic != FXP_MAGIC:
        raise ValueError(f"Bad magic: expected CcnK, got {magic!r}")

    total_size = struct.unpack_from(">I", data, 4)[0]
    chunk_type = data[8:12]
    if chunk_type != FXP_CHUNK_TYPE:
        raise ValueError(f"Bad chunk type: expected FPCh, got {chunk_type!r}")

    version = struct.unpack_from(">I", data, 12)[0]
    fx_id = data[16:20]
    fx_version = struct.unpack_from(">I", data, 20)[0]
    num_progs = struct.unpack_from(">I", data, 24)[0]
    name_raw = data[28:56]
    name = name_raw.split(b"\x00")[0].decode("ascii", errors="replace")

    chunk_size = struct.unpack_from(">I", data, 56)[0]
    chunk_data = data[60:]

    if len(chunk_data) < chunk_size:
        raise ValueError(
            f"Truncated chunk: declared {chunk_size} bytes, "
            f"only {len(chunk_data)} available"
        )
    # Use only the declared chunk size
    chunk_data = chunk_data[:chunk_size]

    # Decompress
    try:
        raw = zlib.decompress(chunk_data)
    except zlib.error as exc:
        raise ValueError(f"Zlib decompression failed: {exc}") from exc

    # Parse full float32 array from the blob
    blob_float_count = len(raw) // 4
    blob: list[float] = []
    for i in range(blob_float_count):
        val = struct.unpack_from("<f", raw, i * 4)[0]
        blob.append(val)

    # Extract the virtual param array from the blob
    params = _extract_virtual_params(blob)

    return {
        "name": name,
        "fx_id": fx_id.decode("ascii", errors="replace"),
        "version": version,
        "fx_version": fx_version,
        "num_programs": num_progs,
        "param_count": SERUM_PARAM_COUNT,
        "params": params,
        "blob": blob,
        "blob_float_count": blob_float_count,
        "raw_size": len(raw),
        "compressed_size": len(chunk_data),
        "file_size": len(data),
        "path": source,
    }


def _build_fxp_bytes(name: str, params: list[float]) -> bytes:
    """Build a valid Serum 1 .fxp from name and virtual params.

    Starts from the init template blob and overlays virtual param values,
    preserving all non-parameter blob data (mod matrix, curves, etc.).
    """
    # Get a fresh copy of the init template blob
    blob = _get_init_template()

    # Overlay the virtual params into the blob
    blob = _overlay_virtual_params(blob, params)

    # Encode the full blob as float32 little-endian
    raw = bytearray(len(blob) * 4)
    for i, val in enumerate(blob):
        struct.pack_into("<f", raw, i * 4, float(val))

    # Compress
    chunk = zlib.compress(bytes(raw), 6)

    # Program name: 28 bytes, null-padded ASCII
    prg_name = name.encode("ascii", errors="replace")[:27] + b"\x00"
    prg_name = prg_name.ljust(28, b"\x00")

    # Inner: version(4) + fxID(4) + fxVersion(4) + numProgs(4) + name(28) + chunkSize(4) + chunk
    inner = bytearray()
    inner.extend(struct.pack(">I", 1))       # version
    inner.extend(SERUM_FX_ID)                 # fxID "XfsX"
    inner.extend(struct.pack(">I", 1))       # fxVersion
    inner.extend(struct.pack(">I", 1))       # numPrograms
    inner.extend(prg_name)
    inner.extend(struct.pack(">I", len(chunk)))
    inner.extend(chunk)

    # Outer: CcnK(4) + totalSize(4) + FPCh(4) + inner
    out = bytearray()
    out.extend(FXP_MAGIC)
    out.extend(struct.pack(">I", len(inner) + 4))  # +4 for FPCh
    out.extend(FXP_CHUNK_TYPE)
    out.extend(inner)

    return bytes(out)


def _default_params() -> list[float]:
    """Return a default Serum 1 init patch virtual parameter array.

    Extracts defaults from the init template blob via PARAM_TO_BLOB mapping,
    so the defaults reflect a real Serum init preset.
    """
    blob = _get_init_template()
    return _extract_virtual_params(blob)


def _resolve_param(name_or_index: str | int) -> int:
    """Resolve a param name or index string to a virtual index."""
    if isinstance(name_or_index, int):
        if 0 <= name_or_index < SERUM_PARAM_COUNT:
            return name_or_index
        raise ValueError(
            f"Index {name_or_index} out of range [0, {SERUM_PARAM_COUNT})"
        )

    # Try as integer string
    try:
        idx = int(name_or_index)
        if 0 <= idx < SERUM_PARAM_COUNT:
            return idx
        raise ValueError(
            f"Index {idx} out of range [0, {SERUM_PARAM_COUNT})"
        )
    except ValueError:
        pass

    # Try as parameter name (case-insensitive)
    name_lower = name_or_index.lower().strip()
    if name_lower in PARAM_NAME_TO_INDEX:
        return PARAM_NAME_TO_INDEX[name_lower]

    raise ValueError(
        f"Unknown parameter: {name_or_index!r}. "
        f"Use a numeric index (0-{SERUM_PARAM_COUNT - 1}) or a known name "
        "like 'osc_a_volume'."
    )
