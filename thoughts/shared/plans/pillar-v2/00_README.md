# Pillar Controller — Final Opus Packet

This packet merges:

- the prior audited packet work
- the uploaded review set
- the uploaded `led_sim.py` source inventory
- repo-specific build-safety corrections

It is written for direct use by Opus against the current `baybrewer/pillar-controller` repo.

## Packet goals

| Goal | Included |
|---|---|
| Per-strip color order, LED count, and chipset setup | Yes |
| `System > Setup` subpage | Yes |
| Camera-assisted RGB-order commissioning | Yes |
| Camera-assisted geometry mapping | Yes |
| Imported `led_sim.py` effect integration | Yes |
| Web simulator and preview transport | Yes |
| UI clarity and tooltips | Yes |
| DRY / SSOT config boundaries | Yes |
| Repo-specific build-safety guidance | Yes |
| Phased implementation order with gates | Yes |

## Merge rule used

Where the uploaded review docs and repo reality disagreed, this packet chooses **repo-truth first** so the implementation does not start from false assumptions.

## Three hard truths

| Topic | Decision |
|---|---|
| Phone camera access | Treat secure context as mandatory for browser camera setup. Keep a manual fallback. |
| DotStar / APA102 | Explicitly unsupported on the current OctoWS2811 output path. |
| Single fixed camera mapping | Store honest front-projection geometry, not pretend 360° reconstruction. |

## Read this packet in order

| Order | File | Purpose |
|---|---:|---|
| 1 | `MASTER_SPEC.md` | One-file executive implementation brief |
| 2 | `01_REPO_TRUTH_AND_GUARDRAILS.md` | Current repo behavior and non-negotiables |
| 3 | `02_SSOT_AND_CONFIGURATION.md` | Mutable vs immutable configuration boundaries |
| 4 | `03_OUTPUT_COMPILER_AND_PROTOCOL.md` | Runtime packer, swizzle logic, protocol rules |
| 5 | `04_SETUP_SUBSYSTEM_AND_APIS.md` | Setup session model, routes, schemas |
| 6 | `05_CAMERA_RGB_ORDER_WIZARD.md` | RGB-order wizard behavior and analysis |
| 7 | `06_CAMERA_GEOMETRY_WIZARD.md` | Geometry mapping behavior and storage |
| 8 | `07_EFFECT_CATALOG_AND_UI_POLISH.md` | Catalog API, labels, tooltips, mobile UX |
| 9 | `08_IMPORTED_ANIMATIONS_AND_AUDIO_ADAPTER.md` | `led_sim.py` port plan and audio contract |
| 10 | `09_WEB_SIMULATOR_AND_PREVIEW.md` | Simulator transport, preview lifecycle |
| 11 | `10_BUILD_SAFETY_CHECKLIST.md` | Path/signature/compat traps to avoid |
| 12 | `11_TEST_PLAN_AND_ACCEPTANCE.md` | Tests, parity gates, acceptance criteria |
| 13 | `12_IMPLEMENTATION_SEQUENCE.md` | Concrete phase order and file touchpoints |
| 14 | `13_REVIEW_MERGE_DECISIONS.md` | What was accepted, corrected, or rejected |
| 15 | `14_EFFECT_INVENTORY.md` | Imported effect catalog and dependency batches |
| 16 | `15_OPUS_EXECUTION_PROMPT.md` | Final prompt to feed into Opus |
| 17 | `16_MANIFEST.md` | File list and line counts |

## What changed versus the review docs

| Area | Final packet stance |
|---|---|
| Runtime mutable config | Use `installation.yaml`, not direct setup writes into `hardware.yaml` |
| Color-order baseline | Normalize on current BGR live path, then remove stale GRB remnants |
| RGB swizzle logic | Compute permutations from controller-order × strip-order composition, not brittle handwritten tables |
| Camera CV location | Browser captures stills; backend scores and solves with Pillow/NumPy |
| Geometry default | Use anchor-fit first, dense scan only as fallback |
| Web simulator transport | Dedicated preview WebSocket, not the existing global `/ws` |
| Imported sound effects | Gated on a real audio adapter and band model, not “drop-in” |

## Deliverable standard

Do not create duplicate editable truths for:

- strip metadata
- controller profile
- mapping rules
- effect metadata
- preview frame metadata
- imported audio adapter fields

Every markdown file in this packet stays under 1000 lines.
