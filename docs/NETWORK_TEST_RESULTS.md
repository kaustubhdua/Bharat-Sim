# BharatSim — network condition support and verification

This document distinguishes the **full engine worker** from the **legacy smoke worker**. A persona target or successful control command is not proof that arbitrary app traffic experienced that condition.

## 1. Worker modes

The worker defaults to legacy smoke mode. Set `BHARATSIM_WORKER_ENGINE=engine` to select `worker/engine.py`.

| Condition | Legacy smoke mode (default) | Full engine mode | Required evidence |
|---|---|---|---|
| Latency | Android emulator console control/readback | Host proxy delay for proxy-routed traffic | Control readback or proxy event/measurement |
| Download bandwidth | Emulator control/readback | Host proxy token-bucket shaping | Readback plus traffic bytes/timing |
| Upload bandwidth | Control-plane readback only | Host proxy uplink shaping | Measured upload traffic path |
| Packet-loss stalls | Unsupported by emulator console | Proxy can inject retransmission-like stalls | Proxy loss-stall counter and app-path evidence |
| Connection resets | Unsupported by legacy runner | Proxy can reset selected connections | Proxy reset counter and app-path evidence |
| Network outage/recovery | Not a general legacy feature | Engine toggles airplane mode and records process/recovery observations | Device state, PID/focus and recovery timing |
| Battery saver | Supported on disposable emulator with readback/cleanup | Supported where device command succeeds | Applied state and cleanup evidence |
| Storage pressure | Bounded temporary allocation with reserve and cleanup | Bounded device pressure where configured | Free-space readback and cleanup |
| RAM | Report-only / emulator provisioning dependent | Emulator provisioning dependent | Actual guest/device memory readback |
| CPU throttling | Unsupported | Unsupported | Never claim applied |
| Arbitrary APK traffic | Not proven | Only proxy-using traffic is shaped | Per-run proxy connection/byte counters |

### Proxy limitations

The engine configures Android's global HTTP proxy to a host-side shaper. It does not transparently intercept all sockets. Applications that ignore the system proxy, use direct sockets or use another network stack may bypass the shaper. A report with zero proxy connections must not claim the app experienced proxy shaping.

The proxy rejects private, loopback, link-local, multicast, reserved and unspecified destination addresses by default. This is a useful egress control for proxied traffic, not a substitute for host firewall policy or per-job VM isolation.

## 2. CI fixture data-plane experiment

The CI Appium fixture uses a source-built Android app that explicitly binds an HTTPS CONNECT socket to the active Android Network and requests a bounded range from a known repository asset. The host proxy:
- allowlists only the fixture's HTTPS destination;
- preserves end-to-end TLS (no TLS interception);
- pins the upstream IP resolved by CI;
- records bytes and timings without logging request bodies or TLS plaintext;
- applies a 384 kbps per-direction bandwidth cap or a 150 ms initial round-trip setup delay;
- verifies proxy readback and reset.

Historical evidence from CI run 41480040855 recorded nine 64,000-byte responses across baseline, latency-only and bandwidth-only conditions. Median transfer times were 206 ms baseline, 302 ms latency-only and 1,492 ms bandwidth-only. The injected latency measurement was 150.41–151.47 ms. The bandwidth delta is an observed diagnostic result, not a deterministic pass threshold.

This experiment proves the **source-built fixture's** traffic path only. It does not prove arbitrary customer APK traffic, physical-device fidelity or production worker isolation. The general smoke report intentionally does not set `constraints_applied=true` merely because emulator controls were read back.

## 3. Release validation still required

- Repeat engine-mode tests on more than one disposable emulator image.
- Verify packet-loss stalls, connection resets, outage and recovery with repeated app-level requests and negative controls.
- Record per-run proxy counters and correlate them with the APK's expected network journey.
- Test apps that bypass system proxy and confirm the report says traffic path unverified.
- Measure upload traffic separately; the existing fixture experiment validates bounded HTTPS downloads.
- Verify cleanup/reset after timeout, worker crash and interrupted execution.
- Test default-deny host firewall and per-job isolation independently.

Do not quote profile targets as measured conditions. Do not claim packet loss, outage or reset was applied unless the selected worker mode and the run's evidence confirm it.
