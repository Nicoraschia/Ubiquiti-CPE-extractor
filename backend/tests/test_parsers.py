from pathlib import Path

from cpe_scanner.parsers import (
    Lease,
    classify_role,
    parse_dhcpd_leases,
    parse_mca_status,
    parse_system_cfg,
    parse_wstalist,
)

FIX = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FIX / name).read_text()


def test_system_cfg_extracts_values_and_drops_secrets():
    cfg = parse_system_cfg(read("ap_system.cfg"))
    assert cfg["resolv.host.1.name"] == "AP_TEST_OE"
    assert cfg["wireless.1.ssid"] == "AP-TEST"
    assert cfg["radio.1.mode"] == "master"
    leaked = [k for k in cfg if "psk" in k or "password" in k or k in ("unms.uri", "snmp.community")]
    assert leaked == []


def test_system_cfg_keeps_equals_inside_value():
    assert parse_system_cfg("wireless.1.ssid=a=b\n") == {"wireless.1.ssid": "a=b"}


def test_mca_status_parses_comma_header_and_lines():
    mca = parse_mca_status(read("ap_mca_status.txt"))
    assert mca["deviceName"] == "AP_TEST_OE"
    assert mca["platform"] == "Rocket 5AC Lite"
    assert mca["deviceIp"] == "192.168.15.205"
    assert mca["wlanOpmode"] == "ap-ptmp-mixed"
    assert mca["wlanConnections"] == "7"


def test_mca_status_device_name_with_comma():
    mca = parse_mca_status("deviceName=Perez, Juan,deviceId=AA:BB,platform=LBE")
    assert mca["deviceName"] == "Perez, Juan"
    assert mca["platform"] == "LBE"


def test_classify_role():
    assert classify_role({"wlanOpmode": "ap-ptmp-mixed"}) == "ap"
    assert classify_role({"wlanOpmode": "sta-ptmp"}) == "cpe"
    assert classify_role({}, {"radio.1.mode": "master"}) == "ap"
    assert classify_role({}, {"radio.1.mode": "managed"}) == "cpe"
    assert classify_role({}) == "unknown"


def test_dhcpd_leases_real_line():
    assert parse_dhcpd_leases(read("cpe_dhcpd.leases")) == [
        Lease(1618662891, "48:b2:5d:b2:0f:0c", "192.168.9.101", "HG8145V5", "01:48:b2:5d:b2:0f:0c")
    ]


def test_dhcpd_leases_keeps_every_lease_and_handles_missing_fields():
    text = (
        "1 aa:aa:aa:aa:aa:01 192.168.9.2 Tenda 01:aa:aa:aa:aa:aa:01\n"
        "2 aa:aa:aa:aa:aa:02 192.168.9.3 01:aa:aa:aa:aa:aa:02\n"
        "3 AA:AA:AA:AA:AA:03 192.168.9.4\n"
        "\n"
        "garbage line\n"
    )
    leases = parse_dhcpd_leases(text)
    assert [l.ip for l in leases] == ["192.168.9.2", "192.168.9.3", "192.168.9.4"]
    assert leases[1].hostname is None and leases[1].client_id == "01:aa:aa:aa:aa:aa:02"
    assert leases[2].mac == "aa:aa:aa:aa:aa:03" and leases[2].client_id is None


def test_wstalist_parses_stations_with_trailing_prompt():
    stations = parse_wstalist(read("ap_wstalist.txt"))
    assert len(stations) == 3
    s = stations[0]
    assert (s.mac, s.ip, s.name, s.platform) == ("b4:fb:e4:6c:a5:df", "192.168.15.115", "Cliente 1", "NanoStation 5AC")
    assert (s.signal, s.remote_signal, s.dl_linkscore) == (-47, -48, 94)
    assert stations[2].mode == "unknown"  # LiteBeam M5 con airOS v6


def test_wstalist_empty_or_garbage():
    assert parse_wstalist("") == []
    assert parse_wstalist("[]") == []
