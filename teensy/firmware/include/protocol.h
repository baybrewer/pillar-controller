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
    _remaining = 0;
    _last_code = 0;
    _had_block = false;
    _started = false;
  }

  // Feed one byte. Returns true when a complete packet delimiter (0x00) is found.
  bool feed(uint8_t byte) {
    if (byte == 0x00) {
      // Delimiter — packet complete
      bool valid = _started && _out_len > 0;
      return valid;
    }

    _started = true;

    if (_remaining == 0) {
      // This is a code byte
      // If we had a previous block that was < 255, insert implicit zero
      if (_had_block && _last_code < 255) {
        if (_out_len < sizeof(_output)) {
          _output[_out_len++] = 0x00;
        }
      }
      _last_code = byte;
      _remaining = byte - 1;
      _had_block = true;
    } else {
      // Data byte
      if (_out_len < sizeof(_output)) {
        _output[_out_len++] = byte;
      }
      _remaining--;
    }
    return false;
  }

  const uint8_t* data() const { return _output; }
  size_t length() const { return _out_len; }

private:
  uint8_t _output[HEADER_SIZE + MAX_PAYLOAD_SIZE + CRC_SIZE + 64];
  size_t _out_len;
  uint8_t _remaining;
  uint8_t _last_code;
  bool _had_block;
  bool _started;
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
