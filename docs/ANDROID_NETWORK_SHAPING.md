# Android Emulator network shaping: verified path only

BharatSim does not treat a requested emulator profile or a successful console command as proof that application traffic was shaped. A network experiment is valid only when the Android device reports an active supported transport, the emulator console reports the requested control values, the fixture request traverses the Android Network selected for the probe, measured latency/bandwidth changes, and the emulator is reset and read back afterward.

## Emulator transport choice

The Android Emulator command-line documentation states that network-speed and network-delay emulation applies to **Ethernet and Cellular**. The emulator console's network-status, network-speed, and network-delay commands are likewise documented for Ethernet and Cellular. Wi-Fi is not accepted as a shaped transport by this test.

Android Emulator 36.5 and later route Wi-Fi traffic through the newer netsim networking stack. The emulator networking documentation describes the -feature -WiFiPacketStream flag as the compatibility switch to return to the previous networking model. The CI workflow uses that flag, disables Wi-Fi after boot, and requires an active Cellular or Ethernet network before starting the data-plane measurement.

References:
- [Android Emulator command-line options](https://developer.android.com/studio/run/emulator-commandline) — network-speed and network-delay emulation applies to Ethernet and Cellular.
- [Android Emulator console commands](https://developer.android.com/studio/run/emulator-console) — network status and shaping controls.
- [Interconnecting Emulator instances](https://developer.android.com/studio/run/emulator-networking-interconnect) — legacy network model compatibility flag -feature -WiFiPacketStream.
- [Advanced Emulator networking](https://developer.android.com/studio/run/emulator-networking-advanced) — modern netsim networking and Wi-Fi behavior.

## Current fixture experiment

- Fixture asset: 256,000 bytes hosted on raw.githubusercontent.com; each sample requests a bounded 64,000-byte range.
- Transport: Cellular or Ethernet only; the CI journey fails closed if neither is active.
- Profiles: baseline, UMTS bandwidth (384 kbps), and 150 ms latency.
- Per-attempt timeout: 20 seconds; overall Android probe deadline: 45 seconds; Appium wait: 60 seconds.
- Data-plane evidence: multiple real HTTPS requests, exact byte counts, per-sample durations, Android Network transport, and console readback.
- Reset: restore full speed/no delay and verify console readback.

The previous run completed the local API → queue → worker → ADB → callback → report path and passed APK install/launch/logcat. Its Appium network journey failed before measurements because the Android image exposed no active Cellular or Ethernet network after Wi-Fi was disabled. The workflow now switches to the legacy Ethernet/Cellular networking model before disabling Wi-Fi. This change is under CI revalidation; no current data-plane pass is claimed until repeated measurements and reset checks succeed.

## Claim boundaries

A successful fixture experiment proves only that the source-built fixture APK traversed the measured emulator transport. It does not prove that arbitrary customer APK traffic follows the same path. The worker report keeps traffic_path_verified=false unless a separate, repeatable data-plane experiment has established the path. Control-plane readback alone is not enough.
