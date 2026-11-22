#!/usr/bin/env bash
# ==============================================================================
# BharatSim — Production Android Worker Host Bootstrap Script
# Target: Ubuntu 22.04 LTS / 24.04 LTS with Hardware Virtualization (KVM)
# Run as root or with sudo.
# ==============================================================================
set -euo pipefail

echo "===================================================================="
echo " BharatSim Android Worker Host Automated Setup"
echo "===================================================================="

# 1. Verify Hardware Virtualization (KVM)
echo "[1/8] Verifying hardware virtualization..."
if ! command -v kvm-ok >/dev/null 2>&1; then
    apt-get update -y && apt-get install -y cpu-checker
fi

if kvm-ok 2>&1 | grep -q "KVM acceleration can be used"; then
    echo "  [OK] Hardware acceleration (KVM) is available and enabled."
else
    echo "  [WARNING] kvm-ok indicates KVM is not active or hardware virtualization is disabled."
    echo "  Ensure your cloud instance supports nested virtualization (e.g. GCP n2-standard with nested virt enabled, AWS bare-metal .metal instance, or Hetzner)."
fi

# 2. Install System Dependencies
echo "[2/8] Installing host packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
    curl \
    wget \
    unzip \
    git \
    python3 \
    python3-pip \
    python3-venv \
    openjdk-17-jdk-headless \
    qemu-kvm \
    libvirt-daemon-system \
    libvirt-clients \
    bridge-utils \
    iproute2 \
    iptables \
    net-tools \
    socat \
    libpulse0 \
    libgl1 \
    libgl1-mesa-glx \
    libnss3 \
    libxcomposite1 \
    libxcursor1 \
    libxi6 \
    libxtst6

# 3. Create BharatSim dedicated system service user
echo "[3/8] Configuring service user and group permissions..."
if ! id -u bharatsim >/dev/null 2>&1; then
    useradd -r -m -d /var/lib/bharatsim -s /bin/bash bharatsim
fi

# Grant user access to KVM and Libvirt
usermod -aG kvm bharatsim || true
usermod -aG libvirt bharatsim || true

# Udev rule to guarantee /dev/kvm permissions on every reboot
cat << 'EOF' > /etc/udev/rules.d/99-bharatsim-kvm.rules
# KVM is available only to the dedicated worker group; never grant world access.
KERNEL=="kvm", GROUP="kvm", MODE="0660", OPTIONS+="static_node=kvm"
EOF
udevadm control --reload-rules || true
udevadm trigger --name-match=kvm || true
if [ -e /dev/kvm ]; then
    chgrp kvm /dev/kvm
    chmod 0660 /dev/kvm
fi

# 4. Install Android Command-Line Tools & SDK
echo "[4/8] Installing Android SDK and platform-tools..."
ANDROID_SDK_ROOT="/opt/android-sdk"
mkdir -p "$ANDROID_SDK_ROOT/cmdline-tools"

if [ ! -d "$ANDROID_SDK_ROOT/cmdline-tools/latest" ]; then
    CMDLINE_ZIP="/tmp/commandlinetools-linux.zip"
    wget -q -O "$CMDLINE_ZIP" "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
    unzip -q -o "$CMDLINE_ZIP" -d "/tmp/cmdline-tools"
    mv "/tmp/cmdline-tools/cmdline-tools" "$ANDROID_SDK_ROOT/cmdline-tools/latest"
    rm -rf "$CMDLINE_ZIP" "/tmp/cmdline-tools"
fi

export ANDROID_HOME="$ANDROID_SDK_ROOT"
export ANDROID_SDK_ROOT="$ANDROID_SDK_ROOT"
export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:$PATH"

# Accept all SDK licenses automatically
yes | sdkmanager --licenses >/dev/null 2>&1 || true

# Install platform-tools, emulator, and API 35 Google APIs x86_64 image
echo "  Installing platform-tools, emulator, and system-images;android-35;google_apis;x86_64..."
sdkmanager "platform-tools" "emulator" "platforms;android-35" "system-images;android-35;google_apis;x86_64" "build-tools;35.0.0"

# 5. Create Android Virtual Device (AVD)
echo "[5/8] Creating BharatSim AVD..."
mkdir -p /var/lib/bharatsim/avd
chown -R bharatsim:bharatsim /var/lib/bharatsim
chown -R bharatsim:bharatsim "$ANDROID_SDK_ROOT"

sudo -u bharatsim bash -c "
export ANDROID_HOME=$ANDROID_SDK_ROOT
export ANDROID_SDK_ROOT=$ANDROID_SDK_ROOT
export ANDROID_AVD_HOME=/var/lib/bharatsim/avd
echo no | $ANDROID_SDK_ROOT/cmdline-tools/latest/bin/avdmanager create avd \
    --name bharatsim-api35 \
    --package 'system-images;android-35;google_apis;x86_64' \
    --device 'pixel_2' \
    --force
"

