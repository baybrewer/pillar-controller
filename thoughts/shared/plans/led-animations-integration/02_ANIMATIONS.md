# Phase 2 — Port All 27 Animations

## Goal

Port every animation class from `led_sim.py` as a repo-native `Effect` subclass. Each animation uses `LEDBuffer` + engine modules, no Pygame.

## File layout

```
pi/app/effects/
  imported/
    __init__.py          # registers all ported effects into ALL three surfaces
    classic.py           # 5 classic animations
    ambient.py           # 12 ambient animations
    sound.py             # 10 sound-reactive animations
```

## Critical: Triple registration

Imported effects must be registered in **all three surfaces** or they'll be invisible:

1. **`renderer.effect_registry`** — so `activate_scene()` works
2. **`EffectCatalogService`** — so `/api/effects/catalog` and `/api/scenes/list` include them
3. **`PreviewService` lookup** — currently hardcoded to `EFFECTS + AUDIO_EFFECTS`

**Fix in Phase 2:**
- `imported/__init__.py` exports `IMPORTED_EFFECTS = {name: class}` dict
- `main.py` registers all into renderer
- `main.py` registers metadata into catalog service
- `PreviewService.start()` must be updated to also check `IMPORTED_EFFECTS`
  (or better: look up from `renderer.effect_registry` instead of hardcoded dicts)

## Critical: AudioCompatAdapter injection

The current render path passes raw `RenderState` to `effect.render(t, state)`.
Sound-reactive imported effects need the richer `AudioSnapshot` surface (`bands`, `beat_energy`, `drop`, `is_phrase`, etc.).

**Solution:** Each imported sound effect wraps the adapter internally:

```python
class ImportedSoundEffect(Effect):
    def __init__(self, ...):
        super().__init__(...)
        self._audio_adapter = AudioCompatAdapter()

    def render(self, t, state):
        # Adapt raw RenderState audio into rich snapshot
        raw = state._audio_lock_free
        audio = self._audio_adapter.adapt(raw, t)
        # Use audio.bands, audio.drop, etc.
        self._update(dt_ms, audio)
        return self.buf.get_frame()
```

This avoids modifying the renderer's core path.

## Critical: Audio adapter fixes needed before port

The adapter must match the source simulator's contract:

| Field | Source behavior | Current adapter | Fix needed |
|-------|----------------|-----------------|------------|
| `drop` | Boolean onset event (True for ~2-3s burst, then False) | Float accumulator (0-1) | Add `drop_event: bool` (onset trigger) alongside `drop: float` (intensity) |
| `_time` | Used by VUMeter/BeatPulse for breakdown sine | Not exposed | Add `_time` alias for `time_s` |
| `drop_intensity` | 0-1+ magnitude of drop | Not exposed | Add field |

## Critical: Stateful effects — no re-create on param change

Many effects maintain internal state (fire buffers, particle lists, trail buffers, scroll positions). The current renderer destroys and recreates the effect on every `activate_scene()` call.

**Solution:** Add `update_params(params)` method to Effect base class:

```python
class Effect(ABC):
    def update_params(self, params: dict):
        """Update parameters without resetting state. Override for custom behavior."""
        self.params.update(params)
```

The renderer checks if the active effect matches the requested effect name; if so, calls `update_params()` instead of re-creating.

The `/api/scenes/activate` route already sends `{effect, params}`. The renderer just needs:
```python
if scene_name == self.state.current_scene and self.current_effect:
    self.current_effect.update_params(merged)
    return True
```

## Adapter pattern (updated)

```python
class PortedEffect(Effect):
    CATEGORY = "imported_classic"
    DISPLAY_NAME = "Rainbow Cycle"
    DESCRIPTION = "Fills every LED with a single palette color that advances over time"
    PALETTE_SUPPORT = True
    PARAMS = [...]  # FROM THE ACTUAL SOURCE, not assumed

    def __init__(self, width=10, height=172, params=None):
        super().__init__(width, height, params)
        self.buf = LEDBuffer(width, height)
        self._last_t = None
        # Initialize from ACTUAL source defaults

    def render(self, t, state):
        if self._last_t is None:
            self._last_t = t
        dt_ms = max(0, (t - self._last_t) * 1000)
        self._last_t = t
        self._update(dt_ms, state)
        return self.buf.get_frame()

    def update_params(self, params):
        """Update without resetting internal state (fire buffer, particles, etc.)."""
        for key, val in params.items():
            if hasattr(self, key.upper()):
                setattr(self, key.upper(), val)
            elif key == 'palette' and self.PALETTE_SUPPORT:
                self._set_palette(val)
```

