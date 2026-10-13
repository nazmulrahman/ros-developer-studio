#!/usr/bin/env python3
"""ROS 2 companion agent. Run with the ROS environment sourced (see scripts/run_agent.sh).

Without rclpy the agent still starts and serves host metrics; ROS features report 'ROS environment unavailable'.
"""
import argparse, asyncio, sys

from .host_metrics.collector import HostCollector
from .ros_graph.backend import NullRos
from .server import AgentServer


def build_ros(disable: bool):
    if disable:
        return NullRos("ROS access disabled with --no-ros")
    try:
        from .ros_graph.backend import RclpyBackend
        return RclpyBackend()
    except Exception as e:
        return NullRos(f"{type(e).__name__}: {e}. Source your ROS 2 setup.bash (and workspace) before starting the agent.")


async def run(a) -> None:
    ros = build_ros(a.no_ros)
    info = ros.info()
    server = AgentServer(ros, HostCollector(), window_s=a.window, graph_interval_s=a.graph_interval, token=a.token)
    srv = await server.serve(a.host, a.port)
    print(f"agent listening ws://{a.host}:{a.port}  ROS available={info['available']} distro={info['distro']} "
          f"domain={info['domain_id']}" + (f"  ({info['error']})" if info["error"] else ""), flush=True)
    try:
        await asyncio.Future()
    finally:
        srv.close()
        await server.aclose()
        ros.close()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8770)
    p.add_argument("--token", default=None, help="Shared token the backend must present (optional, loopback only)")
    p.add_argument("--window", type=float, default=5.0, help="Frequency measurement window, seconds")
    p.add_argument("--graph-interval", type=float, default=2.0, help="Graph change check interval, seconds")
    p.add_argument("--no-ros", action="store_true", help="Run host metrics only")
    try:
        asyncio.run(run(p.parse_args()))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
