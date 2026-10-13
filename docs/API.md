# API reference (Phases 2–3)
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
| `GET /api/live/parameters?name=/ns/node` | read-only parameters (at most 500); 3-second service deadline, HTTP 504 on timeout |
| `GET /api/live/tf` | merged observed TF hierarchy: frames, transforms, roots, disconnected groups and diagnostics |
| `GET/PUT /api/settings` | read server configuration + preferences; PUT accepts only `preview_hz` (0.5–5), `motion_hz` (1–50), `stale_after_s` (1–60) |
| `GET/POST /api/layouts`, `PUT/DELETE /api/layouts/{id}` | authenticated layout CRUD; `{name, config:{signals?,motion?,visualizations?}}`; at most 32 layouts / 512 KiB total |
| `GET /api/live/subscriptions` | topics currently subscribed by the agent |
| `GET /api/host/metrics` | one host sample (agent machine) |
| `GET /api/app/diagnostics` | backend/agent memory, CPU, dropped events |
Errors: `503 agent_unavailable`, `503 ros_unavailable`, `404 topic_not_found|node_not_found`, `422 unsupported_type`.
Still `501`: `/api/live/logs`, `/api/series/*`, bags, record, diagnostics findings, test tools (later phases).

## `WS /ws/live`
Client → server: `{op:"watch", topic, hz, payload, fields[], visual?}` · `{op:"unwatch", topic}` · `{op:"host", interval_s|null}`.
Server → client (`ch`): `status` · `sample {topic,t_ns,size,values?,payload?,visual?,source_mode,source_id,type,stamps}` · `stats {topic,stats,status,evidence,publishers,subscribers,error}` ·
`host {…sample}` · `tf {data:{frames,edges,roots,components,diagnostics}}` · `graph` (graph changed — refetch) · `ros_status` · `watch_error {topic,code,message}` · `host_error`.
`t_ns` remains a legacy numeric receive timestamp. `stamps` contains separate `header_ns`, `receive_ns` and `record_ns`: decimal strings preserve nanosecond precision in JavaScript, or null when absent. Live `record_ns` is always null. `visual:true` explicitly opts into bounded sensor previews. Image previews carry base64 JPEG, scans carry at most 2,048 XY points, other supported sensors carry bounded structured data. The visual channel is capped at 5 Hz independently of numeric field sampling. Per-client queues are bounded (drop-oldest, counted in diagnostics).

## Agent protocol (`ws://127.0.0.1:8770`)
Request `{id, op, args}` → `{id, ok, result|error:{code,message}}`; events `{ch,…}`. Ops: `hello, graph.snapshot, topic.info, node.info, node.parameters, sub.set, sub.stop, sub.list, topic.stats, host.watch, host.sample, diag`.

The unified TF viewer subscribes to discovered `TFMessage` topics. The backend merges their bounded previews into `/api/live/tf`, labels source topics and static/dynamic edges, and clears the model on agent disconnect. It is an observed current hierarchy rather than a historical TF2 lookup buffer.
