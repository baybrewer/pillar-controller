# Test Plan

## Existing tests (must continue passing)

### test_mapping.py (22 tests)
- Logical-to-channel mapping for all 10 strips
- Full coverage verification (all 1720 pixels unique)
- Even/odd strip direction
- map_frame_fast output shape and identity
- Serialization byte order and length
- Wrap and downsample

### test_protocol.py (19 tests)
- Packet build/verify round-trip
- CRC rejection
- Magic rejection
- Truncation rejection
- Large payloads
- COBS round-trip with zeros
- Frame packet delimiter
- Hello/Frame/Caps payload construction

## New tests

### test_protocol.py additions
- `test_blackout_on_payload`: verify BLACKOUT with 0x01 builds correctly
- `test_blackout_off_payload`: verify BLACKOUT with 0x00 builds correctly
- `test_stats_payload_28_bytes`: verify 28-byte payload parses correctly
- `test_stats_payload_too_short`: verify <28 bytes returns structured error

### test_auth.py (NEW)
- `test_protected_endpoint_no_token`: GET/POST without token → 401
- `test_protected_endpoint_bad_token`: wrong token → 401
- `test_protected_endpoint_valid_token`: correct token → 200
- `test_public_endpoint_no_token`: status endpoints → 200 without token
- `test_websocket_no_token`: connection accepted but limited
- `test_auth_fail_closed_no_config`: missing config → all protected rejected

### test_brightness.py (NEW)
- `test_manual_mode_returns_cap`: auto disabled → returns manual_cap
- `test_auto_mode_day`: midday → solar_factor 1.0
- `test_auto_mode_night`: midnight → solar_factor = night_brightness
- `test_auto_mode_dawn_transition`: sunrise boundary → interpolated
- `test_auto_mode_dusk_transition`: sunset boundary → interpolated
- `test_timezone_awareness`: different tz → different phase
- `test_fallback_on_invalid_location`: bad coords → manual_cap
- `test_effective_brightness_formula`: manual * solar
- `test_phase_names`: correct phase enum at each time

### test_media.py (NEW)
- `test_metadata_construction`: MediaItem(**meta) works with correct keys
- `test_scan_library_loads_items`: cached metadata loads correctly
- `test_import_image`: image import creates valid cache
- `test_import_gif`: GIF import creates multi-frame cache
- `test_media_list`: list returns correct format
- `test_media_delete`: delete removes cache and item

### test_upload.py (NEW)
- `test_upload_valid_image`: small PNG accepted
- `test_upload_oversized`: >50MB rejected with 413
- `test_upload_invalid_type`: .exe rejected with 400
- `test_upload_empty`: empty file rejected

### test_state.py (NEW)
- `test_debounced_save`: rapid mutations trigger one save
- `test_force_save`: shutdown writes immediately
- `test_atomic_write`: state file not corrupted on write

## Hardware-dependent tests (cannot run locally)

These are documented but not executed in CI:
- USB transport handshake with real Teensy
- Hotspot networking
- Audio device capture
- LED output verification
- Power/thermal behavior

## Test execution

```bash
cd ~/ai/pillar-controller/pi
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v
```

## Coverage expectations

| Module | Target |
|--------|--------|
| mapping/cylinder.py | 95%+ (existing) |
| models/protocol.py | 90%+ (existing + new) |
| core/brightness.py | 95%+ (new, pure logic) |
| api/auth.py | 90%+ (new) |
| media/manager.py | 70%+ (IO-heavy) |
| core/state.py | 70%+ |
| transport/usb.py | 50% (hardware-dependent) |
| audio/analyzer.py | 30% (hardware-dependent) |
