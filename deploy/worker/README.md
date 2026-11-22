# BharatSim — Production Android Worker Host Deployment Guide

This guide provisions a **single-worker controlled-beta host** with one persistent Android emulator and KVM. It is not a per-job VM/microVM sandbox and is not approved for public arbitrary APK execution.

The bootstrap keeps `BHARATSIM_ENABLE_LOCAL_APK_EXECUTION=false` by default and restricts `/dev/kvm` to the dedicated `kvm` group (mode 0660). Do not enable APK execution on this host for untrusted public uploads. Production public execution requires a separately reviewed per-job isolation layer, default-deny egress, quotas and teardown.

Control plane: `https://bharat-sim-81g2.vercel.app`.

---

## 1. Cloud Infrastructure Comparison Matrix

| Cloud Provider | Machine Type | vCPU / RAM | KVM / Nested Virt Support | Estimated Cost | Recommendation Level |
|---|---|---|---|---|---|
| **Google Cloud (GCE)** | `n2-standard-4` | 4 vCPU / 16 GB | Supported (`--enable-nested-virtualization`) | ~$0.19/hr (~$140/mo) | **High (Best Cloud Option)** |
| **Hetzner Cloud** | `CPX31` / `AX41` | 4 vCPU / 16 GB (or Dedicated Bare-Metal) | Native KVM on dedicated AX line | ~€40/mo (Bare-metal) | **High (Best Value / Cost)** |
| **AWS EC2** | `c5.metal` / `c5n.metal` | Bare-Metal | Native Hardware Virtualization | ~$4.00/hr (Metal only) | Medium (Expensive for staging) |
| **Self-Hosted Linux / Mac** | Any Intel/AMD or Apple Silicon | 4+ Cores / 16 GB | Native KVM / Hypervisor.framework | Existing hardware ($0) | **High (Optimal for In-House Testing)** |

---

## 2. Fast Setup (Google Cloud Compute Engine)

### Step 1: Create GCE Instance with Nested Virtualization
```bash
gcloud compute instances create bharatsim-worker-node \
    --zone=asia-south1-a \
    --machine-type=n2-standard-4 \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=100GB \
    --boot-disk-type=pd-ssd \
    --enable-nested-virtualization \
    --tags=bharatsim-worker
```

### Step 2: SSH and Run Automated Setup
```bash
gcloud compute ssh bharatsim-worker-node --zone=asia-south1-a

# Clone repository
git clone https://github.com/kaustubhdua/Bharat-Sim.git /tmp/bharatsim-repo
cd /tmp/bharatsim-repo

# Run automated bootstrap
sudo bash deploy/worker/setup-worker-host.sh
```

### Step 3: Configure Worker Token & Start Services
```bash
sudo nano /etc/bharatsim/worker.env
# Set BHARATSIM_WORKER_TOKEN=<your-32-char-secret>

# Start emulator and worker daemon
sudo systemctl enable --now bharatsim-emulator
sudo systemctl enable --now bharatsim-worker

# Check status
sudo systemctl status bharatsim-worker
sudo journalctl -u bharatsim-worker -f
```

---

## 3. Alternative: Docker Deployment with KVM Passthrough

If you prefer deploying via Docker on a host that already has `/dev/kvm`:

```bash
cd deploy/worker
export BHARATSIM_WORKER_TOKEN="your-secure-worker-token-at-least-32-chars"
docker compose up -d
docker logs -f bharatsim-worker-node
```

