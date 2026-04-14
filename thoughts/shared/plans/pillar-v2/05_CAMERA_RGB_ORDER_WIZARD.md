# 05 — Camera RGB-Order Wizard

This wizard detects strip-native color order using browser-captured still frames and backend scoring.

## 1. Honest prerequisites

| Requirement | Final stance |
|---|---|
| Secure context | mandatory for browser camera access |
| Manual fallback | mandatory |
| Camera compute location | browser captures; backend analyzes |
| Expected duration | about 20–30 seconds for 10 strips |

## 2. Why backend analysis wins here

The review docs pushed more CV into frontend JS.

For first-pass implementation on this repo, backend analysis is safer because it:

- keeps algorithms testable in Python
- avoids duplicating logic between browser and server
- works with simple still-image uploads
- avoids adding a custom browser CV stack

Use Pillow + NumPy. Do not require OpenCV for v1.

## 3. Wizard flow

For each strip:

1. ensure setup session exists
2. run setup pattern with all others black
3. capture a dark frame
4. show pure red with `use_compiled_color_order = false`
5. upload bright frame and dark frame
6. repeat for green and blue
7. backend returns:
   - observed dominant channels
   - candidate strip-native order
   - confidence
   - debug diagnostics
8. UI fills a results row
9. user can override any row before apply
10. apply only on explicit commit

## 4. Critical pattern rule

The wizard must be able to bypass runtime color compensation.

Otherwise the system will observe its own corrected output and detection becomes meaningless.

Required field:

```python
use_compiled_color_order: bool = False
```

During RGB detection, keep it false.

## 5. Request/response shape

### 5.1 Request

Use `multipart/form-data` with image blobs to avoid giant base64 JSON payloads.

```text
POST /api/setup/rgb-order/analyze
fields:
- session_id
- strip_id
- dark_frame
- red_frame
- green_frame
- blue_frame
- capture_width
- capture_height
```

### 5.2 Response

```json
{
  "strip_id": 3,
  "observed_sequence": ["B", "G", "R"],
  "candidate_color_order": "RGB",
  "confidence": 0.93,
  "status": "ok",
  "needs_manual_review": false,
  "debug": {
    "roi_area_px": 18422,
    "channel_separation": 0.81,
    "repeatability": 0.96
  }
}
```

## 6. Inference algorithm

### 6.1 Step A — isolate bright ROI

Given a dark frame and a lit frame:

- subtract dark from lit
- clamp negatives to zero
- threshold on brightness
- compute a bounding ROI around the bright strip
- reject if the ROI is too dim, too dispersed, or too large

### 6.2 Step B — measure dominant channel

Inside the ROI:

- average channel deltas
- determine dominant channel for the red, green, and blue test steps
- produce an observed sequence such as `["B", "G", "R"]`

### 6.3 Step C — infer candidate color order

Do not hardcode a static lookup table.

Instead:

1. read `controller.controller_wire_order`
2. for each candidate strip order:
   - simulate what observed sequence would result if raw RGB were sent through the current controller order into that strip-native order
3. choose the candidate whose predicted sequence matches the observed sequence

This reuses the same permutation simulator from the runtime swizzle tests.

## 7. Confidence gating

Auto-fill only when all of these pass:

| Check | Minimum |
|---|---|
| bright ROI found | yes |
| channel separation | high enough to avoid ties |
| per-phase repeatability | consistent across retake or secondary sample |
| candidate uniqueness | exactly one valid candidate |
| brightness above floor | yes |

If confidence is low:

- keep the current strip value selected
- mark the row as manual review
- allow one-tap retry

## 8. Frontend UX rules

| Rule | Reason |
|---|---|
| show live preview before start | user must confirm framing |
| show progress per strip | the routine is not instantaneous |
| show per-strip result rows | user needs override control |
| do not auto-commit | setup must remain reviewable |
| allow retry for one strip | avoids rerunning the full wizard |

## 9. Failure handling

| Failure | UI action |
|---|---|
| camera unavailable | show manual strip config only |
| secure-context failure | explain HTTPS requirement and stop camera flow |
| strip not visible | allow retry / skip |
| low confidence | keep current value and request manual review |
| session expired | restart setup session and restore live context cleanly |

## 10. Tests

Add automated tests for:

- dark-frame subtraction
- ROI extraction
- dominant-channel scoring
- candidate-order inference using the permutation simulator
- low-confidence fallback behavior
- regression that raw/identity mode bypasses compiled swizzle

## 11. Done criteria

- wizard works with backend-scored still captures
- ambiguous strips never auto-commit
- user can override every detected row
- setup commit writes new color orders into staged installation and hot-applies safely
