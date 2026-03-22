# backend/core/url_validation.py
"""
URL validation utilities to prevent SSRF attacks.

Validates that user-supplied URLs point to public internet hosts,
blocking requests to internal/private IPs, cloud metadata endpoints,
and non-HTTP schemes.
"""

import ipaddress
import socket
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Private/reserved IP ranges that should never be targeted
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("255.255.255.255/32"),
    # IPv6
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::ffff:127.0.0.0/104"),
    ipaddress.ip_network("::ffff:10.0.0.0/104"),
    ipaddress.ip_network("::ffff:172.16.0.0/108"),
    ipaddress.ip_network("::ffff:192.168.0.0/112"),
    ipaddress.ip_network("::ffff:169.254.0.0/112"),
]


def _is_private_ip(host: str) -> bool:
    """Check if a hostname/IP resolves to a private or reserved address."""
    try:
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in _BLOCKED_NETWORKS)
    except ValueError:
        pass

    # Hostname — resolve and check all addresses
    try:
        results = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _family, _type, _proto, _canonname, sockaddr in results:
            ip_str = sockaddr[0]
            try:
                addr = ipaddress.ip_address(ip_str)
                if any(addr in net for net in _BLOCKED_NETWORKS):
                    return True
            except ValueError:
                continue
    except socket.gaierror:
        # Cannot resolve — let the HTTP client deal with the error
        return False

    return False


def validate_webhook_url(url: str) -> str | None:
    """
    Validate a webhook URL is safe to send requests to.

    Returns None if valid, or an error message string if invalid.
    """
    if not url:
        return "URL is empty"

    parsed = urlparse(url)

    if parsed.scheme not in ("https", "http"):
        return f"URL scheme '{parsed.scheme}' is not allowed (must be http or https)"

    if not parsed.hostname:
        return "URL has no hostname"

    if _is_private_ip(parsed.hostname):
        return "URL points to a private or reserved IP address"

    return None


def validate_scraping_url(url: str) -> str | None:
    """
    Validate a scraping target URL is safe to fetch.

    Returns None if valid, or an error message string if invalid.
    """
    if not url:
        return "URL is empty"

    parsed = urlparse(url)

    if parsed.scheme not in ("https", "http"):
        return f"URL scheme '{parsed.scheme}' is not allowed (must be http or https)"

    if not parsed.hostname:
        return "URL has no hostname"

    if _is_private_ip(parsed.hostname):
        return "URL points to a private or reserved IP address"

    return None
