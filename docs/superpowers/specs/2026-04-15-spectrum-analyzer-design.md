# Spectrum Analyzer & Per-Band Sensitivity

## Goal

Add a live spectrum analyzer to the Sound tab and replace global sensitivity with per-band (bass/mid/treble) sensitivity controls. Bass is currently over-sensitive and treble under-responsive — per-band control fixes this.

## Current State

- `AudioAnalyzer` does 2048-point FFT, extracts 3 bands (bass 20–250 Hz, mid 250–4000 Hz, high 4000–16000 Hz) with smoothing (α=0.85)
- WebSocket broadcast includes `audio_level` and `audio_beat` but NOT `audio_bass`, `audio_mid`, `audio_high`
- Frontend has 3 meter bars in HTML/CSS but **no JS updates them** — they're permanently at 0%
- Global sensitivity and gain sliders exist and work (single multiplier)
- Sound-reactive effects read `state.audio_bass/mid/high` from `RenderState` — this works

## Design

### Layout (Option B — Spectrum Replaces Meters)

The 3 static meter bars are replaced with:

1. **Spectrum analyzer** — 16 vertical bars, color-coded by band region:
   - Bars 0–3: Bass (red `#c0392b`)
   - Bars 4–9: Mid (green `#2ecc71`)
   - Bars 10–15: Treble (purple `#9b59b6`)
   - Labels "BASS", "MID", "TREBLE" above each region
   - Frequency labels below: 20 Hz, 250, 4k, 16k Hz
   - Canvas element, ~140px tall

2. **Per-band sensitivity sliders** — directly below spectrum, proportionally sized to match band widths:
   - Bass slider (flex: 3) — range 10–300%, default 100%
   - Mid slider (flex: 5) — range 10–300%, default 100%
   - Treble slider (flex: 4) — range 10–300%, default 100%
   - Each shows current percentage value
   - Color-matched to band region

3. **Beat indicator** — small pulsing dot, flashes on beat detection

4. **Removed**: Global sensitivity slider (replaced by per-band), 3 meter bars

5. **Kept**: Gain slider (hardware input level), device selector, start/stop buttons

### Backend: AudioAnalyzer Changes

**New properties** on `AudioAnalyzer`:
- `bass_sensitivity: float = 1.0` (range 0.1–3.0)
- `mid_sensitivity: float = 1.0` (range 0.1–3.0)
- `treble_sensitivity: float = 1.0` (range 0.1–3.0)

**Applied in `_audio_callback`** after FFT band extraction, before smoothing:
```
raw_bass *= self.bass_sensitivity
raw_mid *= self.mid_sensitivity
raw_high *= self.treble_sensitivity
```

This means per-band sensitivity affects both the visualization AND sound-reactive effects (they read the same smoothed values via RenderState).

**New snapshot field**: `spectrum` — array of 16 float values (0.0–1.0), one per FFT display bin. Bins are log-spaced to match perceptual frequency distribution. Per-band sensitivity is applied to spectrum bins too (bins in bass range multiplied by bass_sensitivity, etc.).

**Bin frequency mapping** (log-spaced, 16 bins across 20–16000 Hz):
- Bins 0–3: ~20–250 Hz (bass)
- Bins 4–9: ~250–4000 Hz (mid)
- Bins 10–15: ~4000–16000 Hz (treble)

### Backend: RenderState Changes

Add to `RenderState.to_dict()`:
- `audio_bass` — smoothed bass level (already a property, just not serialized)
- `audio_mid` — smoothed mid level (same)
- `audio_high` — smoothed high level (same)
- `audio_spectrum` — 16-element list of floats

These get broadcast via WebSocket every 0.5s (existing periodic broadcast).

### Backend: Audio Config API

Extend `POST /api/audio/config` to accept:
```json
{
  "bass_sensitivity": 0.4,
  "mid_sensitivity": 0.7,
  "treble_sensitivity": 1.5
}
```

Extend `AudioConfigRequest` schema with 3 optional float fields.

Persist band sensitivities in `state.json` via `StateManager`. Restore on startup.

### Frontend: Spectrum Visualizer

**Implementation**: Canvas element (not DOM bars) for performance.

**Update loop**:
- WebSocket delivers spectrum data at 2 Hz (server broadcast rate)
- Client-side interpolation smooths between updates for fluid animation
- `requestAnimationFrame` drives rendering at display refresh rate
- Each bar lerps toward target value with decay factor

**Bar rendering**:
- 16 bars with 2px gap between each
- Gradient fill: darker at base, brighter at peak
- Rounded top corners
- Bar height = bin magnitude × canvas height

### Frontend: Sensitivity Sliders

Three range inputs styled to match existing app sliders:
- Debounced 100ms, send `POST /api/audio/config` with all 3 values
- Display percentage value next to each
- Color-coded labels matching spectrum regions

### State Persistence

Band sensitivities saved in `state.json` under dedicated keys:
- `audio_bass_sensitivity`
- `audio_mid_sensitivity`
- `audio_treble_sensitivity`

Loaded on startup, passed to AudioAnalyzer before `start()`.

Frontend loads current values from a new `GET /api/audio/config` endpoint (or extend existing device list response).

## Files Changed

- `pi/app/audio/analyzer.py` — per-band sensitivity, spectrum bins, snapshot
- `pi/app/core/renderer.py` — add spectrum + band levels to `RenderState.to_dict()`
- `pi/app/api/routes/audio.py` — extend config endpoint, add config GET
- `pi/app/api/schemas.py` — extend `AudioConfigRequest`
- `pi/app/core/state.py` — persist band sensitivities (use existing properties pattern)
- `pi/app/main.py` — restore band sensitivities on startup
- `pi/app/ui/static/index.html` — replace meter bars with canvas + sliders
- `pi/app/ui/static/js/app.js` — spectrum renderer, slider wiring, WebSocket handler
- `pi/app/ui/static/css/app.css` — remove meter bar styles, add spectrum styles

## Not In Scope

- Adjustable FFT size or bin count (16 bins is fixed)
- Peak hold indicators (can add later)
- Waveform view (oscilloscope mode)
- Per-effect audio sensitivity overrides
