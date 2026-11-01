import asyncio
import json
import time
import unittest

from scripts.ci.https_shaping_proxy import ShapingProxy


class ShapingProxyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.echo_server = await asyncio.start_server(self.echo, "127.0.0.1", 0)
        self.echo_port = self.echo_server.sockets[0].getsockname()[1]
        self.proxy = ShapingProxy(
            proxy_host="127.0.0.1",
            proxy_port=0,
            control_host="127.0.0.1",
            control_port=0,
            allowed_hosts={"127.0.0.1"},
            allowed_ports={self.echo_port},
        )
        await self.proxy.start()
        self.proxy_port = self.proxy.addresses()["proxy"][1]
        self.control_port = self.proxy.addresses()["control"][1]

    async def asyncTearDown(self):
        await self.proxy.close()
        self.echo_server.close()
        await self.echo_server.wait_closed()

    async def echo(self, reader, writer):
        try:
            data = await reader.readexactly(8)
            writer.write(data)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def tunnel(self, payload=b"bharatsm"):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.proxy_port)
        writer.write(
            f"CONNECT 127.0.0.1:{self.echo_port} HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{self.echo_port}\r\n\r\n".encode("ascii")
        )
        await writer.drain()
        response = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=2)
        self.assertIn(b"200 Connection Established", response)
        writer.write(payload)
        await writer.drain()
        received = await asyncio.wait_for(reader.readexactly(len(payload)), timeout=3)
        writer.close()
        await writer.wait_closed()
        return received

    async def test_connect_tunnel_records_bytes_and_config_generation(self):
        config = self.proxy.set_config({"label": "bandwidth-only", "delay_ms": 0, "rate_kbps": 384})
        self.assertEqual(config["generation"], 1)

        received = await self.tunnel()
        self.assertEqual(received, b"bharatsm")
        await asyncio.sleep(0.05)

        metrics = self.proxy.metrics()
        event = metrics["events"][-1]
        self.assertEqual(event["status"], "completed")
        self.assertEqual(event["host"], "127.0.0.1")
        self.assertEqual(event["generation"], 1)
        self.assertEqual(event["label"], "bandwidth-only")
        self.assertEqual(event["bytes_client_to_upstream"], 8)
        self.assertEqual(event["bytes_upstream_to_client"], 8)

    async def test_latency_profile_delays_both_directions(self):
        self.proxy.set_config({"label": "latency-only", "delay_ms": 100, "rate_kbps": 0})
        started = time.monotonic()
        received = await self.tunnel()
        elapsed = time.monotonic() - started

        self.assertEqual(received, b"bharatsm")
        self.assertGreaterEqual(elapsed, 0.08)
        event = None
        for _ in range(20):
            events = self.proxy.metrics()["events"]
            if events and events[-1]["label"] == "latency-only":
                event = events[-1]
                break
            await asyncio.sleep(0.05)
        self.assertIsNotNone(event, "proxy did not record the completed latency tunnel")
        self.assertGreaterEqual(event["delay_injected_ms"], 90.0)
        self.assertEqual(event["delayed_directions"], 2)

    async def test_control_endpoint_changes_profile_and_reports_metrics(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.control_port)
        body = json.dumps({"label": "latency-only", "delay_ms": 150, "rate_kbps": 0}).encode()
        writer.write(
            b"POST /config HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"Content-Type: application/json\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode()
            + body
        )
        await writer.drain()
        response = await reader.read()
        writer.close()
        await writer.wait_closed()
        header, payload = response.split(b"\r\n\r\n", 1)
        self.assertIn(b"200 OK", header)
        parsed = json.loads(payload)
        self.assertEqual(parsed["config"]["label"], "latency-only")
        self.assertEqual(parsed["config"]["delay_ms"], 150)

    async def test_proxy_rejects_non_allowlisted_destinations(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.proxy_port)
        writer.write(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=2)
        self.assertIn(b"403 Destination Not Allowed", response)
        writer.close()
        await writer.wait_closed()
        await asyncio.sleep(0.05)
        self.assertEqual(self.proxy.metrics()["events"][-1]["status"], "rejected")

    def test_profile_validation_rejects_mixed_latency_and_bandwidth(self):
        with self.assertRaises(ValueError):
            self.proxy.set_config({"label": "latency-only", "delay_ms": 150, "rate_kbps": 384})


if __name__ == "__main__":
    unittest.main()
