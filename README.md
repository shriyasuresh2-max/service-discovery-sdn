# Service Discovery System (UDP + Mininet + SDN)

A UDP-based service discovery application running in a Mininet network
controlled by an OpenFlow 1.3 SDN controller. Servers advertise themselves to
a registry, clients discover them by service name, the registry expires
servers that stop responding, and the SDN controller installs and removes
forwarding rules as service state changes.

## How it works
- **Servers** (weather, files) register with the registry and send a heartbeat every 3 seconds.
- **The registry** keeps each server on a 10-second lease. A normal shutdown deregisters immediately. A crashed server is removed when its lease expires.
- **Clients** send a `DISCOVER` request to the registry and receive the list of live endpoints (or `NOT_FOUND`), then contact one of them. No server addresses are hardcoded.
- **The SDN controller** receives `register`, `deregister` and `expire` events from the registry over an HTTP API and installs or deletes OpenFlow rules for that service's UDP traffic.

## Topology
| Host | Role | Address | Port |
|------|------|---------|------|
| h1 | Registry | 10.0.0.1 | UDP 4000 |
| h2 | Client | 10.0.0.2 | - |
| h3 | Weather server | 10.0.0.3 | UDP 5001 |
| h4 | File server | 10.0.0.4 | UDP 5002 |

All hosts connect to one OpenFlow 1.3 switch (`s1`). The controller listens for
OpenFlow on TCP 6653 and serves its HTTP API on port 8080 (reachable from h1 at
`http://10.0.0.254:8080`).

## Repository layout
```
app/          UDP registry, server, client and shared protocol
controller/   SDN controller
topology.py   Mininet topology
tests/        automated tests
results/      measurements and graphs
docs/         documentation
```

## Message protocol (JSON over UDP)
| Message | Purpose |
|---------|---------|
| `REGISTER` | Add a service instance |
| `HEARTBEAT` | Refresh its lease (also re-registers it if the registry forgot it) |
| `DEREGISTER` | Remove it on normal shutdown |
| `DISCOVER` | Ask for a service by name |
| `DISCOVER_REPLY` | List of live endpoints `[{server_id, ip, port}]` |
| `NOT_FOUND` | No live instance of that service |

Settings: registry port 4000, heartbeat 3 s, lease 10 s. The registry takes a
server's IP from the packet's source address, not from the JSON.

## Registry to controller API
The registry sends HTTP POST requests with JSON `{service, server_id, ip, port}`:

- `POST /service/register` - a server appeared
- `POST /service/deregister` - normal shutdown
- `POST /service/expire` - lease timed out (crash)
- `GET /health` - controller status

## Requirements
- Ubuntu with Python 3
- Mininet and Open vSwitch:
```
  sudo apt install mininet openvswitch-switch
```
- OS-Ken (SDN controller framework):
```
  pip install os-ken
```

The application itself uses only the Python standard library.

## Running it
1. **Start the controller** from the repository root, in its own terminal:
```
   osken-manager controller/sdn_controller.py
```
2. **Start the Mininet topology** from the repository root, in another terminal:
```
   sudo python3 topology.py
```
3. At the `mininet>` prompt, **start the registry, servers and client**:
```
   h1 python3 app/registry.py --controller-url http://10.0.0.254:8080 > /tmp/registry.log 2>&1 &
   h3 python3 app/server.py --service weather --port 5001 --id weather-1 --registry-ip 10.0.0.1 > /tmp/w1.log 2>&1 &
   h4 python3 app/server.py --service files --port 5002 --id files-1 --registry-ip 10.0.0.1 > /tmp/f1.log 2>&1 &
   h2 python3 app/client.py --service weather --registry-ip 10.0.0.1
```
4. **Inspect the switch rules** from another terminal:
```
   sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

### Testing the application without Mininet
```
python3 app/registry.py
python3 app/server.py --service weather --port 5001 --id weather-1
python3 app/client.py --service weather
```

### Client exit codes
`0` success, `1` registry timeout, `2` service not found, `3` service did not answer.

## Test scenarios
| Scenario | Expected result |
|----------|-----------------|
| Register a server | Registry lists it; controller installs a flow |
| Discover a service | Client receives the endpoint list |
| Discover a missing service | `NOT_FOUND` |
| Two servers for one service | Both are returned |
| Normal shutdown | Server is removed at once; flow deleted |
| Abrupt crash (`kill -9`) | Entry expires after about 10 s; flow deleted |
