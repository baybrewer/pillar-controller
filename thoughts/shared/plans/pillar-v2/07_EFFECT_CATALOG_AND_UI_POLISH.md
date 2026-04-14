# 07 — Effect Catalog and UI Polish

This document merges the good UI detail from the review docs with repo-safe API design.

## 1. Current frontend constraint

The current UI:

- loads effects from `/api/scenes/list`
- splits audio vs non-audio in JS
- skips diagnostics by `diag_` prefix
- serves HTML from `pi/app/ui/static/index.html`

Do not break that accidentally.

## 2. Final metadata model

Introduce a catalog service as the new metadata source.

### 2.1 Metadata object

```python
@dataclass(frozen=True)
class EffectMeta:
    name: str
    label: str
    group: str              # generative | audio | diagnostic | imported
    description: str
    preview_supported: bool
    imported: bool
    geometry_aware: bool
    audio_requires: list[str]
    default_params: dict
```

### 2.2 Metadata source of truth

Use this precedence:

1. explicit `EFFECT_META` or central catalog registry
2. first line of class docstring
3. sane generated fallback from effect name

Do not rely on docstrings alone because many imported effects do not have them.

## 3. Route strategy

### 3.1 New richer route

Add `pi/app/api/routes/effects.py`:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/effects/catalog` | rich metadata for UI and preview |
| `GET` | `/api/effects/{name}` | metadata for one effect |

### 3.2 Compatibility route

Keep `/api/scenes/list` working during migration.

It should return the current shape, but with richer values where safe:

```json
{
  "effects": {
    "fire": {
      "type": "generative",
      "description": "Realistic fire simulation",
      "preview_supported": true
    }
  },
  "current": "fire"
}
```

Do not break the current `app.js` expectation that `effects` is a name-keyed object.

## 4. UI corrections

### 4.1 Critical controls

Replace cryptic critical controls with explicit labels:

| Current | Final |
|---|---|
| `B` | `Blackout` |
| `R` | `Resume` |

The current hover titles are not enough because the target device is a phone.

### 4.2 Tooltips

Implement `data-tooltip` + long-press touch tooltip + native `title`.

Rules:

- desktop hover uses `title`
- mobile long-press uses the custom tooltip
- tooltips must not trigger the underlying action
- keep tooltip text sourced from metadata where possible

### 4.3 Setup entry point

Inside `System`, add a clear `Setup` subnav item or button.

Do not create a seventh crowded top-level tab for setup.

### 4.4 Simulator tab

A `Sim` top-level tab is acceptable because it is an end-user preview surface and separate from system setup.

## 5. Catalog-backed frontend behavior

The frontend should stop inferring everything from name prefixes alone.

Add a compatibility phase:

1. fetch `/api/effects/catalog` when available
2. fall back to `/api/scenes/list` legacy shape if needed
3. retain current grouping behavior only as fallback

## 6. Suggested tooltip map

| Area | Example tooltip |
|---|---|
| Blackout | “Turn all LEDs off immediately” |
| Resume | “Restore live output after blackout” |
| Setup | “Configure strip count, color order, and mapping” |
| RGB Order Wizard | “Use camera-assisted strip color-order detection” |
| Geometry Wizard | “Map visible strip positions from a fixed camera view” |
| Preview | “See effect behavior without changing live LEDs” |

## 7. Additional polish

- add toast notifications for apply/save actions
- add active-effect label text instead of glow-only state
- add better confirmation text for reboot/restart
- keep controls touch-sized and mobile-first

## 8. File touchpoints

| File | Change |
|---|---|
| `pi/app/ui/static/index.html` | labels, setup navigation, sim tab, tooltip hooks |
| `pi/app/ui/static/js/app.js` | catalog consumption, tooltip behavior, sim lifecycle |
| `pi/app/ui/static/css/app.css` | tooltip, toast, setup, sim styles |
| `pi/app/api/routes/scenes.py` | compatibility route improvements |
| new `pi/app/api/routes/effects.py` | rich catalog route |
| `pi/app/main.py` | register metadata-backed imported effects |

## 9. Done criteria

- no critical single-letter mystery controls remain
- mobile tooltip behavior exists
- `/api/scenes/list` keeps the current frontend alive
- richer catalog metadata is available for the new UI flows
