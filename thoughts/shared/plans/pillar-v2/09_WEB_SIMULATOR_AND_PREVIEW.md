# 09 — Web Simulator and Preview

The simulator must show real Python-rendered output without mutating the live LED scene.

## 1. Final transport choice

Use a dedicated preview WebSocket.

Do not extend the current global `/ws` state socket with binary frame traffic.

### Why

| Reason | Benefit |
|---|---|
| current `/ws` is tiny and stable | keeps existing frontend behavior intact |
| preview lifecycle is separate from app-state broadcast | easier migration and debugging |
| binary frame traffic is opt-in | no wasted bandwidth |
| preview may evolve independently | cleaner API surface |

## 2. New route surface

Add `pi/app/api/routes/preview.py`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/preview/status` | preview state |
| `POST` | `/api/preview/start` | start preview effect |
| `POST` | `/api/preview/stop` | stop preview effect |
| `WS` | `/api/preview/ws` | binary preview frame stream |

## 3. Preview rules

| Rule | Final behavior |
|---|---|
| live LEDs | continue showing the active scene |
| preview output | can differ from live scene |
| effect instances | live and preview use separate instances |
| preview timeout | auto-expire after inactivity |
| reconnect | browser may resubscribe cleanly |

## 4. Frame format

Use a small explicit header so the browser can validate dimensions.

```text
u8   message_type      # 0x01 = frame
u32  frame_id_le
u16  width_le
u16  height_le
u8   encoding          # 0 = RGB
payload = width * height * 3 bytes
```

Default payload is the logical canvas after brightness/gamma and before electrical packing.

## 5. Preview service responsibilities

| Responsibility | Detail |
|---|---|
| create preview effect instance | independent from live effect instance |
| render preview frame | same effect code path as live runtime |
| throttle stream | configurable FPS for browser |
| handle subscribers | dedicated preview websocket only |
| expose status | active effect, fps, last frame id |

## 6. Renderer integration

The renderer should support an optional callback or hook for logical frames, but preview state itself belongs in `PreviewService`, not in a pile of ad hoc mutable flags.

Recommended split:

- `Renderer` renders live scene as normal
- `PreviewService` owns preview effect instance and preview websocket clients
- when preview is active, `PreviewService` requests preview frames on its own cadence
- live renderer and preview renderer share effect implementation, not mutable instance state

This avoids cross-contaminating live effect state with preview browsing.

## 7. Browser behavior

### 7.1 UI

Add a `Sim` tab with:

- canvas view
- current preview/live effect label
- FPS selector
- preview on/off state

### 7.2 Lifecycle

- connect preview websocket when Sim tab opens
- disconnect or pause when Sim tab closes
- use `/api/preview/start` when the user previews an effect
- use `/api/preview/stop` when leaving preview mode

## 8. Rendering mode

V1 simulator uses the flat unwrapped 10 x 172 view.

Optional later enhancements:

- CSS perspective “cylinder” hint
- overlay of front-projection geometry
- side-by-side preview vs live metadata

Keep v1 simple.

## 9. File touchpoints

| File | Change |
|---|---|
| new `pi/app/api/routes/preview.py` | preview API and preview websocket |
| `pi/app/api/server.py` | mount preview router |
| `pi/app/core/renderer.py` | expose logical frame hook or shared render helper |
| `pi/app/ui/static/index.html` | Sim tab and canvas |
| `pi/app/ui/static/js/app.js` | preview websocket client and simulator drawing |
| `pi/app/ui/static/css/app.css` | simulator styles |

## 10. Tests

Add tests for:

- preview start/stop routes
- preview/live scene isolation
- binary frame header format
- reconnect/resubscribe path
- no mutation of live scene when preview is active

## 11. Done criteria

- Sim tab shows real Python-rendered frames
- previewing an effect does not change live LEDs
- current `/ws` JSON state channel remains intact
- simulator transport is opt-in and isolated