## Persistent framebuffer requirement

Several effects do NOT clear their buffer each frame — they fade or accumulate:
- `FlowField` — fades buffer by factor, draws particle trails
- `FeldsteinEquation` — accumulates into prior pixels
- `SoundRipples` — fades buffer
- `SoundWorm` — fades buffer
- `ParticleBurst` — fades buffer

The `LEDBuffer` class must support `fade(factor)` and `add_led()` (additive blending). The buffer must persist across frames — it is NOT cleared automatically.

Each effect decides whether to `clear()` or `fade()` at the start of its update.

## Classic animations — ACTUAL params from source

| Name | Actual params (from led_sim.py) | Palette |
|------|--------------------------------|---------|
| RainbowCycle | Speed (0.1-5.0, default 1.0) | Yes (standard 10) |
| FeldsteinEquation | Speed (0.1-3.0, default 0.6), Bar Speed (0.1-3.0, default 1.0) | Yes (standard 10) |
| Feldstein2 (OG) | Speed (0.1-3.0, default 1.0), Fade (10-200, default 40), Palette (0-16, default 0) — **CUSTOM 17-entry palette system, NOT standard 10** | Custom (17 named Feldstein palettes) |
| BrettsFavorite | Speed (0.2-5.0, default 1.0), Bands (4-32, default 12), Damping (0.80-0.99, default 0.95) | Yes (standard 10) |
| Fireplace | **16 params:** FUEL (0-1, 0.65), SPARK_ZONE (0.05-0.5, 0.18), SPARK_PROB (0-1, 0.55), COOL_BASE (0-1, 0.28), COOL_HEIGHT (0-1, 0.6), COOL_NOISE (0-0.5, 0.12), DIFFUSE_CENTER (0-1, 0.65), DIFFUSE_SIDE (0-0.5, 0.15), TURB_X_SCALE (0-1, 0.3), TURB_Y_BIAS (0-1, 0.35), TURB_Y_RANGE (0-0.5, 0.15), BUOYANCY (0-1, 0.4), NOISE_OCTAVES (1-4, 2), EMBER_RATE (0-1, 0.4), EMBER_BURST (0-1, 0.7), EMBER_SPREAD (0-1, 0.5) | Uses fire palette (special) |

## Ambient animations — ACTUAL params from source

| Name | Actual params | Default palette idx |
|------|--------------|-------------------|
| Plasma | Speed (0.1-5.0, 1.0), Scale (0.5-5.0, 2.0) | 0 (Rainbow) |
| Aurora | Speed (0.05-2.0, 0.4), Wave (0.2-3.0, 1.0), Bright (0.2-1.0, 0.9) | 0 (Rainbow) |
| LavaLamp | Speed (0.1-3.0, 0.5), Blobs (2-12, 6), Size (0.3-3.0, 1.2) | 0 (Rainbow) |
| OceanWaves | Speed (0.1-3.0, 0.8), Depth (0.3-1.5, 0.7), Layers (1-5, 3) | **1 (Ocean)** |
| Starfield | Density (0.01-0.1, 0.03), Twinkle (0.5-5.0, 2.0), Speed (0.1-3.0, 0.5) | 0 (Rainbow) |
| MatrixRain | Speed (0.5-5.0, 2.0), Density (0.01-0.1, 0.04), Trail (0.8-0.99, 0.92) | **3 (Forest)** |
| Breathing | Speed (0.1-3.0, 0.5), Wave (0.1-2.0, 0.5) | 0 (Rainbow) |
| Fireflies | Count (3-60, 20), Speed (0.1-3.0, 1.0), Glow (1-5, 2) | 0 (Rainbow) |
| Nebula | Speed (0.05-1.0, 0.2), Scale (0.5-5.0, 2.0), Layers (1-3, 2) | **9 (Vapor)** |
| Kaleidoscope | Speed (0.1-3.0, 0.5), Segments (3-12, 6), Zoom (0.5-3.0, 1.0) | 0 (Rainbow) |
| FlowField | Speed (0.1-3.0, 0.8), Particles (10-200, 80), Fade (0.80-0.99, 0.95), Noise Scale (0.5-5.0, 2.0) | 0 (Rainbow) |
| Moire | Speed (0.1-3.0, 0.5), Scale (0.5-5.0, 2.0), Centers (2-5, 3) | 0 (Rainbow) |

