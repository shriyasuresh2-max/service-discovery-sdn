"""UDP client: discover a service, then contact it. Reports two latencies."""
import argparse, socket, time
from protocol import *


def discover(service, reg, timeout):
    """Return (reply_dict_or_None, discovery_latency_ms_or_None)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    t0 = time.perf_counter_ns()
    s.sendto(encode({"type": DISCOVER, "service": service}), reg)
    try:
        data, _ = s.recvfrom(MAX_DGRAM)
    except socket.timeout:
        return None, None
    finally:
        t1 = time.perf_counter_ns()
        s.close()
    return decode(data), (t1 - t0) / 1e6


def call_service(ep, timeout):
    """Return service round-trip ms, or None on failure."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    t0 = time.perf_counter_ns()
    s.sendto(encode({"type": "SERVICE_REQUEST", "payload": "hello"}), (ep["ip"], ep["port"]))
    try:
        s.recvfrom(MAX_DGRAM)
    except socket.timeout:
        return None
    finally:
        s.close()
    return (time.perf_counter_ns() - t0) / 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", required=True)
    ap.add_argument("--registry-ip", default="127.0.0.1")   # 10.0.0.1 in Mininet
    ap.add_argument("--registry-port", type=int, default=REGISTRY_PORT)
    ap.add_argument("--timeout", type=float, default=2.0)
    a = ap.parse_args()

    reply, d_ms = discover(a.service, (a.registry_ip, a.registry_port), a.timeout)
    if reply is None:
        print(f"TIMEOUT: no registry reply within {a.timeout}s"); return 1
    if reply["type"] == NOT_FOUND:
        print(f"NOT_FOUND: {a.service} (discovery latency {d_ms:.3f} ms)"); return 2
    eps = reply["endpoints"]
    print(f"discovery latency (registry reply): {d_ms:.3f} ms, {len(eps)} instance(s):")
    for e in eps:
        print(f"  {e['server_id']} -> {e['ip']}:{e['port']}")
    ep = eps[0]
    s_ms = call_service(ep, a.timeout)
    if s_ms is None:
        print(f"service {ep['server_id']} did not answer within {a.timeout}s"); return 3
    print(f"service round-trip to {ep['server_id']}: {s_ms:.3f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
