# Sound-Reactive Effects Expansion

## Goal

Add 5 sound-reactive variants of existing effects, fix 2 bugs in existing sound-reactive effects, and ensure every sound-reactive effect has a gain parameter.

## Scope

**5 new "SR" variants** (added alongside originals, not replacing):
- SR Feldstein (based on Feldstein OG)
- SR Lava Lamp (based on Lava Lamp)
- SR Matrix Rain (based on Matrix Rain)
- SR Moire (based on Moire)
- SR Flow Field (based on Flow Field)

**2 bug fixes:**
- Spectral Glow upside-down
- Energy Ring thickness should vary by frequency spectrum (spectrogram-shaped ring)

**Gain audit:**
- Verify every sound-reactive effect has a `gain` param, add one to any that lack it.

## Design

### Naming

All new variants prefix with "SR " (Sound Reactive). This sorts them together in the effects list and keeps names short.

### Audio Driver Per Variant

Each SR variant inherits the base effect's visual style and overlays audio modulation. One signal drives one visual parameter (simple, predictable).

| Effect | Audio → Visual Mapping |
|--------|------------------------|
| SR Feldstein | `bass` → speed boost; `beat` → hue shift pulse; `buildup` → increased fade/persistence |
| SR Lava Lamp | `bass` → blob size scaling; `beat` → blobs pulse toward center; `drop` → blob count surges |
| SR Matrix Rain | `bass` → drop speed multiplier; `beat` → density spike; `buildup` → longer trails |
| SR Moire | `bass` → ring frequency (tighter rings); `beat` → centers pulse inward; `drop` → expansion |
| SR Flow Field | `bass` → flow velocity; `beat` → particle burst (spawn extra); `buildup` → particle count increases |

### Params Per SR Variant

Each SR variant has 2–3 params:
- `gain` (0.1–5.0, default 1.0) — audio sensitivity multiplier
- `palette` (dropdown) — color theme
- `speed` or other base param if essential (varies per effect; e.g., Matrix Rain keeps `speed` for base fall rate)

### Implementation Pattern

Each SR variant follows the existing sound-reactive pattern from `pi/app/effects/imported/sound.py`:

```python
class SRFeldstein(Effect):
  CATEGORY = "sound"
  DISPLAY_NAME = "SR Feldstein"
  PALETTE_SUPPORT = True
  NATIVE_WIDTH = 10
  PARAMS = [
    _Param("Gain", "gain", 0.1, 5.0, 0.1, 1.0),
    _Param("Speed", "speed", 0.04, 0.6, 0.02, 0.2),
  ]

  def __init__(self, width=10, height=N, params=None):
    super().__init__(width, height, params)
    self._audio_adapter = AudioCompatAdapter()
    # Delegate to base Feldstein2 for core rendering
    self._base = Feldstein2(width, height, params)

  def render(self, t, state):
    audio = self._audio_adapter.adapt(state._audio_lock_free, t)
    gain = self.params.get("gain", 1.0)

    # Audio-driven param modulation
    boosted_params = {
      **self.params,
      "speed": self.params.get("speed", 0.2) * (1.0 + audio.bass * gain * 2.0),
      "fade": max(10, min(200, 48 - audio.buildup * gain * 30)),
    }
    self._base.params = boosted_params
    frame = self._base.render(t, state)

    # Beat-triggered hue pulse on top of base render
    if audio.beat:
      self._hue_offset = (self._hue_offset + 0.15 * gain) % 1.0
    # Apply hue rotation overlay here if needed
    return frame
```

Variants delegate to their base effect when possible (Feldstein, Moire, etc.) to avoid duplicating the core noise/physics code. When delegation isn't clean (Lava Lamp blobs, Matrix Rain drops), re-implement the render loop with audio-driven params.

### Energy Ring Fix

Current: uniform ring thickness from `audio_level`.

New: per-column thickness from 16-bin spectrum resampled to 10 columns. Each of the 10 columns gets its own `ring_width` based on its corresponding spectrum band. The ring becomes a wavy band — wide where that frequency is loud, thin where it's quiet. Still moves vertically with time.

Implementation:
```python
# Resample 16-bin spectrum to 10 columns
spectrum = state.audio_spectrum  # 16 floats
bands_10 = self._resample_16_to_10(spectrum)

# Per-column ring thickness
for x in range(self.width):
  ring_width = max(1, int(bands_10[x] * 30 * gain))
  for y in range(self.height):
    dist = toroidal_distance(y, ring_y)
    if dist < ring_width:
      ...
```

### Spectral Glow Fix

Invert the y-axis check so bars grow upward from the bottom. Current code lights pixels where `y_grid < fill_heights` (bottom up, which is correct) but the render places them with y=0 at top. Fix by reversing y_grid indexing:

```python
# Before:
lit_mask = y_grid < fill_heights[:, np.newaxis]
# After (bars grow from bottom):
y_from_bottom = self.height - 1 - y_grid
lit_mask = y_from_bottom < fill_heights[:, np.newaxis]
```

### Gain Audit

Before implementing variants, verify each existing sound-reactive effect has a `gain` param:

| Effect | Has gain? | Action |
|--------|-----------|--------|
| Spectrum | Yes | — |
| VU Meter | Check | Add if missing |
| Beat Pulse | Check | Add if missing |
| Bass Fire | Yes | — |
| Sound Ripples | Check | Add if missing |
| Spectrogram | Yes | — |
| Sound Worm | Check | Add if missing |
| Particle Burst | Check | Add if missing |
| Sound Plasma | Check | Add if missing |
| Strobe Chaos | Check | Add if missing |
| Spectral Glow | Check | Add (was audio_reactive.py, not sound.py) |
| Energy Ring | Check | Add (while rewriting for spectrogram thickness) |

For any missing gain: add `_Param("Gain", "gain", 0.1, 5.0, 0.1, 1.0)` to PARAMS and use it as a multiplier on the audio-driven visual parameter.

### Files

**New:**
- `pi/app/effects/imported/sound_variants.py` — all 5 SR classes

**Modified:**
- `pi/app/effects/audio_reactive.py` — fix Spectral Glow, rewrite Energy Ring
- `pi/app/effects/imported/sound.py` — add gain to any sound effects missing it
- `pi/app/main.py` — register the 5 new SR effects in the catalog

**Updated catalog registration:** The 5 new SR effects go into `CATEGORY = "sound"` so they show up alongside the existing sound effects in the UI filter.

## Not In Scope

- Rewriting existing sound effects' audio behavior beyond the 2 bug fixes
- Adding new audio features to `AudioCompatAdapter`
- UI changes for browsing effects (the sound category already exists)
- Performance optimization beyond existing vectorized patterns

## Performance Targets

All SR variants must sustain 60 FPS on Raspberry Pi 4. Follow the existing vectorized patterns from `sound.py` (numpy operations, not per-pixel Python loops).
