# Sources and factual basis

These are the primary references used to anchor the planning packet.

1. PJRC — OctoWS2811 library  
   https://www.pjrc.com/teensy/td_libs_OctoWS2811.html

2. PJRC — OctoWS2811 adaptor board  
   https://www.pjrc.com/store/octo28_adaptor.html

3. PJRC — Teensy 4.1 development board  
   https://www.pjrc.com/store/teensy41.html

4. Worldsemi / SparkFun mirror — WS2812B datasheet  
   https://cdn.sparkfun.com/assets/e/6/1/f/4/WS2812B-LED-datasheet.pdf

5. Raspberry Pi documentation — headless setup  
   https://www.raspberrypi.com/documentation/computers/getting-started.html

6. NetworkManager reference manual — nmcli hotspot  
   https://networkmanager.dev/docs/api/latest/nmcli.html

7. Adafruit NeoPixel Überguide — powering and best practices  
   https://learn.adafruit.com/adafruit-neopixel-uberguide/powering-neopixels  
   https://learn.adafruit.com/adafruit-neopixel-uberguide?view=all

## Key extracted facts

- OctoWS2811 updates up to 8 strips simultaneously with DMA and minimal CPU impact.
- `show()` returns quickly and LED output time is `30 microseconds × LEDs per strip + 50 microseconds reset`.
- OctoWS2811 expects equal strip lengths; shorter/unused outputs are allowed.
- Teensy 4.1 USB device port runs at 480 Mbit/sec and USB Serial transfers at maximum USB speed.
- Raspberry Pi can be set up headless and NetworkManager can create a Wi-Fi hotspot.
- Separate LED power supplies must share ground but should not have their +5V rails tied together across strips fed by different supplies.
- NeoPixel rule-of-thumb power is ~20 mA/pixel typical and 60 mA/pixel worst-case full-white.
