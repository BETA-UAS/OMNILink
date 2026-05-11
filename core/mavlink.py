import struct


def x25_crc_init() -> int:
    return 0xFFFF


def x25_crc_accumulate(crc: int, byte_value: int) -> int:
    tmp = (byte_value ^ (crc & 0xFF)) & 0xFF
    tmp = (tmp ^ ((tmp << 4) & 0xFF)) & 0xFF
    return ((crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)) & 0xFFFF


def x25_crc_accumulate_buf(crc: int, data: bytes) -> int:
    for byte_value in data:
        crc = x25_crc_accumulate(crc, byte_value)
    return crc


def mavlink_v1_heartbeat_packet(sequence: int) -> bytes:
    start_byte = 0xFE
    payload_length = 9
    message_id = 0
    system_id = 255
    component_id = 190
    mav_type = 6
    autopilot = 8
    base_mode = 0
    system_status = 0
    mavlink_version = 3

    payload = struct.pack("<I", 0) + struct.pack(
        "<BBBBB",
        mav_type,
        autopilot,
        base_mode,
        system_status,
        mavlink_version,
    )
    header = struct.pack(
        "<BBBBB",
        payload_length,
        sequence & 0xFF,
        system_id,
        component_id,
        message_id,
    )

    crc = x25_crc_accumulate_buf(x25_crc_accumulate_buf(x25_crc_init(), header), payload)
    crc = x25_crc_accumulate(crc, 50)

    return bytes([start_byte]) + header + payload + struct.pack("<H", crc)
