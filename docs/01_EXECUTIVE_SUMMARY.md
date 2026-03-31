# 01. Executive Summary

## Decision

Build the controller as a **two-plane system**:

1. **Raspberry Pi control/render plane**
   - Runs headless
   - Creates or maintains its own Wi-Fi network
   - Hosts a phone-friendly control website
   - Handles effects, low-resolution video playback, media uploads, playlists, presets, diagnostics, and audio-reactive analysis
   - Serializes finished frames to USB

2. **Teensy 4.1 output plane**
   - Receives framed pixel data over USB Serial
   - Maintains a small double-buffered LED output path
   - Uses **OctoWS2811 DMA** to refresh the strips with minimal CPU impact[1]
   - Owns diagnostics, test patterns, and fail-safe output behavior

## Why this is the right architecture

### It matches the real bottlenecks
The Pi is good at:
- networking
- a headless web stack
- file/media management
- audio analysis
- easy iteration

The Teensy + Octo path is good at:
- deterministic timing
- 8-way parallel WS2812 output
- keeping USB / computation separate from LED wave timing via DMA[1]

Trying to make one device do both well is how you get jank.

## Hard numbers

### Physical installation
- **10 physical strips**
- **172 LEDs per strip**
- **1,720 LEDs total**

### Electrical output plan
- Pair neighboring strips in series
- Use **5 active Octo outputs**
- Each active output drives **344 LEDs**
- Outputs 6–8 remain unused but reserved

### Frame-rate ceiling
PJRC states that OctoWS2811 LED output time is:

`30 microseconds × LEDs per strip + 50 microseconds reset`[1]

For **344 LEDs per active channel**:

- LED shift time = `344 × 30 µs = 10,320 µs`
- Reset = `50 µs`
- Frame time = `10,370 µs = 10.37 ms`
- Theoretical max = `1 / 0.01037 ≈ 96.4 FPS`

A conservative WS2812B reset assumption of **280 µs** yields:

- `10,320 + 280 = 10,600 µs`
- `≈ 94.3 FPS`[4]

### USB payload
If the Pi sends only the 5 active channels:

- `5 channels × 344 LEDs × 3 bytes = 5,160 bytes/frame`

At:
- **30 FPS** → 154.8 KB/s
- **60 FPS** → 309.6 KB/s
- **90 FPS** → 464.4 KB/s

If the Pi sends a fixed 8-lane payload for simplicity:

- `8 × 344 × 3 = 8,256 bytes/frame`

At:
- **30 FPS** → 247.7 KB/s
- **60 FPS** → 495.4 KB/s
- **90 FPS** → 743.0 KB/s

PJRC documents Teensy 4.1 USB device at **480 Mbit/sec**, and USB Serial runs at **maximum USB speed**, ignoring baud-rate settings.[3]

USB is not the limiter.

## Recommended target modes

| Mode | FPS target | Use case |
|---|---:|---|
| Safe/default | 60 | main operating mode |
| Compatibility | 30 | if media pipeline is stressed |
| High-performance | 75 or 90 | optional mode for lighter effects/media |
| Absolute ceiling | ~94–96 | physical WS2812 limit at 344 LEDs/channel |

## Key product requirements

1. Plug in the Pi and Teensy.
2. The Pi comes up **headless** and exposes a local Wi-Fi network.[5][6]
3. iPhone joins the network.
4. User opens a phone UI at a fixed address such as `http://192.168.4.1` and optionally `http://pillar.local`.
5. User can:
   - pick effects
   - upload and play low-res videos/GIFs/images
   - enable sound-reactive modes
   - run diagnostics and wiring tests
   - save presets/scenes
   - start playlists / autoplay
   - adjust brightness and safety caps

## Recommended MVP boundary

### Must-have in v1
- hotspot networking
- phone UI
- solid/test patterns
- scene presets
- 60 FPS render loop
- Teensy USB protocol
- cylinder mapping
- basic audio-reactive effects
- uploaded media clips
- diagnostics

### Nice-to-have in v2
- captive portal auto-redirect
- OTA update helpers
- scheduling/calendar
- remote client mode on an existing Wi-Fi network
- multi-user roles
- cloud backup / sync

## Bottom line

This is a good architecture, and it is much better aligned to your goals than trying to stretch Pixelblaze into a media server / web appliance.

## References

[1] PJRC OctoWS2811 library  
[3] PJRC Teensy 4.1  
[4] WS2812B datasheet  
[5] Raspberry Pi headless setup  
[6] NetworkManager `nmcli` hotspot
