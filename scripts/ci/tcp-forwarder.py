#!/usr/bin/env python3
"""Simple non-blocking bidirectional TCP stream forwarder for CI network routing."""
from __future__ import annotations

import argparse
import socket
import sys
import threading


def pipe(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try:
            src.close()
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=8443)
    parser.add_argument("--target-host", default="198.18.77.2")
    parser.add_argument("--target-port", type=int, default=8443)
    args = parser.parse_args()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.listen_host, args.listen_port))
    server.listen(128)
    print(
        f"forwarder listening on {args.listen_host}:{args.listen_port} -> {args.target_host}:{args.target_port}",
        flush=True,
    )

    try:
        while True:
            client, _ = server.accept()
            try:
                target = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                target.connect((args.target_host, args.target_port))
                t1 = threading.Thread(target=pipe, args=(client, target), daemon=True)
                t2 = threading.Thread(target=pipe, args=(target, client), daemon=True)
                t1.start()
                t2.start()
            except Exception as exc:
                print(f"forwarder connect error: {exc}", flush=True)
                try:
                    client.close()
                except Exception:
                    pass
    except KeyboardInterrupt:
        pass
    finally:
        server.close()


if __name__ == "__main__":
    main()

