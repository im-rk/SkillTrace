"""
Round-trips a message through /ws/echo-test (only registered when ENABLE_WS_ECHO_SPIKE=true --
see app/main.py). Run this against a newly deployed host's reverse-proxied URL BEFORE
trusting it with the real exam-session WebSocket: this endpoint is a 10-line stand-in,
much cheaper to debug than the full live-session-gateway stack if the platform's proxy
turns out not to pass WebSocket upgrades through correctly.

    uv run python -m scripts.ws_echo_check ws://localhost/ws/echo-test
    uv run python -m scripts.ws_echo_check wss://your-deployed-host.example.com/ws/echo-test
"""
import asyncio
import sys

import websockets


async def check(url: str) -> bool:
    message = "skilltrace-ws-spike"
    try:
        async with websockets.connect(url, open_timeout=10) as ws:
            await ws.send(message)
            reply = await asyncio.wait_for(ws.recv(), timeout=10)
    except Exception as exc:  # noqa: BLE001 -- report whatever went wrong, don't just crash
        print(f"FAILED: could not complete a round trip against {url}: {exc}")
        return False

    expected = f"echo: {message}"
    if reply != expected:
        print(f"FAILED: expected {expected!r}, got {reply!r}")
        return False
    print(f"OK: {url} echoed back correctly")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <ws-or-wss-url>")
    raise SystemExit(0 if asyncio.run(check(sys.argv[1])) else 1)
