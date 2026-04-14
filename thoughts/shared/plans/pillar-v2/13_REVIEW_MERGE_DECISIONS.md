# 13 — Review Merge Decisions

This document records what was accepted, corrected, or rejected when merging the uploaded review docs with the prior audited packet.

## 1. Accepted from the review docs

| Accepted item | Why it stayed |
|---|---|
| Setup under `System` | matches user request and current UI constraints |
| shared camera wizard concept | good frontend reuse idea |
| per-feature acceptance criteria style | makes implementation easier to verify |
| logical-frame browser simulator concept | correct SSOT direction |
| strip inventory UI | required for manual fallback |
| tooltips and explicit labels | directly answers the UI complaint |

## 2. Corrected

| Review-doc idea | Final correction |
|---|---|
| setup writes into `hardware.yaml` | moved to `installation.yaml` |
| handwritten swizzle tables | replaced with permutation simulation |
| plain-HTTP camera optimism | replaced with secure-context prerequisite |
| one-camera “actual physical coordinates” | replaced with honest front-projection coordinates |
| using existing `/ws` for simulator frames | replaced with dedicated preview websocket |
| “no backend changes” for tooltips | corrected to include catalog/compat work |
| “no new infrastructure needed” for imported effects | corrected to require audio adapter and metadata service |

## 3. Rejected

| Rejected item | Reason |
|---|---|
| treating DotStar as a supported strip choice | false on current output path |
| brute-force dense 1720-point scan as the default geometry flow | fragile and slower than anchor-fit-first |
| relying only on docstrings for descriptions | too brittle for imported effects |
| frontend-only CV as the only analysis path | harder to test and maintain on this repo |

## 4. Repo-specific corrections applied

| Correction | Why |
|---|---|
| UI HTML path normalized to `pi/app/ui/static/index.html` | current repo path |
| current state websocket left JSON-only | current frontend depends on it |
| `AppDeps` / `create_app` wiring called out explicitly | current repo uses manual dependency wiring |
| `StateManager` atomic-write pattern reused | existing safe pattern |
| electrical `344` vs physical `172` guarded explicitly | current firmware/config distinction |

## 5. Final design stance

The review docs were strongest on:

- task slicing
- acceptance checklists
- frontend UX detail

The prior audited packet was stronger on:

- repo truth
- SSOT boundaries
- protocol and firmware limits
- imported-effect realism

The final packet keeps the strengths of both and removes the parts most likely to cause rework.
