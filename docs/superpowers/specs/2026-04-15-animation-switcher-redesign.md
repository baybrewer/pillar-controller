# Animation Switcher Redesign

## Goal

Transform the Animation Switcher into a true "set and forget" feature: configurable interval 5–120s, checkbox selection of effects to include in rotation, with all sound-reactive effects labeled "SR " and grouped together (alphabetical within each group).

## Problem Statement

The existing Animation Switcher is a working effect that cycles through a playlist at a configurable interval with cross-fade. However:
- **No UI for selecting the playlist** — the `playlist` param exists but can only be set via raw API calls
- **Interval capped at 60s** — user wants up to 120s
- **Inconsistent SR labeling** — only the 5 new variants have "SR " prefix; the 10 existing sound.py effects (Spectrum, Bass Fire, Spectrogram, etc.) and the 5 audio_reactive built-ins don't
- **Persistence** — playlist selection currently lives in effect params which get wiped/overridden
- **Discoverability** — no visual grouping; sound-reactive effects are scattered across "sound" category but not clearly marked

## Design

### 1. Relabel All Sound-Reactive Effects with "SR " Prefix

Every sound-reactive effect gets its DISPLAY_NAME prefixed with "SR ":

| Current Name | File | New Name |
|--------------|------|----------|
| Spectrum | sound.py | SR Spectrum |
| VU Meter | sound.py | SR VU Meter |
| Beat Pulse | sound.py | SR Beat Pulse |
| Bass Fire | sound.py | SR Bass Fire |
| Sound Ripples | sound.py | SR Sound Ripples |
| Spectrogram | sound.py | SR Spectrogram |
| Sound Worm | sound.py | SR Sound Worm |
| Particle Burst | sound.py | SR Particle Burst |
| Sound Plasma | sound.py | SR Sound Plasma |
| Strobe Chaos | sound.py | SR Strobe Chaos |
| (VU Pulse / Band Colors / Beat Flash / Energy Ring / Spectral Glow) | audio_reactive.py | SR prefix via catalog label override |
| SR Feldstein, SR Lava Lamp, SR Matrix Rain, SR Moire, SR Flow Field | sound_variants.py | Already prefixed — no change |

The catalog label ("Spectrum" vs "SR Spectrum") is what UI shows. The effect `name` (internal ID like `spectrum`) stays the same to preserve state.json compatibility.

**Scope limiter:** Only rename the user-facing label. Internal effect names, class names, file organization stay unchanged.

### 2. Extend Switcher Interval Range

Change max from 60s to 120s in the catalog param registration in `pi/app/main.py`:

```python
{'name': 'interval', 'label': 'Switch Time (s)', 'min': 5, 'max': 120, 'step': 1, 'default': 15, 'type': 'slider'},
```

### 3. Add Effect-Selection UI to Switcher Controls

When Animation Switcher is the active effect, below the interval/fade sliders, render a checkbox list of **every activatable effect** (excluding `animation_switcher` itself and diagnostic effects).

**Two sections, alphabetically sorted within each:**

```
🎵 Sound Reactive
  ☐ SR Bass Fire
  ☐ SR Beat Flash
  ☐ SR Beat Pulse
  ☐ SR Energy Ring
  ☐ SR Feldstein
  ☐ SR Flow Field
  ☐ SR Lava Lamp
  ☐ SR Matrix Rain
  ☐ SR Moire
  ☐ SR Particle Burst
  ☐ SR Sound Plasma
  ☐ SR Sound Ripples
  ☐ SR Sound Worm
  ☐ SR Spectral Glow
  ☐ SR Spectrogram
  ☐ SR Spectrum
  ☐ SR Strobe Chaos
  ☐ SR VU Meter
  ☐ SR VU Pulse
  ☐ SR Band Colors
  [Select All] [Clear]

🎨 Other
  ☐ Aurora Borealis
  ☐ Brett's Favorite
  ☐ Breathing
  ☐ Color Wipe
  ☐ Cylinder Rotate
  ☐ Feldstein Equation
  ☐ Feldstein OG
  ☐ Fire
  ☐ Fireflies
  ☐ Fireplace
  ☐ Flow Field
  ☐ Kaleidoscope
  ☐ Lava Lamp
  ☐ Matrix Rain
  ☐ Moire
  ☐ Nebula
  ☐ Noise Wash
  ☐ Ocean Waves
  ☐ Plasma (generative)
  ☐ Plasma (imported)
  ☐ Rainbow Cycle
  ☐ Rainbow Rotate
  ☐ Scanline
  ☐ Seam Pulse
  ☐ Sine Bands
  ☐ Solid Color
  ☐ Spark
  ☐ Starfield
  ☐ Twinkle
  ☐ Vertical Gradient
  [Select All] [Clear]
```