## Sound-reactive animations — ACTUAL params and audio deps

| Name | Actual params | Audio fields used | Default palette |
|------|--------------|------------------|----------------|
| Spectrum | Gain (0.5-5.0, 2.0), Decay (0.5-0.99, 0.92) | bands, drop, buildup | 0 |
| VUMeter | Gain (0.5-5.0, 2.5), Decay (0.5-0.99, 0.9) | volume, buildup, breakdown, drop, **_time** | 0 |
| BeatPulse | Decay (0.8-0.99, 0.92), Flash (0.5-3.0, 1.5) | beat, drop, breakdown, **_time** | 0 |
| BassFire | Gain (0.5-5.0, 2.0), Base Spark (0.1-0.8, 0.3) | bands, bass, beat, beat_energy, drop, is_downbeat, is_phrase | fire palette |
| SoundRipples | Gain (0.5-5.0, 2.0), Speed (0.5-3.0, 1.5), Decay (0.9-0.99, 0.96), Sensitivity (0.1-1.0, 0.5) | bass, mids, highs, beat, beat_energy, is_downbeat, is_phrase | 0 |
| Spectrogram | Gain (0.5-5.0, 2.0), Scroll Speed (0.5-3.0, 1.0) | bands, buildup, drop | 0 |
| SoundWorm | Gain (0.5-5.0, 2.0), Speed (0.5-5.0, 2.0), Width (1-5, 2) | volume, buildup, drop | 0 |
| ParticleBurst | Gravity (0.1-2.0, 0.5), Speed (0.5-5.0, 2.0), Count (5-50, 20) | beat, buildup, breakdown, drop | 0 |
| SoundPlasma | Gain (0.5-5.0, 2.0), Base Speed (0.1-3.0, 0.8) | volume, buildup, breakdown, drop | 0 |
| StrobeChaos | Intensity (0.3-3.0, 1.0), Segments (1-10, 4) | beat, breakdown, drop | 0 |

## Registration in main.py

```python
from .effects.imported import IMPORTED_EFFECTS

# Register all imported effects
for name, cls in IMPORTED_EFFECTS.items():
    renderer.register_effect(name, cls)

# Register metadata in catalog
for name, cls in IMPORTED_EFFECTS.items():
    meta = EffectMeta(
        name=name, label=cls.DISPLAY_NAME, group=cls.CATEGORY,
        description=cls.DESCRIPTION,
        audio_requires=getattr(cls, 'AUDIO_REQUIRES', ()),
    )
    effect_catalog.register_imported(name, meta)
```

## Update PreviewService to use renderer registry

In `pi/app/preview/service.py`, change `start()` to look up from `renderer.effect_registry` instead of hardcoded `EFFECTS + AUDIO_EFFECTS`:

```python
def start(self, effect_name, ...):
    if effect_name not in self._renderer.effect_registry:
        raise ValueError(f"Unknown effect: {effect_name}")
    effect_cls = self._renderer.effect_registry[effect_name]
```

## Tests

- Every animation returns `(10, 172, 3)` uint8
- Time continuity: render 10 frames, no crash
- Palette switching works for palette-capable effects
- Param update via `update_params()` preserves state
- Sound animations degrade gracefully with zero audio
- Persistent-buffer effects produce visible trails after 10+ frames
- Fire has 16 controllable params
- Feldstein2 has 17 custom palettes

## Gate

- All 27 animations render without error
- Registered in all three surfaces (renderer, catalog, preview)
- Sound effects receive adapted audio via AudioCompatAdapter
- Param changes don't reset stateful animations
