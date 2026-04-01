# R3 Remediation — Final Status

External review R2 found two critical transport defects (COBS long-run truncation
and CRC32 table corruption) plus deployment, performance, and integration issues.
All P0 and most P1 items addressed. 120/120 tests passing.

## P0 fixes — all resolved

| ID | Fix |
|---|---|
| P0-01 COBS long runs | Both Python and Teensy encoders now emit 0xFF continuation blocks for non-zero runs >254 bytes. Decoders handle 0xFF correctly (no implicit zero). Verified with 254/255/300/1000-byte runs and full 5191-byte frame packets. |
| P0-02 CRC32 table | Teensy CRC32 lookup table replaced (88 of 256 entries were corrupted). CRC function itself was correct. Cross-language golden tests verify PING/HELLO/FRAME/BLACKOUT packets. |
| P0-03 Port 80 binding | systemd service has `AmbientCapabilities=CAP_NET_BIND_SERVICE`. |
| P0-04 Video support | setup.sh and deploy.sh both install `[audio,video]` extras. |

## P1 fixes

| ID | Status | Fix |
|---|---|---|
| P1-01 Topology SSOT | ACKNOWLEDGED | Mapping still uses arithmetic (x//2). Promoting pairs/direction to schema is deferred — the current pairs assumption is physically wired and unlikely to change. |
| P1-02 Generated constants | PARTIAL | hardware_constants.py is SSOT for Python. Teensy uses config.h validated by cross-language test. Full codegen deferred. |
| P1-03 leds_per_strip naming | ACKNOWLEDGED | Protocol uses leds_per_strip for electrical output (344). Would require protocol version bump. Documented. |
| P1-04 setup.sh rsync | FIXED | Uses `sudo rsync`, added `rsync` to apt-get. |
| P1-05 Hotspot provisioning | FIXED | Uses venv python, reads hostname from config, fails loudly with retry instructions. |
| P1-06 Media pipeline | ACKNOWLEDGED | Import is still sync. Playback still loads from disk. Threading deferred — infrequent imports, small frame files. |
| P1-07 Media timing | ACKNOWLEDGED | Video FPS metadata clamping and GIF per-frame timing noted. Deferred to v2. |
| P1-08 Startup restore | FIXED | Uses activate_scene() with fallback to startup_scene on failure. Media scenes restore correctly. |
| P1-09 Brightness Teensy | FIXED | Brightness endpoints send effective brightness to Teensy via transport.send_brightness(). |
| P1-10 Audio config | FIXED | sensitivity/gain are Optional, partial updates don't reset each other. |
| P1-11 Fire performance | FIXED | Fully vectorized with numpy. Heat simulation, rising, and color mapping all use array ops. |
| P1-12 Dead UI | FIXED | Preview canvas removed. Audio meters retained (structural). |
| P1-13 Transport architecture | ACKNOWLEDGED | asyncio.Lock protects writes, to_thread for frame send. Full command/response demux deferred to v2. |

## P2 fixes

| ID | Status |
|---|---|
| P2-01 Pydantic models | AudioConfigRequest fields fixed to Optional. Others deferred. |
| P2-03 Dead config | Noted. seam_position, octo_pins etc in config but not consumed. Deferred. |
| P2-04 Frame contract | Teensy clears pendingFrame before copy. Exact length enforcement deferred. |
| P2-05 Artifact hygiene | .gitignore covers all generated files. |
| P2-06 Tests | Added 16 new tests: 7 COBS long-run, 4 CRC cross-language, 5 golden vector round-trips. |
| P2-07 Dead code | sendPong() removed from Teensy. |

## Reproduction verification

| Review reproduction | Before | After |
|---|---|---|
| All-0xFF frame (5191B) | framed=280B, decoded=278B, verify=FAIL | framed=5213B, decoded=5191B, verify=PASS |
| PING packet CRC | Teensy 0xd079db36, Python 0xcbd364c3 | Both 0xcbd364c3 (table fixed) |
| Fire effect timing | ~25ms/frame | vectorized, ~2ms estimated |

## Test counts

| File | Tests |
|---|---|
| test_auth.py | 6 |
| test_brightness.py | 14 |
| test_mapping.py | 22 |
| test_media.py | 6 |
| test_protocol.py | 66 (+16 new: long-run COBS, CRC cross-language) |
| test_state.py | 6 |
| **Total** | **120** |
