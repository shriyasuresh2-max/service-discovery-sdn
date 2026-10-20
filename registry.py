"""UDP service registry. Key = (service, server_id)."""
import argparse, json, socket, threading, time, urllib.request
from protocol import *

registry = {}  # (service, server_id) -> dict


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def notify(url, path, payload):
    """Fire-and-forget POST to the SDN controller API (never blocks registry)."""
    if not url:
        return
    def _post():
        try:
            req = urllib.request.Request(url + path, json.dumps(payload).encode(),
                                         {"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=2).read()
        except Exception as e:
            log(f"controller notify {path} failed: {e}")
    threading.Thread(target=_post, daemon=True).start()


def upsert(msg, ip, now, controller):
    try:
        svc, sid = msg["service"], msg["server_id"]
        port = int(msg["service_port"])
        lease = float(msg.get("lease_seconds", LEASE_SECONDS))
    except (KeyError, ValueError, TypeError):
        log("bad REGISTER/HEARTBEAT, ignored"); return
    key = (svc, sid)
    new = key not in registry
    registry[key] = dict(service_name=svc, server_id=sid, server_ip=ip,
                         service_port=port, last_seen=now, lease_expiry=now + lease)
    if new:
        log(f"REGISTERED {svc}/{sid} at {ip}:{port} lease={lease}s")
        notify(controller, "/service/register",
               dict(service=svc, server_id=sid, ip=ip, port=port))


def live(service, now):
    return [e for e in registry.values()
            if e["service_name"] == service and e["lease_expiry"] > now]


def expire(now, controller):
    for key in [k for k, e in registry.items() if e["lease_expiry"] <= now]:
        e = registry.pop(key)
        log(f"EXPIRED {key[0]}/{key[1]} ({e['server_ip']}:{e['service_port']})")
        notify(controller, "/service/expire",
               dict(service=key[0], server_id=key[1], ip=e["server_ip"], port=e["service_port"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=REGISTRY_PORT)
    ap.add_argument("--controller-url", default=None,
                    help="e.g. http://192.168.56.1:8080 (optional)")
    a = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((a.host, a.port))
    sock.settimeout(1.0)  # wake up every second to expire stale entries
    log(f"registry listening on {a.host}:{a.port}")

    while True:
        try:
            data, (ip, _) = sock.recvfrom(MAX_DGRAM)
        except socket.timeout:
            expire(time.monotonic(), a.controller_url); continue
        now = time.monotonic()
        expire(now, a.controller_url)
        msg = decode(data)
        if msg is None:
            log(f"malformed datagram from {ip}"); continue
        t = msg["type"]
        if t in (REGISTER, HEARTBEAT):          # heartbeat also re-registers
            upsert(msg, ip, now, a.controller_url)
        elif t == DEREGISTER:
            e = registry.pop((msg.get("service"), msg.get("server_id")), None)
            if e:
                log(f"DEREGISTERED {msg['service']}/{msg['server_id']}")
                notify(a.controller_url, "/service/deregister",
                       dict(service=msg["service"], server_id=msg["server_id"],
                            ip=e["server_ip"], port=e["service_port"]))
        elif t == DISCOVER:
            svc = msg.get("service")
            found = live(svc, now)
            if found:
                reply = {"type": DISCOVER_REPLY, "service": svc,
                         "endpoints": [dict(server_id=e["server_id"], ip=e["server_ip"],
                                            port=e["service_port"]) for e in found]}
            else:
                reply = {"type": NOT_FOUND, "service": svc}
            sock.sendto(encode(reply), (ip, _))
            log(f"DISCOVER {svc} from {ip} -> {reply['type']}")
        else:
            log(f"unknown type {t!r}")


if __name__ == "__main__":
    main()