# Configure AVD hardware settings (2 GB RAM, 720p budget tier characteristics)
AVD_CONFIG="/var/lib/bharatsim/avd/bharatsim-api35.avd/config.ini"
if [ -f "$AVD_CONFIG" ]; then
    sed -i 's/^hw.ramSize=.*/hw.ramSize=2048/' "$AVD_CONFIG" || echo "hw.ramSize=2048" >> "$AVD_CONFIG"
    echo "vm.heapSize=256" >> "$AVD_CONFIG"
    echo "disk.dataPartition.size=4096M" >> "$AVD_CONFIG"
fi

# 6. Deploy BharatSim Code & Python Environment
echo "[6/8] Configuring BharatSim worker directory and Python virtualenv..."
WORKER_DIR="/opt/bharatsim"
mkdir -p "$WORKER_DIR"
chown -R bharatsim:bharatsim "$WORKER_DIR"

if [ ! -d "$WORKER_DIR/.venv" ]; then
    sudo -u bharatsim python3 -m venv "$WORKER_DIR/.venv"
fi

# 7. Install Systemd Services
echo "[7/8] Installing and enabling systemd units..."

# Emulator Service
cat << 'EOF' > /etc/systemd/system/bharatsim-emulator.service
[Unit]
Description=BharatSim Headless Android Emulator
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=bharatsim
Group=bharatsim
SupplementaryGroups=kvm
WorkingDirectory=/var/lib/bharatsim
Environment=HOME=/var/lib/bharatsim
Environment=ANDROID_HOME=/opt/android-sdk
Environment=ANDROID_SDK_ROOT=/opt/android-sdk
Environment=ANDROID_AVD_HOME=/var/lib/bharatsim/avd
ExecStartPre=/usr/bin/test -r /dev/kvm
ExecStart=/opt/android-sdk/emulator/emulator @bharatsim-api35 -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect -memory 2048 -wipe-data -no-snapshot -netdelay none -netspeed full
ExecStartPost=/bin/bash -lc 'for i in $(seq 1 120); do if [ "$(/opt/android-sdk/platform-tools/adb -s emulator-5554 shell getprop sys.boot_completed 2>/dev/null | tr -d "\r")" = "1" ]; then exit 0; fi; sleep 2; done; exit 1'
Restart=always
RestartSec=10

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/bharatsim /tmp
RestrictSUIDSGID=true
LockPersonality=true
MemoryMax=6G
CPUQuota=400%
TasksMax=512
DeviceAllow=/dev/kvm rw

[Install]
WantedBy=multi-user.target
EOF

# Worker Daemon Service
mkdir -p /etc/bharatsim
cat << 'EOF' > /etc/bharatsim/worker.env
# Production Worker Configuration
BHARATSIM_API_URL=https://bharat-sim-81g2.vercel.app
BHARATSIM_WORKER_TOKEN=CHANGEME_AT_LEAST_32_RANDOM_CHARS_SECRET_KEY
BHARATSIM_WORKER_ID=production-worker-kvm-01
ANDROID_SERIAL=emulator-5554
BHARATSIM_ENABLE_LOCAL_APK_EXECUTION=true
BHARATSIM_POLL_SECONDS=5
BHARATSIM_SMOKE_DURATION_SECONDS=20
EOF
chmod 600 /etc/bharatsim/worker.env
chown bharatsim:bharatsim /etc/bharatsim/worker.env

cat << 'EOF' > /etc/systemd/system/bharatsim-worker.service
[Unit]
Description=BharatSim Android Execution Worker Daemon
Wants=network-online.target
Requires=bharatsim-emulator.service
After=network-online.target bharatsim-emulator.service

[Service]
Type=simple
User=bharatsim
Group=bharatsim
WorkingDirectory=/opt/bharatsim
EnvironmentFile=/etc/bharatsim/worker.env
Environment=HOME=/var/lib/bharatsim
Environment=ANDROID_HOME=/opt/android-sdk
Environment=ANDROID_SDK_ROOT=/opt/android-sdk
Environment=ANDROID_AVD_HOME=/var/lib/bharatsim/avd
Environment=PATH=/opt/android-sdk/platform-tools:/opt/android-sdk/cmdline-tools/latest/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 /opt/bharatsim/worker/agent.py
Restart=always
RestartSec=5

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/bharatsim /tmp /opt/bharatsim
RestrictSUIDSGID=true
LockPersonality=true
MemoryMax=4G
CPUQuota=300%
TasksMax=256

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo "  [OK] Systemd units registered: bharatsim-emulator.service, bharatsim-worker.service"

# 8. Post-Setup Instructions
echo "[8/8] Host bootstrap complete!"
echo "--------------------------------------------------------------------"
echo "NEXT STEPS TO ACTIVATE WORKER:"
echo "1. Set the production token in /etc/bharatsim/worker.env:"
echo "   sudo nano /etc/bharatsim/worker.env"
echo "2. Copy BharatSim repository files to /opt/bharatsim:"
echo "   git clone https://github.com/kaustubhdua/Bharat-Sim.git /opt/bharatsim"
echo "3. Start and enable the services:"
echo "   sudo systemctl enable --now bharatsim-emulator"
echo "   sudo systemctl enable --now bharatsim-worker"
echo "4. Monitor service status:"
echo "   sudo journalctl -u bharatsim-worker -f"
echo "===================================================================="

