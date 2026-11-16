import ipaddress

import pytest

from app.security.ssrf import OutboundError, OutboundPolicy, _parse, host_allowed, is_blocked


def policy(**overrides: object) -> OutboundPolicy:
    return OutboundPolicy(**{"max_bytes": 1000, "timeout_seconds": 5, **overrides})  # type: ignore[arg-type]


def blocked(ip: str, allow_private: bool) -> bool:
    return is_blocked(ipaddress.ip_address(ip), allow_private)


ALWAYS_BLOCKED = [
    "169.254.169.254",
    "169.254.0.1",
    "0.0.0.0",
    "224.0.0.1",
    "239.255.255.250",
    "240.0.0.1",
    "255.255.255.255",
    "fe80::1",
    "::",
    "::7f00:1",
    "ff02::1",
    "::ffff:169.254.169.254",
    "::ffff:0.0.0.0",
    "64:ff9b::a9fe:a9fe",
    "2002:a9fe:a9fe::",
]
PRIVATE = [
    "127.0.0.1",
    "127.1.2.3",
    "10.0.0.5",
    "172.16.0.1",
    "172.31.255.254",
    "192.168.1.1",
    "100.64.0.1",
    "198.18.0.1",
    "::1",
    "fd00::1",
    "fc00::1",
    "::ffff:127.0.0.1",
    "::ffff:10.0.0.1",
    "64:ff9b::7f00:1",
    "64:ff9b::a00:1",
    "2002:7f00:1::",
    "2002:c0a8:101::",
]
PUBLIC = [
    "8.8.8.8",
    "1.1.1.1",
    "93.184.216.34",
    "2606:4700::1111",
    "::ffff:8.8.8.8",
    "64:ff9b::808:808",
]


@pytest.mark.parametrize("ip", ALWAYS_BLOCKED)
@pytest.mark.parametrize("allow_private", [True, False])
def test_some_addresses_are_never_allowed(ip: str, allow_private: bool) -> None:
    assert blocked(ip, allow_private)


@pytest.mark.parametrize("ip", PRIVATE)
def test_private_addresses_follow_the_flag(ip: str) -> None:
    assert blocked(ip, allow_private=False)
    assert not blocked(ip, allow_private=True)


@pytest.mark.parametrize("ip", PUBLIC)
@pytest.mark.parametrize("allow_private", [True, False])
def test_public_addresses_are_allowed(ip: str, allow_private: bool) -> None:
    assert not blocked(ip, allow_private)


def test_an_address_hidden_in_a_wrapper_is_judged_by_what_it_wraps() -> None:
    assert blocked("::ffff:7f00:1", False) and not blocked("::ffff:7f00:1", True)
    assert blocked("64:ff9b::7f00:1", False)
    assert blocked("2002:7f00:1::", False)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/x",
        "gopher://example.com/",
        "data:text/plain,hi",
        "javascript:alert(1)",
        "ws://example.com/",
        "//example.com/x",
        "example.com/x",
    ],
)
@pytest.mark.parametrize("allow_private", [True, False])
def test_only_http_and_https_urls_pass(url: str, allow_private: bool) -> None:
    with pytest.raises(OutboundError) as error:
        _parse(url, policy(allow_private=allow_private))
    assert error.value.code in {"scheme_not_allowed", "invalid_url"}


def test_http_needs_the_private_networks_flag() -> None:
    with pytest.raises(OutboundError) as error:
        _parse("http://example.com/", policy(allow_private=False))
    assert error.value.code == "scheme_not_allowed"

    assert _parse("http://example.com/", policy(allow_private=True))[1:] == ("example.com", 80)
    assert _parse("https://example.com/", policy(allow_private=False))[1:] == ("example.com", 443)


@pytest.mark.parametrize(
    "url",
    [
        "https://user:pw@example.com/",
        "https://example.com@127.0.0.1/",
        "http://evil.com@127.0.0.1:8000/",
        "https:///path",
        "https://",
        "https://exa mple.com/",
    ],
)
def test_credentials_in_a_url_and_missing_hosts_are_refused(url: str) -> None:
    with pytest.raises(OutboundError) as error:
        _parse(url, policy())
    assert error.value.code == "invalid_url"


@pytest.mark.parametrize(
    "host", ["127.1", "2130706433", "0x7f000001", "017700000001", "0177.0.0.1", "127.0.1", "0x7f.1"]
)
def test_numeric_ip_spellings_are_refused_even_when_private_is_allowed(host: str) -> None:
    with pytest.raises(OutboundError) as error:
        _parse(f"http://{host}/", policy(allow_private=True))
    assert error.value.code == "invalid_url"


@pytest.mark.parametrize(
    "host", ["127.0.0.1", "8.8.8.8", "[::1]", "localhost", "cafe", "a1.b2.example"]
)
def test_ordinary_hosts_still_parse(host: str) -> None:
    assert _parse(f"http://{host}/", policy())[1]


def test_the_fragment_trick_does_not_change_the_host() -> None:
    _, host, _ = _parse("https://127.0.0.1#@example.com/", policy())

    assert host == "127.0.0.1"


@pytest.mark.parametrize(
    ("host", "allowed", "expected"),
    [
        ("api.example.com", (), True),
        ("api.example.com", ("api.example.com",), True),
        ("API.Example.com.", ("api.example.com",), True),
        ("other.example.com", ("api.example.com",), False),
        ("a.b.example.com", ("*.example.com",), True),
        ("example.com", ("*.example.com",), False),
        ("badexample.com", ("*.example.com",), False),
        ("example.com.evil.com", ("*.example.com",), False),
    ],
)
def test_the_allowed_host_list(host: str, allowed: tuple[str, ...], expected: bool) -> None:
    assert host_allowed(host, allowed) is expected


def test_a_host_off_the_list_is_refused_before_anything_resolves() -> None:
    with pytest.raises(OutboundError) as error:
        _parse("https://other.example.com/", policy(allowed_hosts=("api.example.com",)))
    assert error.value.code == "host_not_allowed"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com:0/",
        "https://example.com:65536/",
        "https://example.com:-1/",
        "https://example.com:abc/",
        "https://example.com:443:80/",
        "https://exa\mple.com/",
        "https://127.0.0.1\@example.com/",
        "https://example.com%2f@127.0.0.1/",
        "https://exa%6dple.com/",
        "https://[fe80::1%25eth0]/",
        "https://①②⑦.0.0.1/",
    ],
)
def test_odd_ports_escapes_and_unicode_hosts_are_refused(url: str) -> None:
    with pytest.raises(OutboundError) as error:
        _parse(url, policy())
    assert error.value.code == "invalid_url"


@pytest.mark.parametrize(
    ("url", "host", "port"),
    [
        ("https://example.com#@127.0.0.1/", "example.com", 443),
        ("https://example.com?@127.0.0.1/", "example.com", 443),
        ("https://example.com:00443/", "example.com", 443),
        ("https://Bücher.example/", "xn--bcher-kva.example", 443),
        ("https://LOCALHOST:8080/", "localhost", 8080),
        ("http://[::1]:9000/", "::1", 9000),
    ],
)
def test_the_host_and_port_come_from_one_parse_so_tricks_cannot_split_them(
    url: str, host: str, port: int
) -> None:
    _, parsed_host, parsed_port = _parse(url, policy(allow_private=True))

    assert (parsed_host, parsed_port) == (host, port)
