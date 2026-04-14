# 03 — Output Compiler and Protocol

This document defines how per-strip count and color-order support is implemented without breaking the existing transport contract.

## 1. Core decision

Handle per-strip RGB order and installed LED count on the Pi in a compiled runtime packer.

Do **not** try to solve this in firmware.

## 2. Why this is the right layer

| Reason | Consequence |
|---|---|
| current firmware uses one global OctoWS2811 color-order mode | per-strip swizzle must happen before bytes leave the Pi |
| current protocol is fixed-header and channel-major | variable physical counts still need fixed padded output |
| current mapper already owns logical-to-electrical packing | extending it is cheaper than teaching firmware about strip metadata |

## 3. Current hardware/protocol facts

| Fact | Meaning |
|---|---|
| `ACTIVE_OUTPUTS = 5` | five active electrical channels |
| `LEDS_PER_STRIP = 344` in `config.h` | electrical LEDs per active output, not physical strip length |
| `LEDS_PER_PHYSICAL = 172` | physical LEDs per strip |
| controller wire order is BGR | default live path is BGR, not GRB |
| frame payload is channel-major bytes | keep that shape |

## 4. New runtime objects

```python
@dataclass(frozen=True)
class ControllerProfile:
    output_backend: str            # "octows2811"
    signal_family: str             # "ws281x_800khz"
    controller_wire_order: str     # "BGR"
    active_outputs: int            # 5
    total_outputs: int             # 8
    electrical_leds_per_output: int  # 344
    physical_leds_per_strip: int   # 172
```

```python
@dataclass(frozen=True)
class CompiledStripPlan:
    strip_id: int
    enabled: bool
    logical_order: int
    output_channel: int
    output_slot: int
    output_offset: int
    direction: str
    installed_led_count: int
    color_order: str
    precontroller_swizzle: tuple[int, int, int]
```

```python
@dataclass(frozen=True)
class CompiledOutputPlan:
    controller: ControllerProfile
    strips: list[CompiledStripPlan]
    logical_width: int
    logical_height: int
    channels: int
    leds_per_channel: int
```

## 5. Replace handwritten swizzle tables with permutation composition

The review docs used handwritten tables tied to a possibly wrong controller-order assumption.

Do not repeat that.

### 5.1 Correct rule

Compute the precontroller swizzle from:

- controller wire order
- strip-native wire order

Algorithm:

1. enumerate the 6 RGB permutations
2. for each candidate precontroller permutation:
   - simulate intended logical basis colors `R`, `G`, `B`
   - apply candidate permutation
   - apply controller wire-order permutation
   - interpret bytes using the strip-native order
3. choose the only permutation that reproduces the intended logical basis colors

Because there are only 6 permutations, brute-force composition is clearer and safer than maintaining brittle manual tables.

### 5.2 Required test

```python
def test_swizzle_roundtrip_all_permutations():
    controller_orders = ["RGB", "RBG", "GRB", "GBR", "BRG", "BGR"]
    strip_orders = ["RGB", "RBG", "GRB", "GBR", "BRG", "BGR"]

    for controller_order in controller_orders:
        for strip_order in strip_orders:
            swizzle = derive_precontroller_swizzle(controller_order, strip_order)
            for intended in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
                displayed = simulate_display(intended, swizzle, controller_order, strip_order)
                assert displayed == intended
```

This test becomes the source of truth for both runtime swizzle and wizard inference logic.

## 6. Installed LED count behavior

| Rule | Behavior |
|---|---|
| effect render height | stays `max(controller.physical_leds_per_strip)` for legacy parity |
| strip shorter than max | truncate logical frame to `installed_led_count` |
| output slot fill | zero-pad remainder of that slot |
| channel payload | remains `channels x leds_per_channel x 3` |

## 7. Compiler responsibilities

The compiler must:

- seed default legacy parity plan
- validate channel/slot collisions
- compute each strip output offset
- compute swizzle tuple
- compute channel-major pack layout
- expose `channels` and `leds_per_channel` explicitly to the transport
- tell the renderer whether a hot-apply or restart is required

## 8. Runtime mapping path

### 8.1 New module layout

| Module | Purpose |
|---|---|
| `pi/app/mapping/runtime_plan.py` | compiler and dataclasses |
| `pi/app/mapping/runtime_mapper.py` | plan-driven mapping and serialization |
| `pi/app/mapping/cylinder.py` | retained only as legacy compatibility reference during migration |

### 8.2 Mapping algorithm

For each compiled strip:

1. select logical column by `logical_order`
2. truncate to `installed_led_count`
3. reverse if direction is top-to-bottom
4. apply `precontroller_swizzle`
5. place into `[output_channel, output_offset : output_offset + installed_led_count]`
6. leave remaining bytes zero

## 9. Renderer integration

### 9.1 Hardcoded shape removal

Replace all hardcoded `(5, 344, 3)` allocations in `renderer.py` with plan-driven dimensions:

```python
channel_data = np.zeros(
    (compiled_plan.channels, compiled_plan.leds_per_channel, 3),
    dtype=np.uint8,
)
```

### 9.2 Serializer integration

`serialize_channels` should stop embedding stale comments about GRB internals.

It should accept the compiled plan or a serializer meta object and only serialize bytes in the agreed channel-major fixed shape.

## 10. Generator and firmware sync

### 10.1 Keep generator semantics honest

`generate_teensy_config.py` currently stamps:

- `LEDS_PER_STRIP` from electrical channel length
- `LEDS_PER_PHYSICAL` from physical strip length

That distinction is correct and must remain explicit.

### 10.2 What can change in firmware

Acceptable firmware tweaks:

- richer CAPS fields that expose both physical and electrical lengths clearly
- comments/doc cleanup around BGR runtime truth
- optional commissioning helpers if genuinely useful

Do not push per-strip setup state into firmware.

## 11. Protocol rules

| Rule | Final stance |
|---|---|
| frame header shape | keep existing fixed-header pattern |
| per-strip variable count | compile to padded channel-major bytes |
| CONFIG packet | may remain advisory until explicitly expanded |
| preview traffic | separate from live USB transport and current `/ws` |

## 12. Required touchpoints

| File | Change |
|---|---|
| `pi/app/core/renderer.py` | consume compiled plan and dynamic output shape |
| `pi/app/mapping/cylinder.py` | demote to legacy parity reference |
| `pi/app/transport/usb.py` | accept explicit `channels` + `leds_per_channel` meta |
| `pi/tests/test_protocol.py` | add electrical-vs-physical semantics coverage |
| `teensy/firmware/include/config.h` | keep physical/electrical split explicit |
| `pi/scripts/generate_teensy_config.py` | validate controller envelope consistency |

## 13. Done criteria

- default migrated plan matches the old mapper byte-for-byte
- per-strip count and order changes affect real output at runtime
- no hardcoded shape assumptions remain in live render paths
- swizzle logic is test-derived, not comment-derived
