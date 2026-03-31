#pragma once

#include <stdint.h>
#include <stddef.h>
#include "config.h"

// --- Packet header (24 bytes, little-endian) ---
struct __attribute__((packed)) PacketHeader {
  uint8_t  magic[4];
  uint8_t  version;
  uint8_t  type;
  uint16_t flags;
  uint32_t frame_id;
  uint64_t timestamp_us;
  uint32_t payload_len;
};

// --- COBS decoder ---
class COBSDecoder {
public:
  COBSDecoder() { reset(); }

  void reset() {
    _out_len = 0;
    _code = 0;
    _block_remaining = 0;
    _started = false;
  }

  // Feed one byte. Returns true when a complete packet delimiter (0x00) is found.
  bool feed(uint8_t byte) {
    if (byte == 0x00) {
      // End of packet
      if (_started && _out_len > 0) {
        // Remove trailing zero added by block transitions (if any)
        if (_out_len > 0 && _pending_zero) {
          _out_len--;  // strip the last implicit zero
        }
        return true;
      }
      reset();
      return false;
    }

    _started = true;

    if (_block_remaining == 0) {
      // This byte is a COBS code
      _code = byte;
      _block_remaining = _code - 1;
      _pending_zero = (_code < 255);
    } else {
      // This byte is data
      if (_out_len < sizeof(_output)) {
        _output[_out_len++] = byte;
      }
      _block_remaining--;

      if (_block_remaining == 0 && _pending_zero) {
        // Insert implicit zero between blocks
        if (_out_len < sizeof(_output)) {
          _output[_out_len++] = 0x00;
        }
      }
    }
    return false;
  }

  const uint8_t* data() const { return _output; }
  size_t length() const { return _out_len; }

private:
  uint8_t _output[HEADER_SIZE + MAX_PAYLOAD_SIZE + CRC_SIZE + 64];
  size_t  _out_len;
  uint8_t _code;
  uint8_t _block_remaining;
  bool    _started;
  bool    _pending_zero;
};

// --- COBS encoder ---
size_t cobs_encode(const uint8_t* input, size_t len, uint8_t* output, size_t max_out);

// --- CRC32 ---
uint32_t crc32(const uint8_t* data, size_t len);

// --- Packet verification ---
bool verify_packet(const uint8_t* data, size_t len, PacketHeader* header, const uint8_t** payload);

// --- Packet building ---
size_t build_packet(uint8_t type, const uint8_t* payload, size_t payload_len,
                    uint8_t* output, size_t max_out);
