# 09. Claude / Opus Handoff Prompt

Use this prompt as the first instruction when handing the planning packet to Claude Code / Opus.

---

You are implementing a headless Raspberry Pi + Teensy 4.1 LED pillar controller.

Read these files in order:

1. `00_INDEX.md`
2. `01_EXECUTIVE_SUMMARY.md`
3. `02_SYSTEM_ARCHITECTURE.md`
4. `03_PERFORMANCE_BUDGET.md`
5. `04_WIRING_AND_MAPPING.md`
6. `05_PI_SOFTWARE_SPEC.md`
7. `06_TEENSY_FIRMWARE_SPEC.md`
8. `07_IMPLEMENTATION_PLAN.md`
9. `08_TEST_AND_ACCEPTANCE_PLAN.md`
10. `10_SOURCES.md`

Then do the following:

## Mission

Build a working implementation for a cylindrical LED pillar made from:
- 10 physical WS2812 strips
- 172 LEDs per strip
- paired into 5 serpentine chains of 344 LEDs each
- driven by a Teensy 4.1 + OctoWS2811 adaptor
- controlled by a Raspberry Pi over USB
- operated from an iPhone via a headless local Wi-Fi control site

## Required architectural rules

1. The Raspberry Pi owns:
   - hotspot/AP behavior
   - phone UI
   - media uploads and caching
   - video/effects/audio-reactive rendering
   - scene state
   - USB frame transmission

2. The Teensy owns:
   - USB packet handling
   - OctoWS2811 DMA output
   - diagnostics / local test patterns
   - bounded-latency frame application

3. The Pi renders a **logical 10 x 172 cylindrical frame**.
4. The Pi maps that logical frame to **5 x 344 electrical channels** before sending.
5. The Teensy should not perform heavyweight rendering.
6. The first stable milestone is **60 FPS**.
7. Design for appliance behavior, not lab-demo behavior.

## Implementation priorities

First:
- hardware config
- Teensy firmware skeleton
- USB framing protocol
- Pi transport layer
- mapping math
- diagnostic test patterns

Second:
- minimal web UI
- hotspot boot behavior
- scene save/load
- stable live frame loop

Third:
- media upload/import
- cached playback
- audio-reactive features
- playlists and system page

## Constraints

- Do not over-abstract.
- Do not build a general-purpose lighting engine before the pillar works.
- Keep config file driven.
- Write tests for mapping and packet parsing.
- Prefer clear, debuggable code over clever code.
- Surface useful logs and diagnostics.

## Deliverables

Produce:
1. repo structure
2. Pi application
3. Teensy firmware
4. systemd service files
5. setup docs
6. test docs
7. any helper scripts required to deploy to the Pi

## If you hit ambiguity

Prefer the assumptions in the planning packet.
If a question is still blocking, ask only tightly scoped implementation questions.

---

End of prompt.
