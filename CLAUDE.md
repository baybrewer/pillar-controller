# Pillar Controller

LED pillar controller: Raspberry Pi + Teensy 4.1 + OctoWS2811.

## Architecture
- **Pi**: FastAPI backend, phone UI, effects/media/audio, USB frame transport
- **Teensy**: OctoWS2811 DMA output, packet handling, diagnostics
- **Protocol**: Binary COBS-framed packets over USB Serial with CRC32
- **Canvas**: Logical 10×172 RGB → mapped to 5×344 electrical channels

## Key Files
- `pi/app/main.py` — application entry point
- `pi/app/models/protocol.py` — binary protocol definitions
- `pi/app/mapping/cylinder.py` — serpentine mapping engine
- `pi/app/core/renderer.py` — render loop
- `pi/app/api/server.py` — FastAPI REST + WebSocket
- `teensy/firmware/src/main.cpp` — Teensy firmware
- `pi/config/hardware.yaml` — SSOT for physical layout

## Running Locally (Dev)
```bash
cd pi
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m app.main  # starts on :8000
```

## Running Tests
```bash
cd pi
pytest tests/ -v
```

## Deploying to Pi
```bash
pi/scripts/deploy.sh pillar.local
```

## Rules
- Pi owns rendering; Teensy owns LED output
- Mapping config in hardware.yaml — never hardcode strip layout
- 60 FPS is the default target
- Test mapping and protocol changes with unit tests