**Classification rule:** An effect is "Sound Reactive" if its group is `'sound'` OR `'audio'` in the catalog. Everything else goes to "Other" (excluding `animation_switcher` itself and `diagnostic`).

### 4. Checkbox Interaction

Each checkbox toggle debounces 300ms then POSTs to `/api/scenes/activate` with effect=`animation_switcher` and params including the updated `playlist` array. This follows the existing pattern for param updates.

When the playlist changes, the switcher effect is already running — `Renderer._set_scene` detects the scene is already active and calls `update_params()` which updates the playlist in place. The switcher handles runtime playlist changes via its `_apply_params` method.

**Default playlist:** If `playlist` is empty, the switcher cycles through *everything* selected (empty = all enabled). The UI shows nothing checked initially; clicking checkboxes populates. Actually — to avoid confusion, if no playlist is provided on first activation, the switcher falls back to a sensible default (everything except diagnostics).

Decision: **empty playlist param → switcher uses all non-diagnostic effects**. User explicitly selects to narrow down.

### 5. Switcher Backend Changes

The existing switcher already accepts `playlist` in params. The only needed change is:

**In `pi/app/effects/switcher.py`:** When playlist is empty/missing, fall back to all non-diagnostic effects from the effect_registry.

```python
def _apply_params(self, params: dict):
  new_playlist = params.get('playlist', [])
  if not new_playlist and self._effect_registry:
    # Default: all effects except self and diagnostics
    new_playlist = [
      name for name in sorted(self._effect_registry.keys())
      if name != 'animation_switcher' and not name.startswith('diag_')
    ]
  self._playlist = new_playlist
  # ... existing interval/fade handling
```

### 6. Persistence (Automatic via Existing Mechanism)

The per-effect-params persistence from the previous session (state_manager.set_effect_params) already handles this. When the user checks/unchecks boxes, the `playlist` param in `animation_switcher`'s stored params updates and survives restarts.

No new persistence code needed.

### 7. Status Display (Minimal — "Now Playing")

Show the currently playing effect name and time until next switch below the effect checkboxes. Polls `/api/scenes/switcher/status` every 2 seconds while Animation Switcher is the active effect.

Format:
```
Now playing: SR Matrix Rain — switching in 8s
```

Keep it to one line; don't show "next" effect (it's cross-faded already when next=known).

### 8. Files Changed

| File | Change |
|------|--------|
| `pi/app/effects/imported/sound.py` | Add "SR " prefix to 10 DISPLAY_NAMEs |
| `pi/app/effects/audio_reactive.py` | No DISPLAY_NAME on classes (catalog uses label) — add SR labels in main.py |
| `pi/app/main.py` | Bump switcher interval max to 120; override labels for audio_reactive effects with "SR " prefix |
| `pi/app/effects/switcher.py` | Default playlist to all non-diagnostic if empty |
| `pi/app/ui/static/index.html` | Add switcher-controls container below effect-params |
| `pi/app/ui/static/js/app.js` | Render checkbox list when Animation Switcher active; poll status; wire checkboxes to POST activate |
| `pi/app/ui/static/css/app.css` | Styles for switcher section, section headers, checkbox rows, Select All / Clear buttons |

### 9. Removed or Deprecated

Nothing removed. All existing effects keep their internal names. Only user-visible labels change.

## Non-Goals

- No playlist order customization (alphabetical within SR and Other sections, cycled in order)
- No per-effect params override in playlist (each effect uses its own last-known params)
- No drag-and-drop reordering
- No save/load named playlists (the single selected set persists automatically)
- No preview/audition mode separate from activating the switcher
- No UI changes outside the Animation Switcher's controls panel

## Performance

Trivial impact. The checkbox rendering is a one-time list of ~35 effects. Status polling every 2s is negligible. The actual rotation/cross-fade code is unchanged.

## Testing

Tests to add:
1. Switcher with empty playlist activates without crashing (uses default all-non-diag)
2. Playlist param change at runtime (via `update_params`) rebuilds the rotation without reset
3. Status endpoint returns correct shape when switcher is active
4. Catalog labels reflect "SR " prefix on sound-reactive effects
