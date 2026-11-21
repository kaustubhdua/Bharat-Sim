> Historical audit snapshot (21 Nov 2026). This file records evidence from a prior deployment and is not the current release decision. Its VERIFIED WORKING labels do not establish current production readiness. Use [docs/FINAL_PRODUCT_AUDIT.md](FINAL_PRODUCT_AUDIT.md), [docs/MASTER_FEATURE_INVENTORY.md](MASTER_FEATURE_INVENTORY.md) and [docs/PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for current status.

# BharatSim finale audit (21 Nov 2026)

Audited commit `9699864` on `kaustubhdua/Bharat-Sim` main, live at https://bharatsim.onrender.com.
The one-page build plan (verified commit `f725583`) was treated as a baseline, not proof. Every row below was
re-checked against source, tests or the live deployment.

## Status matrix (before the finale slice)

| Feature | Status | Evidence / reason |
|---|---|---|
| Dashboard, personas, landing | VERIFIED WORKING | Live; 5 personas from `/api/v1/personas` |
| Risk planner (Interaction Hunter) | VERIFIED WORKING | `POST /api/v1/plan` returns 200 live |
| Failure DNA log analysis + BharatScore | VERIFIED WORKING | `POST /api/v1/analyze/logs`; Evaluator Tour crash fixed in `9699864` |
| PostgreSQL readiness | VERIFIED WORKING | `/health/ready` → `database: available` |
| Authentication (Supabase JWT, JWKS) | VERIFIED WORKING | Anonymous `GET /api/v1/runs` → 401 live |
| Tenant isolation | PARTIALLY VERIFIED | Every run query is `owner_id`-scoped in code and covered by tests; not penetration-tested |
| APK upload (signed PUT to private bucket) | VERIFIED WORKING | Real uploads of Rooftop.apk completed today |
| Worker execution (real emulator) | WORKER-GATED | Laptop worker + AVD `bharat_low`; runs `3b1ee9a4` (score 90) and `cb497274` (89) completed. Stops when the laptop or emulator is off (the emulator was found stopped during this audit) |
| Network shaping | PARTIALLY WORKING | Host shaping proxy applies latency, bandwidth, loss stalls, resets and outages. It only shapes traffic that uses the Android system proxy; for Rooftop the report shows no app traffic went through it |
| RAM limits | PARTIALLY WORKING | Below 2 GB (in-guest balloon) or 3–4 GB (AVD restart); 2 GB personas run as is |
| CPU throttling | UNSUPPORTED | No per-app throttle on the emulator; stated in UI and reports |
| Run report, PDF, JSON export | VERIFIED WORKING | Engine report view shipped in `9699864` |
| Run comparison | VERIFIED IN TESTS | Engine reports compared by persona leg; not re-checked live while signed in |
| Sarvam translation | VERIFIED WORKING | `sarvam-translate:v1`, Hindi/Tamil/Marathi; probed today |
| Sarvam voice (Bulbul TTS) | FAILING | Code calls `bulbul:v1` with speaker `meera`; Sarvam now rejects that (400). Live endpoint returns "Sarvam TTS service unavailable" |
| Sarvam TTS endpoint auth | SECURITY GAP | `/api/v1/translate/audio` is reachable without sign-in (credit abuse) |
| "Sarvam explanation" on findings | NOT SARVAM | `explain_failure_with_sarvam` returns fixed English templates; only the optional Hindi path calls Sarvam Translate |
| Speech-to-text, chat/LLM | NOT IMPLEMENTED | Probed today: `saaras:v4` and `sarvam-105b` (JSON-schema output) both work with the server key |
| Microphone in browser | BLOCKED | `Permissions-Policy: microphone=()` |
| Render auto-deploy | FAILING | Pushes to `kaustubhdua/Bharat-Sim` do not trigger deploys; manual deploy needed |

## Sarvam API facts verified today
- Chat: `POST https://api.sarvam.ai/v1/chat/completions`, model `sarvam-105b`, `response_format: json_schema` — 200, schema-valid JSON, ~0.4 s.
- Speech-to-text: `POST /speech-to-text`, model `saaras:v4`, `language_code=unknown` — 200, Hindi transcript, ~0.5 s.
- Text-to-speech: `POST /text-to-speech`, model `bulbul:v3`, speaker `priya`, field `language_code` — 200.
- Translate: `sarvam-translate:v1` en→ta — 200.

## After the finale slice (commits `70ab199`, `bac77fe`, merge `fc76f7b`)

| Feature | Before | After | Evidence |
|---|---|---|---|
| Speak-to-Test (voice + text → validated test spec) | NOT IMPLEMENTED | VERIFIED WORKING (live) | Live plan on bharatsim.onrender.com via `sarvam-105b`; `docs/evidence/sarvam_live_check.json` (Hindi, Hinglish, Tamil, ambiguous, unsupported) |
| Voice input (Saaras) | NOT IMPLEMENTED | VERIFIED via API | Bulbul → Saaras round trip, Hindi and Tamil, verbatim transcripts; browser mic not exercised by the agent |
| Bulbul voice briefing | FAILING | FIXED (`bulbul:v3`) | Live TTS request ids in the evidence file |
| Unsupported-condition reporting | n/a | VERIFIED | incoming call + CPU throttle listed as not applied |
| Janjeevan pack A (payment pending + retry) | n/a | VERIFIED on emulator | Original: 2 charges, "Payment failed" shown; fixed: 1 charge, "pending" shown (standalone spike) |
| FixProof | n/a | VERIFIED in tests | 7 verdicts unit-tested; never verifies an unexecuted or incomparable fix |
| Citizen Impact Translator | n/a | BUILT | Evidence-cited explanation per audience, translated and spoken |
| Sarvam endpoints auth + rate limit | GAP | FIXED | Anonymous → 401 live; 40 calls / 10 min / user |
| Microphone permission | BLOCKED | FIXED | `microphone=(self)` live |
| Other Janjeevan packs (B–F) | n/a | NOT BUILT | Listed as planned, with the missing piece |

### Live end-to-end evidence (21 Nov 2026, 23:10 IST, bharatsim.onrender.com, signed-in user)
- Plan created in Speak-to-Test from the Hinglish request (Sarvam `sarvam-105b`), matched `upi-pending-retry`.
- Run `da29da4a` (bharatpay-original.apk, SHA-256 `93d8a5db8c1c…`), completed on the emulator:
  - Scenario verdict **fail**: 2 charges for one order.
  - Screen after timeout: "Payment failed. Please retry."
  - Readiness 89.
- Run `e0174831` (bharatpay-fixed.apk, `e400222ba5eb…`), completed:
  - Scenario verdict **pass**: 1 charge.
  - Screen: "Payment pending: waiting for bank confirmation. Do not pay again."
  - Readiness 90.
- FixProof (`da29da4a` → `e0174831`): **FIXED AND VERIFIED**. All 6 preconditions passed.
- FixProof against crashed run `2d4f7e56`: **VERIFICATION BLOCKED**.
- Citizen Impact explanation of `da29da4a` (public audience, Hindi): HTTP 200, 9 evidence ids cited, Sarvam request `20261121_283d6608-39c5-440f-a5c9-09b2d3d0048c`.
- Earlier runs `625c18b3`, `336d9e23`, `f92c6d7e`, `2d4f7e56` failed and are kept as failed:
  - The first two because the worker was pointed at a stale local API.
  - The last two because the emulator crashed.

Tests on merged code: backend 206 passed (2 skipped), worker 111 passed, frontend 55 passed, production build OK.

## Priorities chosen
1. Speak-to-Test (voice/text → validated test spec) on Sarvam, in the core flow.
2. One controlled scenario pack (UPI-style payment pending + retry) with machine-checked assertions on a mock fixture.
3. FixProof: deterministic verdict from two real runs of the same scenario.
4. Fix Bulbul TTS, lock Sarvam endpoints behind sign-in, allow microphone for this origin.
