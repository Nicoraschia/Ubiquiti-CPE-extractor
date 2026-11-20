from cpe_scanner.discovery import discover, hosts_in


def test_hosts_in_excludes_network_and_broadcast():
    hosts = hosts_in("192.168.15.0/30")
    assert hosts == ["192.168.15.1", "192.168.15.2"]


def test_hosts_in_accepts_host_bits():
    assert len(hosts_in("192.168.15.77/24")) == 254


def test_discover_skips_closed_ports():
    # 127.0.0.1/32 sin sshd local (el contenedor no corre uno).
    assert discover("127.0.0.1/32") == []
