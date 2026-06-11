"""
RTSP Stream Diagnostic Test
============================
Run this script to test whether your camera's RTSP stream is accessible
and to identify the most likely cause of failure.

Usage:
    python tests/test_rtsp_stream.py <RTSP_URL>

Example:
    python tests/test_rtsp_stream.py ******192.168.1.100:554/stream1

The script performs the following checks:
    1. URL format validation
    2. Network reachability (ping + TCP port check)
    3. OpenCV RTSP connection (with TCP transport)
    4. Frame read verification
    5. Frame decode and quality check

Each step reports PASS/FAIL with a diagnostic message explaining the
possible error and how to fix it.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Colour helpers for terminal output
# ---------------------------------------------------------------------------

def _green(text: str) -> str:
    return f"\033[92m{text}\033[0m"


def _red(text: str) -> str:
    return f"\033[91m{text}\033[0m"


def _yellow(text: str) -> str:
    return f"\033[93m{text}\033[0m"


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

def test_url_format(url: str) -> tuple[bool, str]:
    """Validate that the RTSP URL has the correct format."""
    if not url:
        return False, "No URL provided."

    parsed = urlparse(url)
    if parsed.scheme not in ("rtsp", "rtsps"):
        return False, (
            f"Invalid scheme '{parsed.scheme}'. Expected 'rtsp://' or 'rtsps://'.\n"
            f"  Example: ******192.168.1.100:554/stream1"
        )

    if not parsed.hostname:
        return False, (
            "No hostname/IP found in the URL.\n"
            "  Example: ******192.168.1.100:554/stream1"
        )

    return True, f"URL format OK — host={parsed.hostname}, port={parsed.port or 554}"


def test_network_reachability(url: str) -> tuple[bool, str]:
    """Check if the camera host is reachable on the network."""
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 554

    # TCP port check (more reliable than ping for cameras)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            return True, f"TCP connection to {host}:{port} succeeded."
        else:
            return False, (
                f"Cannot connect to {host}:{port} (TCP connection refused).\n"
                f"  Possible causes:\n"
                f"    • Camera is powered off or not connected to the network\n"
                f"    • Wrong IP address or port number\n"
                f"    • Firewall blocking the connection\n"
                f"    • Camera RTSP service is disabled in camera settings\n"
                f"  Try:\n"
                f"    • Ping the camera: ping {host}\n"
                f"    • Verify port in camera web UI (common ports: 554, 8554, 8080)\n"
                f"    • Check if camera and this machine are on the same subnet"
            )
    except socket.gaierror:
        return False, (
            f"DNS resolution failed for '{host}'.\n"
            f"  Use an IP address instead of a hostname, e.g.:\n"
            f"    ******192.168.1.100:554/stream1"
        )
    except socket.timeout:
        return False, (
            f"Connection to {host}:{port} timed out (5s).\n"
            f"  Possible causes:\n"
            f"    • Camera is on a different network/subnet\n"
            f"    • Firewall dropping packets (no reject, just timeout)\n"
            f"    • Network congestion or camera overloaded"
        )
    except OSError as e:
        return False, f"Network error: {e}"


def test_opencv_connection(url: str) -> tuple[bool, str, object]:
    """Try to open the RTSP stream with OpenCV using TCP transport."""
    try:
        import cv2
    except ImportError:
        return False, (
            "OpenCV (cv2) is not installed.\n"
            "  Install it with: pip install opencv-python"
        ), None

    # Force TCP transport (same as stream_manager.py)
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
        "rtsp_transport;tcp"
        "|analyzeduration;5000000"
        "|stimeout;5000000"
        "|timeout;5000000"
        "|max_delay;500000"
        "|reorder_queue_size;0"
        "|buffer_size;1024000"
    )

    cap = cv2.VideoCapture()
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 15000)
    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    print(f"    Attempting to open stream (timeout: 15s)...")
    start = time.time()
    cap.open(url, cv2.CAP_FFMPEG)
    elapsed = time.time() - start

    if not cap.isOpened():
        cap.release()
        return False, (
            f"OpenCV failed to open the RTSP stream (took {elapsed:.1f}s).\n"
            f"  Possible causes:\n"
            f"    • Wrong RTSP path (the part after the port, e.g. /stream1, /cam/realmonitor)\n"
            f"    • Invalid credentials (username/password in URL)\n"
            f"    • Camera requires digest authentication (not supported by all builds)\n"
            f"    • Stream codec not supported by this OpenCV/FFmpeg build\n"
            f"    • Camera has max connection limit reached\n"
            f"  Try:\n"
            f"    • Test URL in VLC: Media > Open Network Stream > paste URL\n"
            f"    • Check camera docs for correct RTSP path\n"
            f"    • Common paths: /stream1, /h264, /Streaming/Channels/101,\n"
            f"      /cam/realmonitor?channel=1&subtype=0"
        ), None

    return True, f"Stream opened successfully in {elapsed:.1f}s.", cap


def test_frame_read(cap) -> tuple[bool, str]:
    """Try to read frames from the opened stream."""
    import cv2

    # Grab a few frames to get past initial buffering
    for i in range(5):
        ret = cap.grab()
        if not ret and i == 0:
            return False, (
                "Failed to grab the first frame.\n"
                "  Possible causes:\n"
                "    • Stream disconnected immediately after opening\n"
                "    • Network is too slow / unstable for the stream bitrate\n"
                "    • Camera encoder issue"
            )

    ret, frame = cap.read()
    if not ret or frame is None:
        return False, (
            "cap.read() returned no frame data.\n"
            "  Possible causes:\n"
            "    • Stream bitrate too high for the network\n"
            "    • Codec decoding failure (try a sub-stream with lower resolution)\n"
            "    • WiFi interference causing packet loss"
        )

    h, w = frame.shape[:2]
    return True, f"Frame read OK — resolution: {w}x{h}"


def test_frame_quality(cap) -> tuple[bool, str]:
    """Read multiple frames and check for issues like all-black or frozen."""
    import cv2
    import numpy as np

    frames = []
    for _ in range(10):
        ret, frame = cap.read()
        if ret and frame is not None:
            frames.append(frame)
        time.sleep(0.05)

    if len(frames) < 3:
        return False, (
            f"Only {len(frames)}/10 frames were readable.\n"
            f"  The stream is unstable — likely network or bandwidth issues."
        )

    # Check if frames are all black
    avg_brightness = np.mean(frames[0])
    if avg_brightness < 5:
        return False, (
            "Frames appear to be all black (avg brightness < 5).\n"
            "  Possible causes:\n"
            "    • Camera lens cap is on\n"
            "    • Camera is in night mode without IR LEDs\n"
            "    • Wrong stream channel selected"
        )

    # Check if frames are frozen (identical)
    if len(frames) >= 3:
        diff = cv2.absdiff(frames[0], frames[-1])
        if np.sum(diff) == 0:
            return False, (
                "All frames are identical — stream may be frozen.\n"
                "  Possible causes:\n"
                "    • Camera is outputting a static test image\n"
                "    • Encoder is stuck / camera needs reboot"
            )

    return True, f"Frame quality OK — {len(frames)}/10 frames received, stream is live."


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_diagnostics(url: str) -> bool:
    """Run all RTSP diagnostics and return True if all pass."""
    print()
    print(_bold("=" * 60))
    print(_bold("  Oyster RTSP Stream Diagnostic Tool"))
    print(_bold("=" * 60))
    print(f"  URL: {url}")
    print("=" * 60)
    print()

    all_passed = True
    cap = None

    # Test 1: URL format
    print(_bold("[1/5] URL Format Validation"))
    passed, msg = test_url_format(url)
    if passed:
        print(f"  {_green('PASS')}: {msg}")
    else:
        print(f"  {_red('FAIL')}: {msg}")
        all_passed = False
        print(f"\n{_red('Stopping — fix the URL format before proceeding.')}")
        return False
    print()

    # Test 2: Network reachability
    print(_bold("[2/5] Network Reachability"))
    passed, msg = test_network_reachability(url)
    if passed:
        print(f"  {_green('PASS')}: {msg}")
    else:
        print(f"  {_red('FAIL')}: {msg}")
        all_passed = False
        print(f"\n{_red('Stopping — camera is not reachable on the network.')}")
        return False
    print()

    # Test 3: OpenCV connection
    print(_bold("[3/5] OpenCV RTSP Connection (TCP transport)"))
    passed, msg, cap = test_opencv_connection(url)
    if passed:
        print(f"  {_green('PASS')}: {msg}")
    else:
        print(f"  {_red('FAIL')}: {msg}")
        all_passed = False
        print(f"\n{_red('Stopping — cannot open stream with OpenCV.')}")
        return False
    print()

    # Test 4: Frame read
    print(_bold("[4/5] Frame Read"))
    passed, msg = test_frame_read(cap)
    if passed:
        print(f"  {_green('PASS')}: {msg}")
    else:
        print(f"  {_red('FAIL')}: {msg}")
        all_passed = False
        if cap:
            cap.release()
        return False
    print()

    # Test 5: Frame quality
    print(_bold("[5/5] Frame Quality & Stream Stability"))
    passed, msg = test_frame_quality(cap)
    if passed:
        print(f"  {_green('PASS')}: {msg}")
    else:
        print(f"  {_yellow('WARN')}: {msg}")
        all_passed = False
    print()

    if cap:
        cap.release()

    # Summary
    print("=" * 60)
    if all_passed:
        print(_green("  ALL TESTS PASSED — Stream is working correctly."))
        print("  The camera should work in Oyster's Dashboard, Training,")
        print("  and Zone Setup pages.")
    else:
        print(_yellow("  SOME TESTS FAILED — See messages above for details."))
        print()
        print("  Common solutions:")
        print("    1. Verify the RTSP URL in VLC (Media > Open Network Stream)")
        print("    2. Ensure camera and PC are on the same network/subnet")
        print("    3. Try the sub-stream URL for lower bandwidth requirements")
        print("    4. Restart the camera if it has max connection limits")
        print("    5. Check camera firmware for RTSP compatibility")
    print("=" * 60)
    print()
    return all_passed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/test_rtsp_stream.py <RTSP_URL>")
        print()
        print("Example:")
        print("  python tests/test_rtsp_stream.py ******192.168.1.100:554/stream1")
        sys.exit(1)

    rtsp_url = sys.argv[1]
    success = run_diagnostics(rtsp_url)
    sys.exit(0 if success else 1)
