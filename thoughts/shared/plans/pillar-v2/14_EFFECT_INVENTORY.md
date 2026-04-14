# 14 — Imported Effect Inventory

This inventory is generated from the uploaded `led_sim.py` source and is the planning truth for imported effects.

## Summary

| Category | Count |
|---|---:|
| Classic | 5 |
| Ambient | 12 |
| Sound | 10 |
| Total | 27 |

Note: the source file header says 23 animations, but the code defines 27 `AnimBase` classes.

## Classic

| Display name | Class | Batch | Audio dependencies |
|---|---|---|---|
| Brett's Favorite | `BrettsFavorite` | B1 | — |
| Feldstein Equation | `FeldsteinEquation` | B1 | — |
| Feldstein OG | `Feldstein2` | B1 | — |
| Fireplace | `Fireplace` | B1 | — |
| Rainbow Cycle | `RainbowCycle` | B1 | — |

## Ambient

| Display name | Class | Batch | Audio dependencies |
|---|---|---|---|
| Aurora Borealis | `Aurora` | B1 | — |
| Breathing | `Breathing` | B1 | — |
| Fireflies | `Fireflies` | B1 | — |
| Flow Field | `FlowField` | B1 | — |
| Kaleidoscope | `Kaleidoscope` | B1 | — |
| Lava Lamp | `LavaLamp` | B1 | — |
| Matrix Rain | `MatrixRain` | B1 | — |
| Moire | `Moire` | B1 | — |
| Nebula | `Nebula` | B1 | — |
| Ocean Waves | `OceanWaves` | B1 | — |
| Plasma | `Plasma` | B1 | — |
| Starfield | `Starfield` | B1 | — |

## Sound

| Display name | Class | Batch | Audio dependencies |
|---|---|---|---|
| Bass Fire | `BassReactiveFire` | B3 | bands, bass, beat, beat_energy, drop, is_downbeat, is_phrase |
| Beat Pulse | `BeatPulse` | B2 | _time, beat, breakdown, buildup, drop |
| Particle Burst | `ParticleBurst` | B2 | beat, breakdown, buildup, drop |
| Sound Plasma | `SoundPlasma` | B2 | breakdown, buildup, drop, volume |
| Sound Ripples | `SoundRipples` | B3 | bass, beat, beat_energy, highs, is_downbeat, is_phrase, mids |
| Sound Worm | `SoundWorm` | B2 | buildup, drop, volume |
| Spectrogram | `Spectrogram` | B3 | bands, buildup, drop |
| Spectrum | `Spectrum` | B3 | bands, buildup, drop |
| Strobe Chaos | `StrobeChaos` | B2 | beat, breakdown, buildup, drop |
| VU Meter | `VUMeter` | B2 | _time, breakdown, buildup, drop, volume |

## Batch meaning

| Batch | Meaning |
|---|---|
| B1 | import immediately; no audio dependency |
| B2 | requires alias/time + advanced musical-state adapter |
| B3 | also requires `bands`, `beat_energy`, and/or phrase/downbeat structure |
