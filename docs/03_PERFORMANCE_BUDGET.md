# 03. Performance Budget

## 3.1 Project geometry and channelization

| Item | Value |
|---|---:|
| Physical strips | 10 |
| LEDs per strip | 172 |
| Total LEDs | 1,720 |
| Electrical arrangement | 5 serpentine pairs |
| LEDs per active channel | 344 |
| Active Octo outputs | 5 |
| Spare Octo outputs | 3 |

## 3.2 WS2812 refresh ceiling

PJRC documents OctoWS2811 timing as:

- output update time = **30 µs per LED**
- plus **50 µs reset**[1]

Worldsemi's WS2812B datasheet separately documents 800 Kbps timing and reset timing above **50 µs**.[4]

### For 344 LEDs/channel
- `344 × 30 µs = 10,320 µs`
- `+ 50 µs = 10,370 µs`
- `max FPS ≈ 96.43`

### Conservative reset assumption
Some WS2812-family parts and variants are treated more conservatively with a larger reset margin. Using `280 µs` instead:

- `10,320 + 280 = 10,600 µs`
- `max FPS ≈ 94.34`

### For the earlier 340-LED/channel case
- `340 × 30 + 50 = 10,250 µs`
- `max FPS ≈ 97.56`

Conservative:
- `340 × 30 + 280 = 10,480 µs`
- `max FPS ≈ 95.42`

## 3.3 Practical FPS recommendation

| Mode | Recommended | Why |
|---|---:|---|
| Guaranteed operating mode | 60 FPS | healthy margin below strip ceiling |
| Legacy/safe mode | 30 FPS | for debugging or heavy imports |
| Performance mode | 75–90 FPS | optional; depends on Pi-side pipeline |
| Not worth targeting | 95+ FPS | no safety margin; little UX gain |

The correct product target is **stable 60 FPS**.

## 3.4 USB transport budget

PJRC documents Teensy 4.1 USB device as **480 Mbit/sec**, and USB Serial transfers bytes in both directions at **maximum USB speed**, ignoring baud-rate settings.[3]

### Payload option A — 5 active channels only
`5 × 344 × 3 = 5,160 bytes/frame`

| FPS | Payload/sec |
|---|---:|
| 30 | 154.8 KB/s |
| 60 | 309.6 KB/s |
| 90 | 464.4 KB/s |

### Payload option B — fixed 8-lane payload
`8 × 344 × 3 = 8,256 bytes/frame`

| FPS | Payload/sec |
|---|---:|
| 30 | 247.7 KB/s |
| 60 | 495.4 KB/s |
| 90 | 743.0 KB/s |

Either option is tiny compared with USB headroom.

### Recommendation
Use **Option A** in protocol v1 for cleaner semantics:
- less wasted bandwidth
- clearer packet definitions
- explicit active channel count

If implementation simplicity matters more than bandwidth, Option B is still fine.

## 3.5 Teensy memory budget

PJRC documents:
- Teensy 4.1 has **1024K RAM**
- OctoWS2811 needs display memory of **6 integers × ledsPerStrip**
- drawing memory is another **6 integers × ledsPerStrip**, or can be `NULL`[1][3]

For `ledsPerStrip = 344`:

- one buffer = `6 × 344 ints`
- if `int = 4 bytes`, one buffer = `6 × 344 × 4 = 8,256 bytes`
- two buffers = `16,512 bytes`

This is trivial on Teensy 4.1.

## 3.6 Pi-side render cost

Your physical output is only **10 × 172 = 1,720 pixels**.

That is tiny.

The real CPU cost on the Pi is not pixel count. It is:
- video decode
- image resampling
- audio FFT / beat detection
- web stack overhead
- Python / JS runtime overhead
- filesystem / media import work

That is why the implementation should:
1. transcode uploads into a project-native cached format;
2. keep the real-time render surface small;
3. keep the Teensy protocol binary.

## 3.7 Suggested render strategy

### Real-time scene canvas
Maintain a logical frame buffer of:
- `height = 172`
- `width = 10`
- `channels = RGB`

### Optional supersampled internal canvas
For smoother rotational or video motion, render internally at:
- `width = 40` or `60`
- `height = 172`

Then downsample to the 10 physical columns before serialization.

This helps because 10 angular columns around a cylinder is extremely low horizontal resolution.

## 3.8 End-to-end latency model

The LED output time is the hard floor once a new frame starts transmission to the strips: about **10.37 ms** at 344 LEDs/channel.[1]

A realistic software pipeline at 60 FPS should budget roughly:

| Stage | Target budget |
|---|---:|
| scene/effect evaluation | 1–3 ms |
| media/frame extraction | 0–4 ms |
| audio feature update | 0–2 ms |
| mapping + serialization | <1 ms |
| USB write | <1 ms |
| Teensy parse / copy | <1 ms |
| LED wire time | 10.37 ms |

That keeps you in the right ballpark for a one-frame real-time loop.

## 3.9 Power budget

Adafruit's practical guidance:
- worst-case WS2812/NeoPixel current is **60 mA/pixel** at full-white
- practical rule of thumb is **20 mA/pixel** average for many animations[7]

### Whole installation
- worst-case: `1,720 × 60 mA = 103.2 A`
- rule-of-thumb typical: `1,720 × 20 mA = 34.4 A`

### Per physical strip (172 LEDs)
- worst-case: `172 × 60 mA = 10.32 A`
- rule-of-thumb: `172 × 20 mA = 3.44 A`

### Consequence
You should not design the mechanical/power system assuming "one little 5V supply somewhere."

Use:
- distributed power injection
- common ground
- conservative brightness cap in software
- heavy gauge power distribution

## 3.10 Engineering conclusions

1. **USB is not the bottleneck.**
2. **Teensy RAM is not the bottleneck.**
3. **The WS2812 channel length is the real hard FPS limiter.**
4. **Stable 60 FPS is comfortably achievable.**
5. **The only way to lose is sloppy Pi software, bad power distribution, or wrong mapping.**

## References

[1] PJRC OctoWS2811 library  
[3] PJRC Teensy 4.1  
[4] WS2812B datasheet  
[7] Adafruit NeoPixel power guidance
