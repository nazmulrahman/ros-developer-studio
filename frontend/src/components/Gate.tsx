import type { ReactNode } from "react";
import { useLive } from "../services/live";
import { Empty } from "./ui";

/** Shows why a live page has no data instead of rendering empty widgets. needsRos=false for host-only pages. */
export function Gate({ needsRos = true, children }: { needsRos?: boolean; children: ReactNode }) {
  const { status, wsState } = useLive();
  if (wsState === "idle") return <Empty title="Enter the access token">Paste the token printed by the backend into the box in the top bar.</Empty>;
  if (wsState === "unauthorized") return <Empty title="Token rejected">The backend refused the token. Copy it again from the backend's console output.</Empty>;
  if (wsState !== "open" || !status) return <Empty title="Backend not reachable">Waiting for the backend; the page reconnects automatically.</Empty>;
  if (status.mode === "offline") return <Empty title="Offline bag mode">Live data is not used in this mode. Offline bag analysis is planned for phase 4.</Empty>;
  if (status.agent.state !== "connected")
    return <Empty title="Agent disconnected">The backend cannot reach the ROS agent{status.agent.url ? ` at ${status.agent.url}` : ""}.
      Start it on the robot host with <span className="mono">scripts/run_agent.sh</span>.{status.agent.last_error ? ` Last error: ${status.agent.last_error}` : ""}</Empty>;
  if (needsRos && status.ros && !status.ros.available)
    return <Empty title="ROS environment unavailable">The agent is connected but cannot use ROS 2: {status.ros.error}</Empty>;
  return <>{children}</>;
}
