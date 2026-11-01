#!/usr/bin/env python3
"""Allowlisted HTTP CONNECT proxy for repeatable Android fixture network tests.

The proxy does not terminate TLS or inspect application payloads. It only
records host/byte/timing metadata and applies per-direction delay/rate limits.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import deque
from typing import Any
from urllib.parse import urlsplit


class ShapingProxy:
    def __init__(
        self,
        *,
        proxy_host: str = "0.0.0.0",
        proxy_port: int = 8888,
        control_host: str = "127.0.0.1",
        control_port: int = 8889,
        allowed_hosts: set[str] | None = None,
        allowed_ports: set[int] | None = None,
        target_ips: dict[str, str] | None = None,
        max_events: int = 200,
    ) -> None:
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.control_host = control_host
        self.control_port = control_port
        self.allowed_hosts = {host.lower() for host in (allowed_hosts or {"raw.githubusercontent.com"})}
        self.allowed_ports = allowed_ports or {443}
        self.target_ips = {host.lower(): ip for host, ip in (target_ips or {}).items()}
        self.config: dict[str, Any] = {
            "generation": 0,
            "label": "baseline",
            "delay_ms": 0,
            "rate_kbps": 0,
        }
        self.events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self.next_event_id = 1
        self.proxy_server: asyncio.AbstractServer | None = None
        self.control_server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self.proxy_server = await asyncio.start_server(
            self.handle_proxy_client, self.proxy_host, self.proxy_port, limit=16_384
        )
        self.control_server = await asyncio.start_server(
            self.handle_control_client, self.control_host, self.control_port, limit=16_384
        )

    async def close(self) -> None:
        for server in (self.proxy_server, self.control_server):
            if server is not None:
                server.close()
                await server.wait_closed()

    def addresses(self) -> dict[str, tuple[str, int]]:
        proxy = self.proxy_server.sockets[0].getsockname() if self.proxy_server and self.proxy_server.sockets else (self.proxy_host, self.proxy_port)
        control = self.control_server.sockets[0].getsockname() if self.control_server and self.control_server.sockets else (self.control_host, self.control_port)
        return {"proxy": (str(proxy[0]), int(proxy[1])), "control": (str(control[0]), int(control[1]))}

    def set_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        label = payload.get("label")
        delay_ms = payload.get("delay_ms")
        rate_kbps = payload.get("rate_kbps")
        if label not in {"baseline", "bandwidth-only", "latency-only"}:
            raise ValueError("label must be baseline, bandwidth-only, or latency-only")
        if not isinstance(delay_ms, int) or isinstance(delay_ms, bool) or not 0 <= delay_ms <= 5000:
            raise ValueError("delay_ms must be an integer between 0 and 5000")
        if not isinstance(rate_kbps, int) or isinstance(rate_kbps, bool) or not 0 <= rate_kbps <= 100_000:
            raise ValueError("rate_kbps must be an integer between 0 and 100000")
        if label == "baseline" and (delay_ms != 0 or rate_kbps != 0):
            raise ValueError("baseline requires zero delay and unlimited bandwidth")
        if label == "bandwidth-only" and (delay_ms != 0 or rate_kbps <= 0):
            raise ValueError("bandwidth-only requires a positive rate and zero delay")
        if label == "latency-only" and (delay_ms <= 0 or rate_kbps != 0):
            raise ValueError("latency-only requires positive delay and unlimited bandwidth")
        self.config = {
            "generation": int(self.config["generation"]) + 1,
            "label": label,
            "delay_ms": delay_ms,
            "rate_kbps": rate_kbps,
        }
        return dict(self.config)

    def metrics(self, after: int = 0) -> dict[str, Any]:
        events = [dict(event) for event in self.events if int(event["id"]) > after]
        return {
            "status": "ok",
            "config": dict(self.config),
            "last_event_id": self.next_event_id - 1,
            "events": events,
        }

    async def _send_proxy_response(self, writer: asyncio.StreamWriter, status: int, reason: str) -> None:
        body = (reason + "\n").encode("utf-8")
        response = (
            f"HTTP/1.1 {status} {reason}\r\n"
            "Connection: close\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n\r\n"
        )
        writer.write(response.encode("ascii") + body)
        await writer.drain()

    async def _relay(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        delay_ms: int,
        rate_kbps: int,
        event: dict[str, Any] | None = None,
    ) -> int:
        loop = asyncio.get_running_loop()
        started = loop.time()
        total = 0
        first_chunk = True
        rate_bytes_per_second = (rate_kbps * 1000 / 8) if rate_kbps else 0.0
        while True:
            chunk = await reader.read(16_384)
            if not chunk:
                break
            if first_chunk and delay_ms:
                # Split the configured RTT evenly across the two relay directions.
                half_delay_ms = delay_ms / 2
                delay_started = loop.time()
                await asyncio.sleep(half_delay_ms / 1000)
                actual_delay_ms = (loop.time() - delay_started) * 1000
                if event is not None:
                    event["delay_injected_ms"] = round(
                        float(event.get("delay_injected_ms", 0.0)) + actual_delay_ms, 2
                    )
                    event["delayed_directions"] = int(event.get("delayed_directions", 0)) + 1
                first_chunk = False
            elif first_chunk:
                first_chunk = False
            total += len(chunk)
            if rate_bytes_per_second:
                target_elapsed = total / rate_bytes_per_second
                elapsed = loop.time() - started
                if target_elapsed > elapsed:
                    await asyncio.sleep(target_elapsed - elapsed)
            writer.write(chunk)
            await writer.drain()
        return total

    async def handle_proxy_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        event: dict[str, Any] = {
            "id": self.next_event_id,
            "status": "started",
            "started_at": time.time(),
            "bytes_client_to_upstream": 0,
            "bytes_upstream_to_client": 0,
            "delay_injected_ms": 0.0,
            "delayed_directions": 0,
        }
        self.next_event_id += 1
        upstream_writer: asyncio.StreamWriter | None = None
        try:
            header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=8)
            if len(header) > 8192:
                raise ValueError("proxy request headers exceed 8 KiB")
            lines = header.decode("iso-8859-1").split("\r\n")
            request_parts = lines[0].split()
            if len(request_parts) != 3 or request_parts[0].upper() != "CONNECT":
                await self._send_proxy_response(writer, 405, "CONNECT Required")
                event.update({"status": "rejected", "error": "only HTTPS CONNECT is supported"})
                return
            host_port = request_parts[1]
            host, separator, port_text = host_port.rpartition(":")
            if not separator or not port_text.isdigit():
                await self._send_proxy_response(writer, 400, "Invalid CONNECT authority")
                event.update({"status": "rejected", "error": "invalid CONNECT authority"})
                return
            host = host.strip("[]").lower()
            port = int(port_text)
            event.update({"host": host, "port": port})
            if host not in self.allowed_hosts or port not in self.allowed_ports:
                await self._send_proxy_response(writer, 403, "Destination Not Allowed")
                event.update({"status": "rejected", "error": "destination is not allowlisted"})
                return

            config = dict(self.config)
            event.update({
                "generation": config["generation"],
                "label": config["label"],
                "delay_ms": config["delay_ms"],
                "rate_kbps": config["rate_kbps"],
            })
            upstream_host = self.target_ips.get(host, host)
            event["upstream_target_ip"] = upstream_host
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(upstream_host, port), timeout=10
            )
            peer = upstream_writer.get_extra_info("peername")
            event["upstream_ip"] = str(peer[0]) if peer else upstream_host
            writer.write(
                b"HTTP/1.1 200 Connection Established\r\n"
                b"Proxy-Agent: BharatSimFixtureProxy/1\r\n\r\n"
            )
            await writer.drain()
            up_task = asyncio.create_task(
                self._relay(reader, upstream_writer, delay_ms=config["delay_ms"], rate_kbps=config["rate_kbps"], event=event)
            )
            down_task = asyncio.create_task(
                self._relay(upstream_reader, writer, delay_ms=config["delay_ms"], rate_kbps=config["rate_kbps"], event=event)
            )
            try:
                up_bytes, down_bytes = await asyncio.wait_for(asyncio.gather(up_task, down_task), timeout=90)
            except Exception:
                up_task.cancel()
                down_task.cancel()
                raise
            event.update({
                "status": "completed",
                "bytes_client_to_upstream": up_bytes,
                "bytes_upstream_to_client": down_bytes,
            })
        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError) as exc:
            event.update({"status": "disconnected", "error": type(exc).__name__})
        except Exception as exc:
            event.update({"status": "error", "error": f"{type(exc).__name__}: {str(exc)[:240]}"})
            try:
                await self._send_proxy_response(writer, 502, "Proxy Error")
            except Exception:
                pass
        finally:
            event["duration_ms"] = round((time.time() - event["started_at"]) * 1000, 2)
            event.pop("started_at", None)
            self.events.append(event)
            # Keep exact upstream-connect failure and byte/timing evidence in
            # the CI artifact; a generic HTTP 502 alone is not diagnosable.
            print(json.dumps(event, sort_keys=True, separators=(",", ":")), flush=True)
            if upstream_writer is not None:
                upstream_writer.close()
                try:
                    await upstream_writer.wait_closed()
                except Exception:
                    pass
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def handle_control_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        status = 200
        try:
            header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
            if len(header) > 8192:
                raise ValueError("control request headers exceed 8 KiB")
            lines = header.decode("iso-8859-1").split("\r\n")
            parts = lines[0].split()
            if len(parts) != 3:
                raise ValueError("invalid HTTP request line")
            method, target, _ = parts
            headers = {}
            for line in lines[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().lower()] = value.strip()
            length = int(headers.get("content-length", "0"))
            if length < 0 or length > 4096:
                raise ValueError("control request body exceeds 4 KiB")
            body = await reader.readexactly(length) if length else b""
            if method == "GET" and target.startswith("/health"):
                payload = {"status": "ok", "config": dict(self.config)}
            elif method == "GET" and target.startswith("/metrics"):
                query = urlsplit(target).query
                after = 0
                for field in query.split("&"):
                    if field.startswith("after="):
                        after = int(field.split("=", 1)[1])
                payload = self.metrics(after=after)
            elif method == "POST" and target == "/config":
                parsed = json.loads(body.decode("utf-8"))
                if not isinstance(parsed, dict):
                    raise ValueError("config body must be an object")
                payload = {"status": "ok", "config": self.set_config(parsed)}
            elif method == "POST" and target == "/reset":
                payload = {"status": "ok", "config": self.set_config({"label": "baseline", "delay_ms": 0, "rate_kbps": 0})}
            else:
                status = 404
                payload = {"error": "not found"}
        except Exception as exc:
            status = 400
            payload = {"error": f"{type(exc).__name__}: {str(exc)[:240]}"}
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        reason = "OK" if status == 200 else "Bad Request" if status == 400 else "Not Found"
        response = (
            f"HTTP/1.1 {status} {reason}\r\n"
            "Connection: close\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(encoded)}\r\n\r\n"
        )
        writer.write(response.encode("ascii") + encoded)
        await writer.drain()
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def _serve(args: argparse.Namespace) -> None:
    proxy = ShapingProxy(
        proxy_host=args.proxy_host,
        proxy_port=args.proxy_port,
        control_host=args.control_host,
        control_port=args.control_port,
        allowed_hosts=set(args.allowed_host),
        allowed_ports=set(args.allowed_port),
        target_ips=dict(args.target_ip),
    )
    await proxy.start()
    print(json.dumps({"status": "listening", "addresses": proxy.addresses(), "allowed_hosts": sorted(proxy.allowed_hosts)}), flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await proxy.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proxy-host", default="0.0.0.0")
    parser.add_argument("--proxy-port", type=int, default=8888)
    parser.add_argument("--control-host", default="127.0.0.1")
    parser.add_argument("--control-port", type=int, default=8889)
    parser.add_argument("--allowed-host", action="append", default=["raw.githubusercontent.com"])
    parser.add_argument("--allowed-port", action="append", type=int, default=[443])
    parser.add_argument("--target-ip", action="append", default=[], metavar="HOST=IP")
    args = parser.parse_args()
    target_ips = {}
    for item in args.target_ip:
        host, separator, ip = item.partition("=")
        if not separator or not host or not ip:
            parser.error("--target-ip must be HOST=IP")
        target_ips[host.lower()] = ip
    args.target_ip = list(target_ips.items())
    try:
        asyncio.run(_serve(args))
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
