# Evidence synthesis and diagnostic confidence

BharatSim derives an evidence-synthesis object from each stored Android worker report when a run is opened or exported. The synthesis is computed from the original report and is not written back into the worker's stored evidence.

## Evidence inputs

- **Logcat:** bounded crash, ANR, OOM, network and storage markers with line-addressable excerpts.
- **Condition manager:** requested conditions, apply status, verification status, readback and cleanup status.
- **Network control plane:** Android Emulator latency/bandwidth configuration and console readback.
- **Network data plane:** explicit traffic-path verification. A verified control-plane readback alone does not establish that arbitrary app traffic traversed the shaped path.
- **Execution steps:** ADB step return codes and durations, including install, launch and logcat collection.

## Status meanings

| Status | Meaning |
| --- | --- |
| `CORRELATED` | At least one symptom has independent condition and traffic evidence. The root-cause hypothesis remains unconfirmed. |
| `OBSERVED_ONLY` | A symptom marker exists, but independent evidence is insufficient to attribute it to a requested constraint. |
| `NO_MARKER_OBSERVED` | No known marker was found in the bounded logcat capture. This is not an application health pass. |
| `INCOMPLETE` | The report or successful logcat capture is missing. |

Hypothesis confidence is deliberately limited to **low** or **medium**. The system never reports a confirmed root cause. A human must inspect the full logs, repeat the flow and validate a remediation.

## Known limits

- RAM restriction is report-only. An OOM marker is not attributed to a simulated low-RAM cap.
- The worker's single-run network probe does not verify arbitrary application traffic. The separate repeated baseline-versus-shaped fixture experiment is required for a data-plane claim.
- Missing markers in bounded logcat do not prove the application is healthy.
- The planner and synthesis are deterministic heuristics, not an LLM-generated diagnosis.
- The exported report preserves the original worker-report SHA-256 separately from the derived diagnostics SHA-256.

## Relationship to jai-hack

The fail-closed evidence-fusion and explicit-review approach was informed by the MIT-licensed [jai-hack](https://github.com/kaustubhdua/jai-hack) repository, particularly its CyberSentinel fusion/correlation-agent design. BharatSim implements its own Android-specific synthesis over logcat, emulator conditions and ADB execution evidence. Cybersecurity network classifiers, traffic-blocking policies and unrelated model code are not imported.
