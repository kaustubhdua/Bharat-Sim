# Firecracker host preflight

BharatSim's production APK worker must run on a dedicated Linux x86_64 host with hardware virtualization. This preflight is deliberately **read-only**: it does not install binaries, alter kernel settings, create TAP devices, start guests, or change firewall rules.

## Run

```bash
sudo python3 scripts/firecracker_host_preflight.py
python3 scripts/firecracker_host_preflight.py --json
```

The preflight checks:
- x86_64 host architecture and an accessible `/dev/kvm` character device;
- unified cgroup v2 with CPU, memory, PID and I/O controllers;
- swap disabled;
- executable Firecracker and jailer binaries reporting the same release version;
- root-owned, non-group/world-writable jailer binary directory;
- privileged operator context for host inspection.

A passing preflight is necessary but **not sufficient** for production acceptance. It does not prove that Firecracker was launched through jailer with default seccomp, that each tenant receives a unique UID/GID and cgroup, that egress is default-deny, or that cleanup works after crashes. Those require runtime evidence and independent review. Never set BharatSim's three production worker flags based on this script alone.

## Upstream security references

- [Firecracker production host setup](https://github.com/firecracker-microvm/firecracker/blob/main/docs/prod-host-setup.md)
- [Firecracker jailer requirements](https://github.com/firecracker-microvm/firecracker/blob/main/docs/jailer.md)
- [Google Android Emulator container requirements](https://github.com/google/android-emulator-container-scripts/blob/master/REGISTRY.MD)
- [Android Emulator hardware acceleration](https://developer.android.com/studio/run/emulator-acceleration)

The Android Emulator container requires Linux with KVM; a normal shared Vercel function or unprivileged container is not a suitable substitute for the dedicated worker host.
