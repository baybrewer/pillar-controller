# 07. Implementation Plan

## 7.1 Repository structure

```text
pillar-controller/
  README.md
  docs/
  pi/
    app/
      api/
      audio/
      core/
      diagnostics/
      effects/
      mapping/
      media/
      models/
      transport/
      ui/
    config/
    scripts/
    systemd/
    tests/
  teensy/
    firmware/
      src/
      include/
      test/
  tools/
    asset_prep/
    bench/
```

## 7.2 Build order

### Phase 1 — Hardware bring-up
Deliverables:
- Teensy firmware that drives 5 outputs
- test patterns
- verified color order
- verified strip numbering
- verified safe power-up sequence

Exit criteria:
- every strip can be identified
- mapping assumptions are confirmed physically
- no flicker at 60 FPS static updates

### Phase 2 — USB protocol
Deliverables:
- Pi ↔ Teensy hello/config handshake
- frame packet send/receive
- stats endpoint
- packet CRC validation

Exit criteria:
- Pi can push full frames reliably for at least 10 minutes
- no frame corruption
- reconnect works

### Phase 3 — Minimal web UI
Deliverables:
- hotspot boot
- phone-accessible UI
- live preview
- scene select
- brightness slider
- blackout button
- diagnostics tab

Exit criteria:
- user can control the pillar from an iPhone with no monitor

### Phase 4 — Effects engine
Deliverables:
- at least 8 core effects
- per-effect parameter model
- preset save/load
- scene recall

Exit criteria:
- effects stable at 60 FPS

### Phase 5 — Media pipeline
Deliverables:
- upload image/GIF/video
- import/transcode cache
- playback controls
- loop / speed / fit controls

Exit criteria:
- cached video clips play smoothly at 30 and 60 FPS modes

### Phase 6 — Audio-reactive
Deliverables:
- audio device selection
- FFT + beat detection
- modulation routing
- at least 3 audio-reactive scenes

Exit criteria:
- live audio visibly modulates effects with stable frame output

### Phase 7 — Hardening
Deliverables:
- crash-safe config writes
- startup restore
- reconnect robustness
- logs / metrics
- system actions from UI

Exit criteria:
- appliance-like behavior after repeated reboots and disconnects

## 7.3 Work packages for Claude / Opus

### WP1 — teensy firmware scaffold
Implement:
- Octo init
- output config
- test patterns
- stats counters
- USB serial setup

### WP2 — protocol library
Implement shared packet schema:
- framing
- CRC32
- serializer/deserializer
- typed command objects

### WP3 — Pi transport
Implement:
- device discovery
- reconnect loop
- handshake
- async frame send
- stats query

### WP4 — mapping engine
Implement:
- logical 10x172 frame
- 5x344 electrical serializer
- seam wrap
- config-driven strip order / inversion

### WP5 — core renderer
Implement:
- scene loop
- effect registry
- timing clock
- brightness clamp
- gamma correction

### WP6 — UI backend
Implement:
- FastAPI app
- REST models
- WebSocket status stream
- config persistence

### WP7 — UI frontend
Implement:
- mobile-first control panel
- diagnostics
- media upload
- scene list
- audio controls
- system page

### WP8 — media import
Implement:
- upload endpoint
- validation
- ffmpeg/PyAV transcode
- cache format
- preview generation

### WP9 — audio analysis
Implement:
- input device selection
- beat/onset
- band levels
- modulator state

### WP10 — system integration
Implement:
- systemd units
- first-run scripts
- hotspot profile instructions
- logs and health endpoints

## 7.4 Recommended task ordering inside each work package

Always implement in this order:
1. deterministic core
2. instrumentation
3. UI wrapper
4. polish

Do not start with beautiful screens while transport is still wrong.

## 7.5 Configuration files to define early

Create these on day 1:

### `hardware.yaml`
- active channels
- leds per strip
- color order
- strip numbering
- seam position
- inversions

### `system.yaml`
- hotspot SSID/password
- hostname
- UI port
- brightness cap
- startup scene

### `effects.yaml`
- built-in effect defaults
- scene parameters
- palette defaults

## 7.6 Suggested coding standards

- strict packet schemas
- no magic numbers in mapping code
- structured logs
- config-driven behavior
- unit tests for mapping math
- integration tests for protocol parsing
- explicit versioning for packet format

## 7.7 Critical path risks

| Risk | Why it matters | Mitigation |
|---|---|---|
| wrong physical strip order | breaks all rendering | diagnostics + mapping config |
| power injection too weak | flicker / wrong colors | power test before software blame |
| USB back-feed | can damage or destabilize host | explicit power plan |
| media decode jitter | causes dropped frames | import/transcode cache |
| audio device weirdness | blocks sound-reactive features | support device selection and fallback |
| trying to over-generalize | slows delivery | build for this pillar first |

## 7.8 Milestone acceptance checklist

| Milestone | Acceptance |
|---|---|
| M1 | all strips identified and mapped correctly |
| M2 | full frame transport stable |
| M3 | iPhone control works headless |
| M4 | core effects stable at 60 FPS |
| M5 | imported media plays correctly |
| M6 | audio-reactive scenes working |
| M7 | system survives reboot/disconnect cycles |

## 7.9 Engineering stance

The right move is to get to a robust, narrow, pillar-specific implementation first.
Do not waste time building a general-purpose lighting platform until this device behaves like an appliance.

