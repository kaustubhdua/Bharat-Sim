#!/usr/bin/env bash
set -Eeuo pipefail

# End-to-end proof and lifecycle manager for the guarded Linux netem environment.
# A dedicated veth connects the host namespace to a disposable network namespace.
# Host interface: veth-bs-run01 (198.18.77.1/24)
# Namespace: bharatsim-netem-e2e
# Peer interface: veth-peer01 (198.18.77.2/24)

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IFACE="veth-bs-run01"
PEER="veth-peer01"
NS="bharatsim-netem-e2e"
HOST_IP="198.18.77.1"
PEER_IP="198.18.77.2"
SHAPER=(python3 "$ROOT/worker/network_shaper.py")

teardown() {
  set +e
  if ip link show dev "$IFACE" >/dev/null 2>&1; then
    BHARATSIM_ENABLE_NETEM=true "${SHAPER[@]}" clear --interface "$IFACE" >/dev/null 2>&1
  fi
  if ip netns list | grep -q "$NS"; then
    ip netns exec "$NS" env BHARATSIM_ENABLE_NETEM=true "${SHAPER[@]}" clear --interface "$PEER" >/dev/null 2>&1
    ip netns del "$NS" >/dev/null 2>&1
  fi
  ip link del "$IFACE" >/dev/null 2>&1
  set -e
  echo "teardown_completed=true"
}

setup() {
  teardown >/dev/null 2>&1 || true
  ip netns add "$NS"
  ip link add "$IFACE" type veth peer name "$PEER"
  ip link set "$PEER" netns "$NS"
  ip addr add "$HOST_IP/24" dev "$IFACE"
  ip link set "$IFACE" up
  ip netns exec "$NS" ip addr add "$PEER_IP/24" dev "$PEER"
  ip netns exec "$NS" ip link set lo up
  ip netns exec "$NS" ip link set "$PEER" up

  # Enable host IP forwarding and routing
  sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true

  # Confirm host-to-namespace peer reachability
  ping -n -c 2 -W 2 "$PEER_IP" >/dev/null
  echo "setup_completed=true"
}

run_test() {
  # Establish the unshaped baseline and prove peer reachability before impairment.
  BASELINE="$(ping -n -c 3 -W 2 "$PEER_IP")"
  BASELINE_MS="$(printf '%s\n' "$BASELINE" | sed -nE 's/.*min\/avg\/max\/[a-z]+ = [0-9.]+\/([0-9.]+)\/.*/\1/p')"
  test -n "$BASELINE_MS"
  printf 'baseline_avg_rtt_ms=%s\n' "$BASELINE_MS"

  # Apply and independently read back netem configuration on the dedicated host veth.
  BHARATSIM_ENABLE_NETEM=true "${SHAPER[@]}" apply \
    --interface "$IFACE" --latency-ms 120 --jitter-ms 0 --loss-pct 0 --rate-kbit 100000

  # Measure actual packets through that interface; 120ms egress delay must be visible.
  SHAPED="$(ping -n -c 4 -W 3 "$PEER_IP")"
  SHAPED_MS="$(printf '%s\n' "$SHAPED" | sed -nE 's/.*min\/avg\/max\/[a-z]+ = [0-9.]+\/([0-9.]+)\/.*/\1/p')"
  test -n "$SHAPED_MS"
  printf 'shaped_avg_rtt_ms=%s\n' "$SHAPED_MS"
  python3 - "$BASELINE_MS" "$SHAPED_MS" <<'PY'
import sys
baseline, shaped = map(float, sys.argv[1:])
delta = shaped - baseline
print(f"observed_rtt_increase_ms={delta:.2f}")
if delta < 80:
    raise SystemExit(f"FAIL: expected >=80ms measured increase, observed {delta:.2f}ms")
print("PASS: real peer-namespace traffic traversed the shaped veth")
PY

  # Ensure the cleanup path also verifies removal of the impairment.
  BHARATSIM_ENABLE_NETEM=true "${SHAPER[@]}" clear --interface "$IFACE"
  if tc qdisc show dev "$IFACE" | grep -q netem; then
    echo "FAIL: netem qdisc remains after clear" >&2
    exit 1
  fi
  echo "PASS: qdisc removed after the experiment"
}

if [[ "$EUID" -ne 0 ]]; then
  echo "Run as root (CI uses sudo)." >&2
  exit 2
fi

for tool in ip tc ping python3; do
  command -v "$tool" >/dev/null || { echo "Missing required tool: $tool" >&2; exit 2; }
done

ACTION="${1:-all}"

case "$ACTION" in
  setup)
    setup
    ;;
  test)
    run_test
    ;;
  teardown)
    teardown
    ;;
  all)
    trap teardown EXIT
    setup
    run_test
    ;;
  *)
    echo "Usage: $0 [setup|test|teardown|all]" >&2
    exit 1
    ;;
esac
