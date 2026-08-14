"""Small network diagnostics used by the deployment UI."""

from __future__ import annotations

import ipaddress

import requests


def get_public_ipv4(timeout: float = 5.0) -> str:
    """Return the server's current outbound public IPv4 address."""
    response = requests.get("https://api.ipify.org", params={"format": "json"}, timeout=timeout)
    response.raise_for_status()
    value = str(response.json().get("ip", "")).strip()
    address = ipaddress.ip_address(value)
    if address.version != 4 or not address.is_global:
        raise ValueError("공인 IPv4 응답이 올바르지 않습니다.")
    return value


def is_ip_not_allowed(error: BaseException | str) -> bool:
    message = str(error).lower()
    return "ip address not allowed" in message or "access_denied" in message
