"""
Metadata registry for imported led_sim.py effects.

27 effects total: 5 Classic, 12 Ambient, 10 Sound-reactive.
Organized by batch for dependency gating.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ImportedEffectMeta:
  name: str
  display_name: str
  category: str  # classic | ambient | sound
  batch: str  # B1 | B2 | B3
  class_name: str
  description: str
  audio_requires: tuple = ()


# Complete inventory of all 27 imported effects

IMPORTED_EFFECTS_META = {
  # === Classic (B1) ===
  'bretts_favorite': ImportedEffectMeta(
    'bretts_favorite', "Brett's Favorite", 'classic', 'B1', 'BrettsFavorite',
    'Classic color cycling with smooth gradient transitions',
  ),
  'feldstein_equation': ImportedEffectMeta(
    'feldstein_equation', 'Feldstein Equation', 'classic', 'B1', 'FeldsteinEquation',
    'Mathematical color field based on sine wave composition',
  ),
  'feldstein_og': ImportedEffectMeta(
    'feldstein_og', 'Feldstein OG', 'classic', 'B1', 'Feldstein2',
    'Original Feldstein color algorithm variant',
  ),
  'fireplace': ImportedEffectMeta(
    'fireplace', 'Fireplace', 'classic', 'B1', 'Fireplace',
    'Warm flickering fireplace simulation',
  ),
  'rainbow_cycle_sim': ImportedEffectMeta(
    'rainbow_cycle_sim', 'Rainbow Cycle', 'classic', 'B1', 'RainbowCycle',
    'Smooth rainbow color cycling across the pillar',
  ),

  # === Ambient (B1) ===
  'aurora_borealis': ImportedEffectMeta(
    'aurora_borealis', 'Aurora Borealis', 'ambient', 'B1', 'Aurora',
    'Shimmering northern lights with flowing curtains',
  ),
  'breathing': ImportedEffectMeta(
    'breathing', 'Breathing', 'ambient', 'B1', 'Breathing',
    'Gentle pulsing glow like calm breathing',
  ),
  'fireflies': ImportedEffectMeta(
    'fireflies', 'Fireflies', 'ambient', 'B1', 'Fireflies',
    'Random twinkling points like fireflies at dusk',
  ),
  'flow_field': ImportedEffectMeta(
    'flow_field', 'Flow Field', 'ambient', 'B1', 'FlowField',
    'Particles following smooth vector field paths',
  ),
  'kaleidoscope': ImportedEffectMeta(
    'kaleidoscope', 'Kaleidoscope', 'ambient', 'B1', 'Kaleidoscope',
    'Symmetric rotating color patterns',
  ),
  'lava_lamp': ImportedEffectMeta(
    'lava_lamp', 'Lava Lamp', 'ambient', 'B1', 'LavaLamp',
    'Slow morphing blobs of warm color',
  ),
  'matrix_rain': ImportedEffectMeta(
    'matrix_rain', 'Matrix Rain', 'ambient', 'B1', 'MatrixRain',
    'Cascading green characters falling downward',
  ),
  'moire': ImportedEffectMeta(
    'moire', 'Moire', 'ambient', 'B1', 'Moire',
    'Interference patterns from overlapping wave grids',
  ),
  'nebula': ImportedEffectMeta(
    'nebula', 'Nebula', 'ambient', 'B1', 'Nebula',
    'Deep space nebula clouds with slow color shifts',
  ),
  'ocean_waves': ImportedEffectMeta(
    'ocean_waves', 'Ocean Waves', 'ambient', 'B1', 'OceanWaves',
    'Rolling ocean wave patterns in blue gradients',
  ),
  'plasma_sim': ImportedEffectMeta(
    'plasma_sim', 'Plasma', 'ambient', 'B1', 'Plasma',
    'Classic plasma effect with smooth color blending',
  ),
  'starfield': ImportedEffectMeta(
    'starfield', 'Starfield', 'ambient', 'B1', 'Starfield',
    'Twinkling stars with varying brightness and color',
  ),

  # === Sound-Reactive (B2) ===
  'beat_pulse': ImportedEffectMeta(
    'beat_pulse', 'Beat Pulse', 'sound', 'B2', 'BeatPulse',
    'Pulsing color flash synchronized to beat',
    audio_requires=('beat', 'buildup', 'breakdown', 'drop', 'time_s'),
  ),
  'particle_burst': ImportedEffectMeta(
    'particle_burst', 'Particle Burst', 'sound', 'B2', 'ParticleBurst',
    'Explosive particle spray triggered by beats',
    audio_requires=('beat', 'buildup', 'breakdown', 'drop'),
  ),
  'sound_plasma': ImportedEffectMeta(
    'sound_plasma', 'Sound Plasma', 'sound', 'B2', 'SoundPlasma',
    'Plasma patterns modulated by audio volume',
    audio_requires=('volume', 'buildup', 'breakdown', 'drop'),
  ),
  'sound_worm': ImportedEffectMeta(
    'sound_worm', 'Sound Worm', 'sound', 'B2', 'SoundWorm',
    'Crawling worm trail driven by volume',
    audio_requires=('volume', 'buildup', 'drop'),
  ),
  'strobe_chaos': ImportedEffectMeta(
    'strobe_chaos', 'Strobe Chaos', 'sound', 'B2', 'StrobeChaos',
    'Chaotic strobe patterns triggered by beats',
    audio_requires=('beat', 'buildup', 'breakdown', 'drop'),
  ),
  'vu_meter': ImportedEffectMeta(
    'vu_meter', 'VU Meter', 'sound', 'B2', 'VUMeter',
    'Classic VU meter bar visualization',
    audio_requires=('volume', 'buildup', 'breakdown', 'drop', 'time_s'),
  ),

  # === Sound-Reactive (B3) ===
  'bass_fire': ImportedEffectMeta(
    'bass_fire', 'Bass Fire', 'sound', 'B3', 'BassReactiveFire',
    'Fire effect modulated by bass intensity',
    audio_requires=('bands', 'bass', 'beat', 'beat_energy', 'drop', 'is_downbeat', 'is_phrase'),
  ),
  'sound_ripples': ImportedEffectMeta(
    'sound_ripples', 'Sound Ripples', 'sound', 'B3', 'SoundRipples',
    'Ripple waves expanding from beat impacts',
    audio_requires=('bass', 'beat', 'beat_energy', 'highs', 'is_downbeat', 'is_phrase', 'mids'),
  ),
  'spectrogram': ImportedEffectMeta(
    'spectrogram', 'Spectrogram', 'sound', 'B3', 'Spectrogram',
    'Scrolling frequency band visualization',
    audio_requires=('bands', 'buildup', 'drop'),
  ),
  'spectrum': ImportedEffectMeta(
    'spectrum', 'Spectrum', 'sound', 'B3', 'Spectrum',
    'Real-time frequency spectrum display',
    audio_requires=('bands', 'buildup', 'drop'),
  ),
}

# Batch groupings
BATCH_B1 = {k: v for k, v in IMPORTED_EFFECTS_META.items() if v.batch == 'B1'}
BATCH_B2 = {k: v for k, v in IMPORTED_EFFECTS_META.items() if v.batch == 'B2'}
BATCH_B3 = {k: v for k, v in IMPORTED_EFFECTS_META.items() if v.batch == 'B3'}
