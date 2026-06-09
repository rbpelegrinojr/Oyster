"""
LAN network scanner.

Performs a concurrent ping sweep of the local subnet to discover
devices that may be IP cameras.  No third-party tools required –
uses Python's subprocess for ICMP ping.
"""

from __future__ import annotations

import ipaddress
import platform
import subprocess
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

_MAX_WORKERS = 50
_PING_TIMEOUT = 1  # seconds


def _ping(ip: str) -> str | None:
    """Return ip if host responds to ping, else None."""
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(_PING_TIMEOUT * 1000), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(_PING_TIMEOUT), ip]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_PING_TIMEOUT + 1,
        )
        return ip if result.returncode == 0 else None
    except Exception:
        return None


def _resolve_hostname(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""


def get_local_subnet() -> str:
    """Best-effort detection of the local /24 subnet."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        # Return /24 subnet
        parts = local_ip.rsplit(".", 1)
        return parts[0] + ".0/24"
    except Exception:
        return "192.168.1.0/24"


def scan_network(subnet: str | None = None) -> List[Dict[str, str]]:
    """
    Scan *subnet* (CIDR notation) and return a list of responsive hosts.

    Each entry: {"ip": "...", "hostname": "..."}
    """
    if subnet is None:
        subnet = get_local_subnet()

    try:
        network = ipaddress.IPv4Network(subnet, strict=False)
    except ValueError:
        return []

    hosts = [str(h) for h in network.hosts()]
    alive: List[str] = []

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_ping, ip): ip for ip in hosts}
        for future in as_completed(futures):
            result = future.result()
            if result:
                alive.append(result)

    alive.sort(key=lambda ip: tuple(int(p) for p in ip.split(".")))

    results = []
    for ip in alive:
        hostname = _resolve_hostname(ip)
        results.append({"ip": ip, "hostname": hostname})
    return results
