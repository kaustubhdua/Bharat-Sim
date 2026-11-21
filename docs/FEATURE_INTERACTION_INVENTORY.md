# BharatSim — Feature Interaction Inventory

**Audited main:** `2c754dcb428fdbacc67da18d41fad3c1d0745c83`  
**Working branch:** `fix/accurate-capabilities-and-product-evidence`  
**Rule:** A control is complete only when its behaviour, backend dependency, success state and failure state are real and testable. Fixture data is not execution evidence.

| Route / surface | Control | Behaviour / dependency | Current state |
|---|---|---|---|
| Public landing `/landing` | Product tour link from sign-in | Public route through AuthGate | Implemented on this branch |
| Public landing | Start Testing | Navigates to `/new-test`; AuthGate requires sign-in | Implemented; upload remains capability-gated |
| Public landing | Explore Planner | Enters explicit UI-only guest preview and navigates to overview | Implemented on this branch |
| Overview `/` | Persona cards | Selects API profile for planner/configuration | Implemented; built-in profiles are labelled when API is offline |
| Overview | APK upload entry | Opens test wizard | Implemented; disabled if private storage/database capability is false |
| Overview | Readiness score | Displays latest analysis score | No score is shown before a real report exists |
| Overview | Run counts / worker status | Uses API runs and worker heartbeat data | API-backed; offline/empty states shown |
| Test wizard `/new-test` | APK file picker / drag-drop | Validates file, extracts metadata/checksum, prepares upload | Implemented; production upload disabled while storage/database are unavailable |
| Test wizard | Worker interaction count / telemetry switches | Current run-registration API does not accept per-run overrides | Read-only defaults with explanatory copy; not represented as configurable |
| Test wizard | Start test | Registers run and uploads APK | Capability-gated; no production execution until storage and isolated worker exist |
| Comparison `/compare` | Baseline / constrained selectors | Selects two completed runs | This branch filters both selectors to completed runs |
| Comparison | Compare measured telemetry | Calls owner-scoped comparison API | Disabled when database capability is false; missing metrics are not imputed |
| Settings `/settings` | Theme toggle | Shared ThemeProvider + localStorage | Implemented on this branch; topbar and settings share one state |
| Settings | Language preference | Local browser preference | Implemented locally; server/account sync not implemented |
| Settings | Account / RLS / quota / storage / worker / TTS status | Displays session and API capability data | Dynamic where API exposes data; production RLS and quota remain unverified/not exposed |
| History `/runs` | Search/status filters | Filters loaded run list | Client-side filtering; server pagination/date/persona filters remain missing |
| Run detail `/runs/:id` | Refresh / event polling | Reads run status and events | Implemented for existing run records |
| Run detail | Download report JSON | Downloads persisted run report | Implemented where report exists |
| Run detail | Delete | Confirms and deletes owner-scoped run | Implemented; active execution guarded |
| Analysis `/analysis` | Logcat input / Analyze evidence | Calls stateless FastAPI log-analysis endpoint | Implemented; Playwright journey still has a failing result-screen assertion and is being instrumented |
| Analysis | Finding expansion / JSON export | Shows evidence and downloads analysis JSON | Implemented |
| Analysis | Translation | Calls Sarvam translation or configured fallback | Real provider requires server-side `SARVAM_API_KEY` |
| Analysis / finding cards | Voice briefing | Checks `sarvam_audio_tts` capability before calling Bulbul endpoint | Disabled when provider is not configured; fixture WAV is never played as speech |
| Evaluator tour | Load scenario | Loads curated fixture logcat into analyzer | Fixture-only; never represented as an executed APK |
| Navigation | Sidebar / topbar / responsive drawer | Navigates routes and toggles shared theme | Implemented; full accessibility audit outstanding |

## Known missing or blocked interactions

| Feature | Why it is not complete |
|---|---|
| PDF export | No production PDF generation/download path |
| Password reset / verification resend UX | No complete dedicated recovery flow |
| Dedicated findings resource page | Findings currently appear within analysis/run evidence |
| Dedicated reports resource page | No complete persisted report library |
| Server-side history pagination/date/persona filters | Current history filtering is client-side |
| Per-run worker overrides | Run-registration API does not accept interaction-count or telemetry toggles |
| Persistent account settings | Theme/language are local; profile/security/notification preferences are not persisted server-side |
| Production APK execution | Production database/storage/worker capabilities are false; arbitrary execution remains disabled |
| Live Sarvam translation/TTS | Requires server-side provider credentials |
| Independent ML validation | No held-out dataset or model registry/version governance |
| Full accessibility conformance | No independent WCAG audit or screen-reader E2E suite |

## Evidence and safety rules

- Never render a default readiness score, fabricated jank/PSS/network values, fake customer activity or synthetic worker heartbeat.
- Persona values are requested configuration, not proof of applied device constraints.
- Evaluator scenarios and landing previews are illustrative fixtures.
- Comparison uses only completed owner-scoped runs and telemetry measured in both reports.
- A 200 response from the SPA is not proof that the API, database, storage or worker is healthy.
- Keep public APK execution disabled until worker isolation, tenant isolation, storage boundaries and default-deny egress are verified.
