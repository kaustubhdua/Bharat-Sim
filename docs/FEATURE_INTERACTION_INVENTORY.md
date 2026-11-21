# BharatSim — feature interaction inventory

**Baseline:** main `529d308532f042a3ba4092171370cd4c29a068cb`  
**Audit date:** 2026-11-21

This inventory records the interactive surface discovered in the current React application. It is not a claim that production credentials or infrastructure are configured.

| Surface | Control/action | Intended result | Backend/provider | Current state |
|---|---|---|---|---|
| Global shell | Brand | Navigate to overview | React Router | Implemented |
| Global shell | Overview / Test runs / Log analysis | Navigate between existing routes | React Router | Implemented |
| Global shell | API refresh | Reload personas, capabilities, runs and workers | FastAPI | Implemented |
| Auth gate | Email/password sign-in | Establish Supabase session | Supabase Auth | Code implemented; live provider unverified |
| Auth gate | Create account | Create user or prompt email confirmation | Supabase Auth | Code implemented; live provider unverified |
| Auth gate | Public preview | Enter UI-only guest preview | Session storage | Implemented; private APIs intentionally locked |
| Auth gate | Sign out | Revoke session best-effort and clear local session | Supabase Auth | Implemented |
| Overview | Persona card selection | Select persona for planner/run | Personas API | Implemented |
| Overview | APK selection and submit | Validate, upload and register run | FastAPI + private Storage | Capability-gated; production blocked by missing persistence/storage credentials in latest release evidence |
| Overview | Risk planner | Generate risk-first plan | Planner API | Implemented; planning is not execution |
| Overview | Logcat textarea and analyze | Analyze submitted logs and return findings | Analysis API | Implemented; private analysis requires auth |
| Overview | Recent run link / View all | Open run detail/history | FastAPI + router | Implemented |
| Overview | Evaluator quick tour | Load curated logcat fixture into analyzer | Evaluator scenarios API | Mounted in merged PR #131; API envelope corrected; clearly labelled fixture, not an executed APK run |
| Runs | Search | Filter loaded run records | Client-side | Implemented |
| Runs | Status filter | Filter active/completed/failed records | Client-side | Implemented |
| Runs | Open run | Navigate to run evidence | FastAPI | Implemented |
| Run detail | Refresh/poll | Refresh active run and lifecycle events | FastAPI | Implemented |
| Run detail | Download report | Download worker report JSON | FastAPI | Implemented |
| Run detail | Delete | Confirm and delete eligible owner-scoped run | FastAPI | Implemented; active execution guarded |
| Run detail | Compare runs | Compare completed baseline and constrained runs | FastAPI + persisted telemetry | Corrected in merged PR #131 to use owner-scoped `result_json` and measured metrics only; current database unavailability keeps the operation disabled by this branch's capability gate |
| Analysis | Export JSON | Download current analysis report | Browser Blob | Implemented |
| Analysis | Finding expansion | Inspect evidence and recommendations | React state/component | Implemented |
| Analysis | Sarvam language selector | Choose Hindi/Tamil/Marathi | Local state | Implemented |
| Analysis | Translate report | Translate condensed report summary | FastAPI + Sarvam | Conditional on server API key; deterministic fallback exists for selected summaries |
| Analysis | Play voice briefing | Generate and play translated speech | FastAPI Bulbul TTS | API/player contract fixed in merged PR #131; this branch also gates the button on `sarvam_audio_tts`; real speech requires `SARVAM_API_KEY` and silent fixture is never played as speech |
| Theme | Light/dark toggle | Persist theme and apply before paint | Local storage + root theme attribute | Implemented in merged PR #131; persistent selection and pre-paint bootstrap are deployed |
| Missing | PDF export | Generate downloadable PDF | Not implemented | Missing |
| Missing | Password reset/email resend | Recover/verify account | No complete flow found | Missing |
| Missing | Settings/profile/security/notifications | Save account preferences | No settings route/API found | Missing |
| Missing | Server pagination/date/persona filters | Query history at scale | No complete API/UI flow found | Missing |
| Missing | Dedicated apps/APK library | Browse, inspect and manage uploaded APKs | No separate resource screen found | Missing |
| Missing | Dedicated findings/reports resources | Browse and filter persisted findings/reports | No separate resource screen found | Missing |

## Evidence rules

- Do not mark an action complete because a button exists; verify the API call and resulting persisted state.
- Keep unsupported actions absent or clearly disabled with an explanation.
- Do not show fabricated metrics, synthetic runs or invented worker activity.
- Keep guest preview read-only for private resources.
- Treat CI fixture execution separately from customer APK execution.
- Test every supported flow at mobile and desktop widths, with keyboard-only navigation and reduced motion.

## Branch remediation notes

The current branch additionally corrects the comparison query to use `result_json`, scopes both run lookups to the authenticated owner, refuses fabricated telemetry defaults, requires completed runs and shared measured metrics, and aligns the comparison response shape with the UI. It fixes the Sarvam audio response contract and refuses silent fixture audio as a voice briefing. The evaluator tour reads the API's `items` envelope and is mounted on Overview by merged PR #131; scenario logs and metrics are explicitly marked as fixtures.
