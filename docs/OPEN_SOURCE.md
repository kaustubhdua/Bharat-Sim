# Open-source components and reuse policy

BharatSim is designed to compose existing tools rather than reimplement Android infrastructure. These references were checked during the October 2026 research pass; verify current versions, compatibility and licenses before adopting or pinning dependencies.

| Tool / project | Proposed role | Upstream documentation |
|---|---|---|
| Android Emulator and ADB | Disposable Android device, install/launch, device logs | https://developer.android.com/studio/run/emulator-commandline |
| Android UI Automator | UI testing that interacts with user and system apps | https://developer.android.com/training/testing/other-components/ui-automator |
| Appium UiAutomator2 | Optional black-box app journey automation | https://appium.github.io/appium-uiautomator2-driver/latest/getting-started/ |
| Linux `tc/netem` | Network delay, jitter, loss, rate, reorder and corruption emulation | https://www.man7.org/linux/man-pages/man8/netem.8.html |
| OWASP File Upload Cheat Sheet | Upload threat model and layered validation guidance | https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html |
| FastAPI / Pydantic / Uvicorn | API and schema validation | https://fastapi.tiangolo.com/ |
| React / Vite / Lucide | Frontend UI and icons | https://react.dev/ · https://vite.dev/ · https://lucide.dev/ |

## Practical integration guidance

- Android Emulator/ADB should run in a disposable worker, not inside the public API process. BharatSim's separate emulator workflow uses the open-source ReactiveCircus Android Emulator Runner and a source-built fixture app; it is CI validation, not a public untrusted-APK service.
- UI Automator/Appium should execute declared test flows and preserve step-level evidence; do not claim app journeys were tested when only an app launch was attempted.
- Linux netem can shape a selected Linux egress interface, but emulator traffic must actually traverse that interface. Measure a known endpoint and preserve requested versus observed conditions separately.
- Upload validation should be layered. Extension checks and archive metadata checks do not establish that an APK is safe to execute; isolation, quotas, restricted egress and cleanup remain essential.
- Sarvam AI is a potential hosted regional-language summary provider, not an open-source dependency. It is not wired into this draft. Keep credentials server-side and require consent before sending sensitive logs to a hosted service.

## License and provenance hygiene

No third-party source code is copied into the repository by this document. Before adding any external implementation, record its upstream URL, exact version/commit, license, modifications, and attribution obligations. Re-check transitive dependency licenses before release. Android SDK terms, Appium package dependencies and any external service terms must be reviewed independently.
