# Sound-Reactive Effects Expansion

## Goal

Add 5 sound-reactive variants of existing effects, fix 2 bugs in existing sound-reactive effects, and add a gain param to every sound-reactive effect that lacks one.

## Scope

**5 new "SR" variants** (added alongside originals, not replacing):
- SR Feldstein (based on Feldstein OG)
- SR Lava Lamp (based on Lava Lamp)
- SR Matrix Rain (based on Matrix Rain)
- SR Moire (based on Moire)
- SR Flow Field (based on Flow Field)

**2 bug fixes:**
- Spectral Glow upside-down
- Energy Ring: thickness driven by 16-bin FFT spectrum

**Gain audit:**
- Add a `gain` param to every sound-reactive effect that lacks one.

## Design

### Naming

All new variants prefix with "SR " (Sound Reactive). This sorts them together in the effects list.

### Implementation Pattern: Fork, don't delegate

Initial design proposed delegating to the base effect by mutating its params. This doesn't work for effects whose audio-driven behavior isn't expressible through existing params (Lava Lamp center attraction, Moire center pulse, Flow Field burst). The base effects also hold private state (noise caches, particle pools, persistent buffers) that a delegating wrapper can't access cleanly.

**Decision:** Each SR variant is a full fork. The class copies the base effect's render loop into its own `render()` method and layers audio modulation on top. Yes, this duplicates code; the upside is each variant is self-contained, easy to read, and safe to tune without touching the original.

### Audio Driver Per Variant

