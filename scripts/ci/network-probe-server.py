#!/usr/bin/env python3
"""Disposable CI-only HTTP/HTTPS payload server for measuring real emulator traffic."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import ssl
import struct
from urllib.parse import parse_qs, urlsplit

DEFAULT_PAYLOAD_SIZE = 500_000
PAYLOAD_UNIT = b"BharatSim controlled network probe payload\n"


def build_payload(size: int) -> bytes:
    if size <= 0:
        return b""
    repetitions = (size // len(PAYLOAD_UNIT)) + 1
    return (PAYLOAD_UNIT * repetitions)[:size]


class ProbeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/health":
            body = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path in ("/__down", "/payload"):
            params = parse_qs(parsed.query)
            default_size = getattr(self.server, "default_payload_size", DEFAULT_PAYLOAD_SIZE)
            requested_str = params.get("bytes", [str(default_size)])[0]
            try:
                requested_bytes = int(requested_str)
            except ValueError:
                self.send_error(400, f"Invalid bytes parameter: {requested_str}")
                return

            cached_payload = getattr(self.server, "cached_payload", None)
            if cached_payload is not None and len(cached_payload) == requested_bytes:
                payload = cached_payload
            else:
                payload = build_payload(requested_bytes)

            try:
                self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 30))
            except Exception:
                pass

            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()

            # Linux netem performs all shaping; the server writes payload directly without chunk sleeps.
            try:
                chunk_size = 16384
                offset = 0
                while offset < len(payload):
                    to_write = min(chunk_size, len(payload) - offset)
                    self.wfile.write(payload[offset : offset + to_write])
                    offset += to_write
                self.wfile.flush()
                print(f"served_bytes={len(payload)} client={self.client_address[0]}", flush=True)

                # Keep connection alive while client drains through shaped link until client closes
                try:
                    self.connection.settimeout(15.0)
                    self.rfile.read(1)
                except Exception:
                    pass
            except (BrokenPipeError, ConnectionResetError):
                print(f"client_disconnected={self.client_address[0]}", flush=True)
            return

        self.send_error(404, f"Endpoint not found: {parsed.path}")

    def log_message(self, format: str, *args: object) -> None:
        print(f"probe_server {self.client_address[0]} {format % args}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0", help="Address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8443, help="Port to listen on (default: 8443)")
    parser.add_argument("--bytes", type=int, default=DEFAULT_PAYLOAD_SIZE, help="Default payload size in bytes")
    parser.add_argument("--cert", type=Path, default=None, help="Path to TLS server certificate (PEM)")
    parser.add_argument("--key", type=Path, default=None, help="Path to TLS server private key (PEM)")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ProbeHandler)
    server.daemon_threads = True
    server.default_payload_size = args.bytes
    server.cached_payload = build_payload(args.bytes)

    is_tls = bool(args.cert and args.key)
    if is_tls:
        if not args.cert.is_file():
            raise FileNotFoundError(f"TLS certificate not found: {args.cert}")
        if not args.key.is_file():
            raise FileNotFoundError(f"TLS private key not found: {args.key}")
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=str(args.cert), keyfile=str(args.key))
        server.socket = ctx.wrap_socket(server.socket, server_side=True)

    protocol = "https" if is_tls else "http"
    print(
        f"listening={protocol}://{args.host}:{args.port} default_bytes={args.bytes} tls={is_tls}",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
