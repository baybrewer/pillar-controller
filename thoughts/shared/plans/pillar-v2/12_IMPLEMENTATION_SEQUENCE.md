# 12 — Implementation Sequence

This is the exact phase order recommended for Opus.

## Phase 0a — Normalize truth before adding features

### Work

- clean stale GRB comments/fallbacks/docs
- add immutable `controller` block to `hardware.yaml`
- keep current BGR live path explicit
- sync `docs/current-contracts.md` and `docs/MASTER_SPEC.md`

### Touchpoints

- `pi/config/hardware.yaml`
- `pi/app/hardware_constants.py`
- `pi/app/mapping/cylinder.py`
- `docs/current-contracts.md`
- `docs/MASTER_SPEC.md`

### Gate

- no behavior change
- docs/comments/fallbacks agree on current live path

---

## Phase 0b — Add config boundary

### Work

- add `installation.yaml` schema, loader, migration, atomic writes
- add optional `spatial_map.json` loader
- extend `main.py` to load installation truth
- extend `AppDeps` with config services

### Gate

- fresh boot on old repo state synthesizes a legacy-parity installation profile

---

## Phase 0c — Add compiled runtime packer

### Work

- add `ControllerProfile`, `CompiledOutputPlan`, `CompiledStripPlan`
- add plan compiler and runtime mapper
- replace hardcoded render output shape
- keep legacy `cylinder.py` for parity testing only
- plumb compiled `channels` / `leds_per_channel` meta into transport

### Gate

- migrated default plan produces byte-identical output to old mapper

---

## Phase 1 — Add Setup subsystem

### Work

- add `SetupSessionService`
- add `routes/setup.py`
- add `System > Setup` UI shell
- add manual strip inventory editing
- add pattern runner and restore semantics

### Gate

- setup works manually without camera
- cancel restores prior live context

---

## Phase 2 — Add catalog metadata and UI cleanup

### Work

- add `EffectCatalogService`
- add `routes/effects.py`
- add `/api/scenes/list` compatibility enrichment
- replace critical cryptic labels
- add tooltip/toast/mobile help behavior

### Gate

- current Effects tab still works
- richer metadata exists
- no critical single-letter controls remain

---

## Phase 3 — Add audio adapter foundation

### Work

- add alias surface (`volume`, `mids`, `highs`)
- add `bands`
- add beat timing and advanced state
- make BPM meaningful

### Gate

- audio adapter tests pass
- sound-port dependency batches can be enforced

---

## Phase 4 — Add RGB-order wizard

### Work

- browser still capture + backend analysis
- ROI scoring and confidence gating
- per-strip results table and overrides
- apply through staged installation

### Gate

- confident detections auto-fill
- ambiguous detections remain manual-review items

---

## Phase 5 — Add geometry wizard

### Work

- fixed-camera stability check
- anchor-fit solver
- validation overlay
- dense fallback only for failed strips
- save `spatial_map.json`

### Gate

- visible strips solve cleanly
- hidden strips are handled honestly

---

## Phase 6 — Port imported effects

### Work

- port helper functions
- port batch B1 effects
- add metadata for all 27 imported effects
- port B2/B3 once audio adapter gates pass

### Gate

- B1 renders cleanly
- sound effects only ship when their dependencies are present

---

## Phase 7 — Add simulator and preview

### Work

- add `PreviewService`
- add `routes/preview.py`
- add preview websocket
- add Sim tab and canvas rendering
- allow preview without changing live LEDs

### Gate

- simulator previews real Python-rendered frames
- preview/live isolation is preserved

---

## Phase 8 — Final sync and hardening

### Work

- update repo docs
- update deploy/package assets for new config files
- rerun compileall + full tests
- verify phase gates

### Gate

- all tests pass
- docs reflect runtime truth
- packet deliverables are implemented without open contradictions
