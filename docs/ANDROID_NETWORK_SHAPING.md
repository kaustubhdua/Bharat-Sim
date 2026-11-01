# Android Emulator network shaping: fixture proxy evidence

BharatSim does not treat a requested profile or a successful control command as proof that application traffic was shaped. The CI fixture experiment routes its HTTPS request through a local, allowlisted HTTP CONNECT proxy running on the GitHub Actions host. The proxy does not terminate TLS or inspect payloads. It pins the upstream IP, records tunnel byte counts and timings, and applies deterministic delay/rate limits.

## Why CI uses a proxy

Android Emulator's documented console network-speed and network-delay controls apply to Ethernet and Cellular. Wi-Fi is not accepted as emulator-console shaping evidence. The CI emulator image repeatedly exposed no active Cellular or Ethernet network after Wi-Fi was disabled, so the Appium data-plane experiment failed before measuring traffic. The workflow now keeps the emulator's real network active and routes the source-built fixture's HTTPS socket through an explicit CONNECT proxy bound to the active Android Network.

References:
- [Android Emulator command-line options](https://developer.android.com/studio/run/emulator-commandline) — network-speed and network-delay controls for Ethernet and Cellular.
- [Android Emulator console commands](https://developer.android.com/studio/run/emulator-console) — network status and shaping controls.
- [Advanced Emulator networking](https://developer.android.com/studio/run/emulator-networking-advanced) — modern Wi-Fi/netsim behavior.
- [Interconnecting Emulator instances](https://developer.android.com/studio/run/emulator-networking-interconnect) — compatibility networking model options.

## Proxy design

- The host proxy listens on TCP 8888; its control API listens on host loopback TCP 8889.
- Only raw.githubusercontent.com:443 is allowlisted. The proxy connects to the CI-resolved IPv4 address, while the Android app retains the HTTPS hostname for SNI and normal certificate hostname verification.
- The Android fixture creates an HTTP CONNECT socket and binds it to the active Android Network. TLS terminates in the fixture app, not in the proxy.
- The proxy applies a 384 kbps per-direction rate cap for the bandwidth-only profile.
- The latency-only profile inserts 75 ms before the first forwarded bytes in each direction (a measured initial 150 ms round-trip setup delay). It is a bounded fixture experiment, not a full packet-level mobile-network emulator.
- Every sample must create a completed proxy event with the expected hostname, upstream IP, configuration generation and at least 64,000 response bytes.
- The Appium journey measures repeated baseline, bandwidth-only and latency-only samples on the same Android transport, then resets the proxy to baseline and verifies the control readback.
- The proxy records only connection metadata, bytes and durations. It does not log URLs, headers, request bodies or TLS plaintext.

## Current fixture experiment

- Fixture asset: 256,000 bytes hosted in this repository; each sample requests a bounded 64,000-byte HTTPS range.
- Transport: the latest CI evidence uses Wi-Fi; the fixture explicitly binds its proxy socket to the active Android Network. Cellular/Ethernet proxy-path measurements are not claimed by this run.
- Bandwidth profile: 384 kbps in both tunnel directions.
- Latency profile: 150 ms initial round-trip setup delay (75 ms each direction).
- Per-attempt timeout: 20 seconds; overall Android probe deadline: 45 seconds; Appium wait: 60 seconds.
- Data-plane evidence: Android probe logcat, proxy event ID/generation, exact upstream IP, response byte count, per-sample duration and reset readback.

Verified in GitHub Actions run 41328703086 (PR head ea8ecf800641e688d39b9cf1dbd043b983cdba1f): the source-built fixture completed repeated baseline, latency-only and bandwidth-only HTTPS range requests on the active Wi-Fi network. Every measured response transferred 64,000 bytes through the pinned upstream IP. The 384 kbps bandwidth profile increased median end-to-end transfer time by 757 ms. The 150 ms latency profile recorded 150.47–150.59 ms of actual injected delay across both relay directions; end-to-end RTT medians remain diagnostic because the public upstream varies. The proxy profile readback and reset-to-baseline verification both passed. This is fixture-only evidence: it does not prove arbitrary uploaded APK traffic, production isolation, or physical-device fidelity.

## Claim boundaries

A successful proxy experiment proves only that the source-built fixture APK routed its HTTPS probe through the allowlisted, shaped CONNECT proxy. It does not prove arbitrary customer APK traffic follows the system proxy or uses the same route. The worker's general report keeps traffic_path_verified=false unless a separate repeatable experiment establishes the uploaded app's traffic path. Proxy control readback alone is not enough.
