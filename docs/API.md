# API reference (implemented in phase 2)
Auth: `Authorization: Bearer <token>` for REST, `?token=` for WebSockets. Generated schema: `/docs`, snapshot `docs/openapi.json`.

## REST
| Endpoint | Returns |
|---|---|
| `GET /api/health` (no auth) | liveness |
| `GET /api/session`, `POST /api/session/mode` | mode, agent/ROS capabilities |
| `GET /api/live/status` | `{mode, agent:{state,url,last_error,version}, ros:{available,distro,domain_id,rmw,error,discovery,discovery_error}|null, host}` |
| `GET /api/live/graph` | `{nodes[], topics[{name,types,publishers,subscribers}], services[], actions[], warnings[]}` |
| `GET /api/live/topic?name=` | types, publisher/subscriber endpoints with QoS, `qos_conflicts`, numeric `fields`, `fields_error` |
| `GET /api/live/topic/stats?name=` | stats if the topic is monitored, else `{monitored:false}` |
| `GET /api/live/node?name=` | publishers/subscribers/services of one node |
| `GET /api/live/subscriptions` | topics currently subscribed by the agent |
| `GET /api/host/metrics` | one host sample (agent machine) |
| `GET /api/app/diagnostics` | backend/agent memory, CPU, dropped events |
Errors: `503 agent_unavailable`, `503 ros_unavailable`, `404 topic_not_found|node_not_found`, `422 unsupported_type`.
Still `501`: `/api/live/tf`, `/api/live/logs`, `/api/series/*`, bags, record, diagnostics findings, layouts, test tools (later phases).

## `WS /ws/live`
Client → server: `{op:"watch", topic, hz, payload, fields[]}` · `{op:"unwatch", topic}` · `{op:"host", interval_s|null}`.
Server → client (`ch`): `status` · `sample {topic,t_ns,size,values?,payload?}` · `stats {topic,stats,status,evidence,publishers,subscribers,error}` ·
`host {…sample}` · `graph` (graph changed — refetch) · `ros_status` · `watch_error {topic,code,message}` · `host_error`.
`t_ns` is the agent's receive time; header stamps stay inside `payload`. Per-client queues are bounded (drop-oldest, counted in diagnostics).

## Agent protocol (`ws://127.0.0.1:8770`)
Request `{id, op, args}` → `{id, ok, result|error:{code,message}}`; events `{ch,…}`. Ops: `hello, graph.snapshot, topic.info, node.info, sub.set, sub.stop, sub.list, topic.stats, host.watch, host.sample, diag`.
