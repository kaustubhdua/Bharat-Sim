# BharatSim — Network Simulation Results

**Candidate:** `75d78e108ab9b2778131847a0d25f45ac7ccd2e6`  
**Date:** 2026-11-21

## Supported scope and evidence

Repository CI includes a controlled emulator fixture/proxy exercise with selected latency/bandwidth controls, readback and reset. This verifies a bounded fixture path, not arbitrary uploaded APK traffic in production or physical low-cost devices.

Production currently reports network shaping unavailable for customer runs. Packet loss and outage/recovery are not supported. CPU pressure is unsupported; RAM is report-only. Persona settings describe requested conditions and do not prove they were applied.

## Required verification before advertising broader support

- Prove app requests traverse the configured network path using a known test APK.
- Capture requested, applied, read-back and traffic-path evidence as separate fields.
- Run cleanup/reset tests after success, failed run, cancellation and worker termination.
- Test supported Android transports separately and prove there is no cross-job profile leakage.
- Add jitter/packet loss/outage only after the controls are implemented and measured.
- Validate performance impact using repeated samples, sample count, medians/spread and baseline pairing.

Keep production network shaping disabled for public APK testing until isolated worker and egress controls are independently signed off.