| Effect | Audio → Visual Mapping |
|--------|------------------------|
| SR Feldstein | `bass * gain` → speed boost; `buildup * gain` → increased fade/persistence; `beat` → 0.15-rad hue shift pulse |
| SR Lava Lamp | `bass * gain` → blob size scaling (up to 2x base size); `beat` → blobs momentarily pull toward vertical center; `drop` → temporarily add 4 more blobs (capped at base max of 12) |
| SR Matrix Rain | `bass * gain` → drop speed multiplier (1x – 3x base); `beat` → spawn probability spike for 1 frame; `buildup * gain` → longer trail length (up to 2x) |
| SR Moire | `bass * gain` → ring scale (frequency); `beat` → centers jump toward pillar center for one frame; `drop` → ring scale briefly doubles |
| SR Flow Field | `bass * gain` → flow velocity multiplier (1x – 2.5x); `buildup * gain` → particle trail brightness multiplier (no extra particle spawning — avoids 60 FPS risk from the base's scalar per-particle loop); `beat` → 1-frame full-brightness flash on existing particles |

### Params Per SR Variant

Each SR variant has 2–3 params:
- `gain` (0.1–5.0, default 1.0) — audio sensitivity multiplier
- Base effect's essential control param(s) (varies; e.g., Matrix Rain keeps `speed` for base fall rate, Lava Lamp keeps `blobs` for base count)
- `palette` (dropdown) — color theme (via PALETTE_SUPPORT)

### Energy Ring Rewrite

**Current behavior:** uniform horizontal ring (a band across y at a sweeping vertical position), thickness set by `audio_level`.

**New behavior:** the ring becomes a horizontal band that moves vertically over time, but its **local thickness varies around the circumference (around the cylinder) based on the 16-bin FFT spectrum resampled to 10 bands**. Each of the 10 columns (strips around the cylinder) gets its own ring thickness from its corresponding band. Loud frequencies produce a thick ring segment at that column; quiet frequencies produce a thin segment. Visually, the ring becomes a wavy band whose profile matches the frequency content.

**Implementation:**

```python
# In EnergyRing.render:
spectrum = state.audio_spectrum  # 16 floats
bands_10 = self._resample_16_to_10(spectrum)  # new helper method
gain = self.params.get("gain", 1.0)

# Per-column thickness from corresponding band
col_widths = np.maximum(1, (bands_10 * 30 * gain).astype(int))

# Existing vertical sweep logic
ring_y = int((elapsed * speed * 10) % self.height)

for x in range(self.width):
  width = col_widths[x]
  for y in range(self.height):
    dist = min(abs(y - ring_y), self.height - abs(y - ring_y))
    if dist < width:
      fade = 1.0 - dist / width
      hue = (x / self.width + elapsed * 0.1) % 1.0
      frame[x, y] = hsv_to_rgb(hue, 1.0, fade)
```

### Spectral Glow Fix

**Investigation:**

Current code at `pi/app/effects/audio_reactive.py:136`:
```python
lit_mask = y_grid < fill_grid  # pixels at y=0..fill_height-1 are lit
```

The project's logical coordinate system defines `y=0 = bottom` (cylinder.py:7). So `y_grid < fill_grid` lights pixels from the bottom upward — correct bar growth direction.

The fade:
```python
fade = 1.0 - np.arange(height) / height * 0.5  # y=0 → 1.0, y=height → 0.5
```
Makes bars brightest at the bottom and dimmer at the top. This is probably what looks "upside down" — users expect the **tip** of a VU bar to be brightest (like a rising flame), not the base.

**Fix:** Invert the fade direction so the bar is brightest at its top (at `y = fill_height`) and dimmer near the base. This preserves the correct fill direction (grows up from bottom) and gives the intuitive "bar tip bright" appearance.

```python
# Before:
fade = 1.0 - y_frac * 0.5

# After (brightest at top of bar / y=height-1):
fade = 0.5 + y_frac * 0.5  # y=0 → 0.5, y=height → 1.0
```

If the user tests this fix and the bars still look wrong (i.e., they grow downward from the top), the underlying issue is strip-wiring orientation, not the effect — and the fix belongs in the setup (per-strip direction), not in Spectral Glow.

Also add a `gain` param (0.1–5.0, default 1.0) that multiplies the band values before computing `fill_heights`.

### Gain Semantics Per Effect Type

Codex flagged that `gain` has different meanings depending on whether an effect is driven by continuous (bass/mid/high) or trigger (beat/drop) signals. We document this per effect rather than trying to unify the meaning:

| Effect | Gain meaning |
|--------|-------------|
| Spectrum, Spectrogram, Bass Fire, Sound Worm, Sound Plasma, Sound Ripples, Spectral Glow, Energy Ring | Continuous sensitivity (multiplier on band/level values) |
| Beat Pulse, Particle Burst, Strobe Chaos, VU Meter | Response amplitude (multiplier on flash intensity or burst count) |
| SR Feldstein, SR Lava Lamp, SR Matrix Rain, SR Moire, SR Flow Field | Continuous sensitivity (multiplier on audio-driven modulations) |

All use the same param name `gain` with range 0.1–5.0. UI is consistent; behavior varies per effect.

### Gain Audit Table

Verify/add gain to each sound-reactive effect:

| Effect | File | Has gain? | Action |
|--------|------|-----------|--------|
| Spectrum | sound.py | Yes | — |
| VU Meter | sound.py | Verify | Add if missing |
| Beat Pulse | sound.py | Verify | Add if missing |
| Bass Fire | sound.py | Yes | — |
| Sound Ripples | sound.py | Verify | Add if missing |
| Spectrogram | sound.py | Yes | — |
| Sound Worm | sound.py | Verify | Add if missing |
| Particle Burst | sound.py | Verify | Add if missing |
| Sound Plasma | sound.py | Verify | Add if missing |
| Strobe Chaos | sound.py | Verify | Add if missing |
| Spectral Glow | audio_reactive.py | No | Add with fix |
| Energy Ring | audio_reactive.py | No | Add with rewrite |

### Files

**New:**
- `pi/app/effects/imported/sound_variants.py` — the 5 SR classes (all in one file; each is ~80-150 lines since it's a full fork of the base render loop with audio layered on)

**Modified:**
- `pi/app/effects/imported/__init__.py` — import `SOUND_VARIANTS_EFFECTS` and merge into `IMPORTED_EFFECTS`
- `pi/app/effects/audio_reactive.py` — fix Spectral Glow fade, rewrite Energy Ring, add gain to both
- `pi/app/effects/imported/sound.py` — add gain param to any sound effects that lack one

**No changes needed to `main.py`:** effects auto-register through `IMPORTED_EFFECTS`.

### Category / Catalog

All 5 new SR effects use `CATEGORY = "sound"` so they appear in the existing Sound filter alongside Spectrum, Spectrogram, etc. Each has `PALETTE_SUPPORT = True` so it gets the palette dropdown.

## Performance

All variants must sustain 60 FPS on Pi 4. Follow existing numpy-vectorized patterns. The main performance risks flagged by review:

- **SR Flow Field**: base is scalar per-particle with `cyl_noise` inside the loop (`ambient_b.py:344`). The SR variant does NOT spawn extra particles on beat — it only modulates existing particles' brightness and trail. This keeps the particle loop count bounded by the `particles` param (max 200 in the base).
- **SR Moire**: base is vectorized; safe.
- **SR Feldstein**: base uses 3 Perlin noise layers. Speed modulation doesn't add work. Safe.
- **SR Lava Lamp**: base is vectorized; blob count capped at 12 (the `_blob_seeds` array is precomputed). SR drop adds up to 4 blobs, still within 12. Safe.
- **SR Matrix Rain**: base is vectorized with fixed 200-drop pool. Spawn rate spike is bounded by the pool capacity. Safe.

## Not In Scope

- Rewriting existing sound effects' audio behavior beyond the 2 bug fixes
- Adding new audio features to `AudioCompatAdapter`
- Vectorizing Flow Field's particle loop (separate performance task)
- UI changes for browsing effects
