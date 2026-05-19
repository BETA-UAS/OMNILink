from core.mavlink import mavlink_v1_heartbeat_packet


def test_mavlink_v1_heartbeat_packet_is_stable():
    packet = mavlink_v1_heartbeat_packet(0)

    assert len(packet) == 17
    assert packet.hex() == "fe0900ffbe000000000006080000032842"
