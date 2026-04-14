# 06 — Camera Geometry Wizard

This wizard learns the visible front-projection layout of the strips and LEDs.

## 1. Scope

This is **front-projection calibration**, not full 360° geometry recovery.

Use it for:

- simulator alignment
- preview overlays
- geometry-aware effects
- installation validation

Do not market it as true cylindrical reconstruction.

## 2. Correct v1 strategy

Use **anchor-fit first**.

Do not default to a blind 1720-point dense scan.

### Recommended sequence

1. capture a dark frame
2. identify visible strip ROIs using whole-strip or base-anchor lighting
3. confirm strip-to-ROI identity in UI
4. light anchors at `0, 25, 50, 75, 100%` per visible strip
5. fit a centerline or polyline for each visible strip
6. interpolate intermediate LED positions
7. validate with sampled LEDs
8. dense-scan only strips that fail validation

## 3. Why anchor-fit first is better

| Benefit | Why it matters |
|---|---|
| fewer captures | faster wizard |
| lower motion sensitivity | easier on phone camera setup |
| better explainability | user can see anchor hits and validation |
| enough for strip-based installs | the pillar topology is already known |

## 4. Geometry storage model

Store one optional `spatial_map.json` front-projection profile and reference it from `installation.yaml`.

### Coordinate model

- normalized UV in image space
- origin at bottom-left for consistency with LED row 0 = bottom
- per-strip positions ordered by physical LED index
- visibility status per strip

### What not to store as truth

Do not overwrite canonical cylindrical order.

Projection coordinates are an additional geometry view.

## 5. Browser/backend split

| Browser | Backend |
|---|---|
| preview camera | detect blobs and centroids |
| capture stills | solve centerlines and interpolation |
| render overlays | validate fit quality |
| confirm strip IDs | persist solved map |

Use still snapshots or short burst captures. No custom streaming CV pipeline in v1.

## 6. Suggested API surface

### Analyze anchors

```text
POST /api/setup/geometry/analyze
multipart/form-data:
- session_id
- phase: "identify" | "anchors" | "validate"
- frame_001..frame_n
- expected_lit_points metadata
```

### Solve final map

```text
POST /api/setup/geometry/solve
json:
- session_id
- confirmed_strip_rois
- anchor_observations
- validation_observations
```

### Save final map

```text
POST /api/setup/spatial-map
json:
- profile_id
- geometry_mode
- solved map payload
```

## 7. Solver rules

### 7.1 Visible strip identification

- start by lighting one anchor per visible strip
- cluster bright regions into candidate strip ROIs
- ask the user to confirm strip-to-ROI mapping if ambiguity exists

### 7.2 Anchor fit

For each strip:

- detect the 5 anchor centroids
- fit a line or polyline through anchors
- interpolate all LEDs along that fit using installed LED count
- mark fit quality

### 7.3 Validation

Light sampled LEDs on the fitted strip:

- compare observed centroids to predicted positions
- compute mean error and max error
- if within tolerance, accept
- otherwise escalate that strip to a denser scan

### 7.4 Dense fallback

Only for strips with poor validation:

- light a smaller sampled set first
- only go full dense scan if sampled fallback still fails

## 8. Geometry use in the runtime

### 8.1 What changes immediately

Available immediately after calibration:

- simulator overlay
- preview alignment
- geometry-aware imported effects
- optional future projection-aware helpers

### 8.2 What stays canonical for legacy safety

Legacy effects continue to render against canonical unwrap unless explicitly updated to use geometry coordinates.

This avoids breaking current effects just to satisfy projection accuracy.

## 9. UI rules

| Rule | Purpose |
|---|---|
| require phone stability check before capture | reduce bad solves |
| show ROI and anchor overlays | help user trust the fit |
| allow strip-by-strip retry | avoid rerunning everything |
| show visibility status | be honest about hidden/back strips |

## 10. Failure handling

| Failure | Handling |
|---|---|
| hidden strips not visible | keep canonical order for those strips |
| poor fit | retry anchors or run dense fallback for that strip |
| motion during capture | reject current step and retry |
| inconsistent validation | do not save until user resolves |

## 11. Tests

Add tests for:

- strip ROI detection from synthetic images
- anchor interpolation math
- validation error thresholds
- hidden-strip fallback behavior
- spatial map schema load/save
- geometry mode switching in installation config

## 12. Done criteria

- wizard produces a saved front-projection map for visible strips
- hidden strips are handled honestly
- anchor-fit path is the default
- dense scan is only a fallback
- the spatial map is available to preview and effect code without replacing canonical install truth
