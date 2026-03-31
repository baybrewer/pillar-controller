# Requirements and Non-Goals

## Functional requirements

### R1: Deployment consistency
- Python package installs cleanly via `pip install -e .`
- systemd service starts the installed console script
- setup.sh creates venv and installs from pyproject.toml
- deploy.sh syncs code and restarts service
- No ambiguous import paths or working directory assumptions

### R2: Explicit blackout
- Blackout command carries an explicit on/off byte
- Pi sends `BLACKOUT` with payload `0x01` (on) or `0x00` (off)
- Teensy sets blackout state to the received value, never toggles
- Pi tracks blackout as explicit bool, never toggles
- Turning blackout off always resumes normal output

### R3: Media import correctness
- MediaItem constructor and metadata JSON use consistent keys
- scan_library correctly reconstructs items from cached metadata
- Image, GIF, and video import produce valid cached items
- Upload endpoint validates size, type, and reports errors clearly
- Media can be listed, played, and deleted after import

### R4: Stats payload alignment
- Teensy sends exactly 28 bytes (7 × uint32_t)
- Pi parser expects exactly 28 bytes minimum
- Field names and order documented in schemas doc
- Parse failure returns structured error, not hex dump

### R5: Authentication
- All mutating/privileged endpoints require Bearer token
- Token configured in system.yaml `auth.token`
- Missing or invalid token → 401 Unauthorized
- Auth enforced via FastAPI Depends() — single implementation
- If token not configured, all privileged endpoints reject (fail closed)

### R6: Brightness with solar automation
- Manual max brightness (0.0–1.0) always available
- Optional auto mode using sunrise/sunset calculation
- Configurable latitude, longitude, timezone
- Five-phase transition model (see architecture doc)
- Effective brightness = min(manual_cap, solar_factor)
- Solar calculation uses `astral` library (pure Python, no network)
- Graceful fallback to manual if solar calc fails
- UI shows manual slider, auto toggle, effective brightness

### R7: Upload limits
- Maximum upload size enforced at request level (default 50MB)
- Oversized uploads rejected with 413 before full read
- File extension and content-type validated
- No full-file memory reads for large uploads

### R8: Metrics correctness
- Frame count only incremented on successful transport send
- Separate counters: frames_rendered, frames_sent, frames_dropped
- Transport failures not counted as successful sends

### R9: Shutdown lifecycle
- FastAPI shutdown event stops renderer, transport, audio
- Background asyncio tasks tracked and cancelled
- Serial port released cleanly
- Audio thread joined with timeout
- No orphaned processes after systemctl stop

### R10: Production config
- Production port derived from system.yaml `ui.port` (default 80)
- Dev mode detected by environment variable `PILLAR_DEV=1`
- Dev mode uses `ui.dev_port` (default 8000)
- Config paths respect `/opt/pillar` in prod, local in dev

### R11: No committed secrets
- system.yaml tracked as system.yaml.example with placeholder values
- Real system.yaml in .gitignore
- Setup docs explain provisioning
- WiFi password and auth token never in git history going forward

### R12: Persistence consistency
- State saves batched via debounced write (max 1 write/second)
- Related state changes grouped before save
- Atomic write preserved (tempfile + rename)

### R13: Thread-safe audio state
- Audio analyzer writes to a local snapshot dict
- Renderer reads snapshot via lock-protected copy
- No direct cross-thread mutable attribute access

### R14: Clean dependencies
- All runtime deps in pyproject.toml `dependencies`
- Optional deps in `[project.optional-dependencies]`
- setup.sh installs from pyproject.toml, not duplicated pip list
- No conflicting requirements between dev/prod

### R15: Repo hygiene
- Remove any tracked .venv, __pycache__, .pytest_cache, .DS_Store
- Tighten .gitignore
- No generated artifacts in git

## Non-goals

- New LED effects or effect parameter validation UI
- Multi-device support (multiple Teensys)
- Cloud connectivity or remote access
- Captive portal
- OTA firmware updates
- Video streaming to phone preview
- User account management
- Database backend (JSON files are fine for this scale)
