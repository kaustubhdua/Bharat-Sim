# BharatSim — Performance Report

**Candidate:** `75d78e108ab9b2778131847a0d25f45ac7ccd2e6`  
**Date:** 2026-11-21

## Measurements

No controlled k6/load test or representative production browser performance profile was run during this audit. No p50/p95/p99 latency, throughput, concurrency, Core Web Vitals, memory or CPU value is claimed.

A passing build/container smoke is not a runtime performance measurement.

## Areas to measure

- Initial route load, navigation, dashboard render and large history/log views.
- APK upload throughput and resumability under staging network conditions.
- API auth, persona, job lifecycle, history, comparison and report retrieval latency.
- Queue wait, worker startup, install/launch and telemetry collection time.
- Browser bundle size, long tasks, layout shift, large chart/log rendering and memory use.

## Acceptance method

Use controlled staging, bounded k6 concurrency and measured thresholds aligned to target infrastructure. Publish scripts, raw results, environment, baseline and regression thresholds. Never load-test production without a specific approved plan.
