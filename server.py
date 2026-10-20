"""UDP service server: registers, heartbeats, answers requests."""
import argparse, signal, socket, sys, threading, time
from protocol import *


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--service", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--registry-ip", default="127.0.0.1")   # use 10.0.0.1 in Mininet
    ap.add_argument("--registry-port", type=int, default=REGISTRY_PORT)
    ap.add_argument("--heartbeat", type=float, default=HEARTBEAT_INTERVAL)
    ap.add_argument("--lease", type=float, default=LEASE_SECONDS)
    a = ap.parse_args()
    reg = (a.registry_ip, a.registry_port)

    svc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    svc_sock.bind(("0.0.0.0", a.port))
    ctl_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # registry traffic only

    info = dict(service=a.service, server_id=a.id, service_port=a.port, lease_seconds=a.lease)
    ctl_sock.sendto(encode({"type": REGISTER, **info}), reg)
    print(f"{a.id}: registered {a.service} on :{a.port}", flush=True)

    stop = threading.Event()

    def beat():
        while not stop.wait(a.heartbeat):
            ctl_sock.sendto(encode({"type": HEARTBEAT, **info}), reg)
    threading.Thread(target=beat, daemon=True).start()

    def shutdown(*_):
        ctl_sock.sendto(encode({"type": DEREGISTER, "service": a.service,
                                "server_id": a.id}), reg)
        print(f"{a.id}: deregistered, exiting", flush=True)
        sys.exit(0)
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)   # kill -9 skips this on purpose (T6)

    while True:
        data, addr = svc_sock.recvfrom(MAX_DGRAM)
        req = decode(data) or {}
        reply = {"type": "SERVICE_REPLY", "service": a.service, "server_id": a.id,
                 "echo": req.get("payload", ""), "time": time.time()}
        svc_sock.sendto(encode(reply), addr)


if __name__ == "__main__":
    main()
