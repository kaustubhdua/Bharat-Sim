import unittest

from worker.network_shaper import IFACE_RE, parse_netem_parameters, parameters_match


class NetworkShaperGuardTests(unittest.TestCase):
    def test_accepts_dedicated_test_veth_names(self):
        self.assertTrue(IFACE_RE.fullmatch("veth-bs-run01"))
        self.assertTrue(IFACE_RE.fullmatch("veth-bs-a"))

    def test_rejects_host_and_arbitrary_interfaces(self):
        for interface in ("eth0", "wlan0", "lo", "docker0", "veth0", "veth-bs-"):
            with self.subTest(interface=interface):
                self.assertFalse(IFACE_RE.fullmatch(interface))


class NetemParameterVerificationTests(unittest.TestCase):
    def test_parses_and_matches_tc_reported_parameters(self):
        output = "qdisc netem 8001: root refcnt 2 limit 1000 delay 180ms 30ms loss 2% rate 1200Kbit"
        observed = parse_netem_parameters(output)
        self.assertEqual(observed["latency_ms"], 180.0)
        self.assertEqual(observed["jitter_ms"], 30.0)
        self.assertEqual(observed["loss_pct"], 2.0)
        self.assertEqual(observed["rate_kbit"], 1200.0)
        self.assertTrue(parameters_match(observed, {
            "latency_ms": 180.0, "jitter_ms": 30.0, "loss_pct": 2.0, "rate_kbit": 1200.0,
        }))

    def test_converts_rate_units_and_zero_loss(self):
        observed = parse_netem_parameters("qdisc netem 8001: root delay 0.2s rate 1.2Mbit")
        self.assertEqual(observed["latency_ms"], 200.0)
        self.assertEqual(observed["jitter_ms"], 0.0)
        self.assertEqual(observed["loss_pct"], 0.0)
        self.assertEqual(observed["rate_kbit"], 1200.0)

    def test_missing_parameters_never_count_as_verified(self):
        observed = parse_netem_parameters("qdisc netem 8001: root limit 1000")
        self.assertFalse(parameters_match(observed, {
            "latency_ms": 180.0, "jitter_ms": 30.0, "loss_pct": 2.0, "rate_kbit": 1200.0,
        }))

    def test_zero_delay_and_loss_are_observed_as_zero(self):
        observed = parse_netem_parameters("qdisc netem 8001: root limit 1000 rate 16Kbit")
        self.assertEqual(observed["latency_ms"], 0.0)
        self.assertEqual(observed["jitter_ms"], 0.0)
        self.assertEqual(observed["loss_pct"], 0.0)
        self.assertEqual(observed["rate_kbit"], 16.0)

    def test_non_netem_output_has_no_observed_values(self):
        observed = parse_netem_parameters("qdisc fq_codel 0: root")
        self.assertIsNone(observed["latency_ms"])
        self.assertIsNone(observed["loss_pct"])
        self.assertIsNone(observed["rate_kbit"])


if __name__ == "__main__":
    unittest.main()
