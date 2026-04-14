# 08 — Imported Animations and Audio Adapter

This document covers the `led_sim.py` import plan.

## 1. Inventory truth

The uploaded file header says “23 animations,” but the code actually defines **27** `AnimBase` classes:

- 5 Classic
- 12 Ambient
- 10 Sound-reactive

That discrepancy must be corrected in metadata and planning.

## 2. Porting approach

Do not embed the simulator shell.

### Wrong path

- importing the simulator wholesale
- running its Pygame loop
- monkeypatching its globals at runtime
- depending on desktop-only modules

### Right path

Create repo-native effect modules plus shared helpers:

| Module | Purpose |
|---|---|
| `pi/app/effects/imported_sim_helpers.py` | palettes, noise, matrix buffer, math helpers |
| `pi/app/effects/imported_sim_classic.py` | classic ports |
| `pi/app/effects/imported_sim_ambient.py` | ambient ports |
| `pi/app/effects/imported_sim_sound.py` | sound-reactive ports |
| `pi/app/effects/imported_sim_meta.py` | metadata registry |

## 3. Runtime adapter pattern

Each imported effect should become a normal repo `Effect` subclass.

Recommended adapter behavior:

- keep an instance-local buffer
- track `last_t`
- compute `dt_ms = max(0, (t - last_t) * 1000)`
- translate repo audio state into an `AudioCompat` object
- call the ported update logic
- return `(width, height, 3)` uint8

## 4. Audio adapter contract

The current repo exposes too little for sound-reactive parity.

### Required adapter fields

| Field | Source |
|---|---|
| `volume` | alias of repo `level` |
| `bass` | current bass |
| `mids` | alias of repo `mid` |
| `highs` | alias of repo `high` |
| `bands` | fixed-length 10-column view for visualizers |
| `beat` | current beat trigger |
| `beat_energy` | new |
| `bpm` | new meaningful estimate |
| `beat_count` | new |
| `bar_beat` | new |
| `phrase_beat` | new |
| `is_downbeat` | new |
| `is_phrase` | new |
| `beat_phase` | new |
| `buildup` | new |
| `breakdown` | new |
| `drop` | new |
| `time_s` | derived from `t` |

### Important rule

Do not reproduce `audio._time` as a private mutable backdoor.

Replace it with `time_s` or direct use of `t`.

## 5. Safe port batches

| Batch | Description |
|---|---|
| `B1` | non-audio classic + ambient ports |
| `B2` | sound ports that only need aliases/time plus advanced musical state |
| `B3` | sound ports that also need `bands`, `beat_energy`, or phrase/downbeat structure |

## 6. Imported effect inventory

| Effect | Category | Batch | Audio dependencies |
|---|---|---|---|
| Brett's Favorite | Classic | B1 | — |
| Feldstein Equation | Classic | B1 | — |
| Feldstein OG | Classic | B1 | — |
| Fireplace | Classic | B1 | — |
| Rainbow Cycle | Classic | B1 | — |
| Aurora Borealis | Ambient | B1 | — |
| Breathing | Ambient | B1 | — |
| Fireflies | Ambient | B1 | — |
| Flow Field | Ambient | B1 | — |
| Kaleidoscope | Ambient | B1 | — |
| Lava Lamp | Ambient | B1 | — |
| Matrix Rain | Ambient | B1 | — |
| Moire | Ambient | B1 | — |
| Nebula | Ambient | B1 | — |
| Ocean Waves | Ambient | B1 | — |
| Plasma | Ambient | B1 | — |
| Starfield | Ambient | B1 | — |
| Bass Fire | Sound | B3 | bands, bass, beat, beat_energy, drop, is_downbeat, is_phrase |
| Beat Pulse | Sound | B2 | _time, beat, breakdown, buildup, drop |
| Particle Burst | Sound | B2 | beat, breakdown, buildup, drop |
| Sound Plasma | Sound | B2 | breakdown, buildup, drop, volume |
| Sound Ripples | Sound | B3 | bass, beat, beat_energy, highs, is_downbeat, is_phrase, mids |
| Sound Worm | Sound | B2 | buildup, drop, volume |
| Spectrogram | Sound | B3 | bands, buildup, drop |
| Spectrum | Sound | B3 | bands, buildup, drop |
| Strobe Chaos | Sound | B2 | beat, breakdown, buildup, drop |
| VU Meter | Sound | B2 | _time, breakdown, buildup, drop, volume |

## 7. Metadata cleanup needed

The following imported classes lack docstrings and will need explicit metadata entries:

Fireplace, Rainbow Cycle, Aurora Borealis, Breathing, Fireflies, Kaleidoscope, Lava Lamp, Matrix Rain, Nebula, Ocean Waves, Plasma, Starfield, Beat Pulse, Sound Plasma, Sound Worm, Spectrogram, Spectrum, Strobe Chaos, VU Meter

## 8. Batch details

### 8.1 Batch B1 — import immediately

All non-audio effects can ship once helper functions and buffer logic are ported.

### 8.2 Batch B2 — gated on advanced musical state

These ports need aliasing plus `breakdown`, `buildup`, `drop`, or beat timing:

- VU Meter
- Beat Pulse
- Sound Worm
- Particle Burst
- Sound Plasma
- Strobe Chaos

### 8.3 Batch B3 — gated on full band/phrase surface

These ports need `bands`, `beat_energy`, and/or phrase/downbeat structure:

- Spectrum
- Bass Fire
- Sound Ripples
- Spectrogram

## 9. Parameter handling

Use repo-native parameter metadata.

Rules:

- default params live in `effects.yaml`
- explicit catalog metadata defines label/description/default group
- runtime request params override YAML defaults
- imported effect code must not hardcode user-visible defaults in multiple places

## 10. Tests

Add tests for:

- every imported effect returns `(10, 172, 3)` uint8
- time continuity across multiple renders
- param overrides work
- audio adapter aliases exist
- band array length is exactly 10 for visualizers
- batch-gated sound effects are not activated before their dependencies exist

## 11. Done criteria

- 27 imported effects are cataloged
- batch B1 ships first and is stable
- sound-reactive imports only ship when their adapter surface is real
- imported metadata is explicit and tooltip-ready
