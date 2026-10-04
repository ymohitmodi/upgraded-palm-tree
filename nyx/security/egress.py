"""Egress / SSRF protection for autonomous web access.

An autonomous agent that fetches attacker-influenced URLs is a Server-Side
Request Forgery (SSRF) risk: a poisoned filing or search result can point the
crawler at ``http://169.254.169.254/`` (cloud metadata → credentials) or at
internal services on ``localhost``/RFC-1918. This module enforces, in order:

1. scheme allowlist (http/https only),
2. optional domain allowlist (deny-by-default when configured),
3. resolution guard — the host must not resolve to a loopback, private,
   link-local, or cloud-metadata address.

Aligned with OWASP LLM07 (insecure plugin/tool design) and classic SSRF defense.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# Cloud metadata endpoints (AWS/GCP/Azure/OpenStack) — always denied.
_METADATA_HOSTS = {"169.254.169.254", "metadata.google.internal", "100.100.100.200"}


class EgressBlocked(PermissionError):
    """Raised when a URL is denied by egress policy."""


def _addr_is_forbidden(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return (addr.is_loopback or addr.is_private or addr.is_link_local
            or addr.is_multicast or addr.is_reserved or addr.is_unspecified)


def check_url(url: str, allowed_domains: tuple[str, ...] = (), *, resolve: bool = True) -> None:
    """Raise EgressBlocked if the URL violates egress policy; return None if OK."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise EgressBlocked(f"scheme not allowed: {parsed.scheme!r}")
    host = (parsed.hostname or "").lower()
    if not host:
        raise EgressBlocked("missing host")
    if host in _METADATA_HOSTS:
        raise EgressBlocked(f"cloud metadata endpoint blocked: {host}")

    if allowed_domains:
        allow = tuple(d.lower() for d in allowed_domains)
        if not any(host == d or host.endswith("." + d) for d in allow):
            raise EgressBlocked(f"domain not in allowlist: {host}")

    # Literal-IP hosts can be checked directly; names need resolution.
    try:
        ipaddress.ip_address(host)
        literals = [host]
    except ValueError:
        if not resolve:
            return
        try:
            literals = [ai[4][0] for ai in socket.getaddrinfo(host, None)]
        except OSError as exc:
            raise EgressBlocked(f"cannot resolve host: {host}") from exc

    for ip in literals:
        if ip in _METADATA_HOSTS or _addr_is_forbidden(ip):
            raise EgressBlocked(f"host resolves to a forbidden address: {host} -> {ip}")
