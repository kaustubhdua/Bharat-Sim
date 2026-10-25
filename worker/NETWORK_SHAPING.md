# Network shaping prototype (Linux)

BharatSim now includes a guarded `tc/netem` adapter for a dedicated Linux test veth. The adapter is opt-in, requires root and refuses interface names outside `veth-bs-<suffix>` to reduce the chance of changing a host's normal network interface.

## Scope and limitations

- Shapes outbound traffic on the specified interface only.
- Does not create network namespaces or veth pairs automatically.
- Does not prove emulator traffic uses the selected interface.
- Does not currently shape inbound traffic, configure IFB, or verify measured throughput/latency against a controlled endpoint.
- Clearing deletes the root qdisc on the dedicated veth; use only a disposable test interface with no pre-existing qdisc configuration.

## Example

Run only inside an isolated Linux network namespace with a dedicated veth already created:

```bash
export BHARATSIM_ENABLE_NETEM=true
sudo -E python worker/network_shaper.py apply --interface veth-bs-run01 --latency-ms 180 --jitter-ms 30 --loss-pct 2 --rate-kbit 1200
sudo -E python worker/network_shaper.py verify --interface veth-bs-run01
sudo -E python worker/network_shaper.py clear --interface veth-bs-run01
```

The apply action now parses the active `tc` qdisc report and compares reported delay, jitter, loss and rate against the requested profile. It exits non-zero when parameters are missing or mismatch. The `verify` action checks qdisc presence only because it does not receive a target profile; it does not verify end-to-end traffic. Even a `parameters_match` result proves only that `tc` reports the requested qdisc settings on this interface—not that Android/emulator traffic traverses it or that a remote endpoint experienced those exact values. Before integrating into a run, route emulator traffic through the namespace, probe a known endpoint, record measured latency/throughput/loss and store the result with the run ID.
