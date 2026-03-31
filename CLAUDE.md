# Pillar Controller

LED pillar controller: Raspberry Pi + Teensy 4.1 + OctoWS2811.

## Architecture
- **Pi**: FastAPI backend, phone UI, effects/media/audio, USB frame transport
- **Teensy**: OctoWS2811 DMA output, packet handling, diagnostics
- **Protocol**: Binary COBS-framed packets over USB Serial with CRC32
- **Canvas**: Logical 10x172 RGB -> mapped to 5x344 electrical channels

## Key modules
- `pi/app/main.py` — entry point, lifecycle, config
- `pi/app/api/server.py` — FastAPI REST + WebSocket + auth
- `pi/app/api/auth.py` — centralized Bearer token auth
- `pi/app/core/renderer.py` — render loop
- `pi/app/core/brightness.py` — brightness engine + solar automation
- `pi/app/core/state.py` — debounced persistent state
- `pi/app/models/protocol.py` — binary protocol definitions (SSOT)
- `pi/app/mapping/cylinder.py` — serpentine mapping engine
- `pi/app/transport/usb.py` — USB serial transport
- `teensy/firmware/src/main.cpp` — Teensy firmware

## Auth
- Bearer token in `Authorization` header
- Token configured in `system.yaml` under `auth.token`
- All mutating endpoints require auth; reads are public
- Fail closed: no configured token = all protected endpoints rejected

## Brightness
- Manual cap always active
- Optional solar automation (astral library, 5 phases: night/dawn/day/dusk)
- Effective brightness = min(manual_cap, solar_factor)
- Config in system.yaml under `brightness`

## Config
- `pi/config/system.yaml.example` — template (tracked)
- `pi/config/system.yaml` — real config (gitignored, contains secrets)
- `pi/config/hardware.yaml` — physical layout SSOT
- `pi/config/effects.yaml` — effect defaults

## Running locally (dev)
```bash
cd pi
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
PILLAR_DEV=1 python -m app.main  # starts on :8000
```

## Running tests
```bash
cd pi
PYTHONPATH=. pytest tests/ -v
```

## Deploying to Pi
```bash
pi/scripts/setup.sh   # first time
pi/scripts/deploy.sh pillar.local  # updates
```

## Rules
- Pi owns rendering; Teensy owns LED output
- Mapping config in hardware.yaml — never hardcode strip layout
- 60 FPS is the default target
- Blackout is explicit (on/off payload), never toggle
- Stats payload is exactly 28 bytes (7 x uint32)
- All privileged endpoints require Bearer auth
