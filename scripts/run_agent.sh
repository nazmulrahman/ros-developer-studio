#!/usr/bin/env bash
# Start the ROS 2 agent on the robot host. Sources ROS and (optionally) a workspace first.
#   scripts/run_agent.sh                       # uses /opt/ros/$ROS_DISTRO or auto-detects humble/jazzy
#   WORKSPACE=~/ros2_ws scripts/run_agent.sh   # also source a workspace (needed for custom message types)
set -e
cd "$(dirname "$0")/.."
if [ -z "${ROS_DISTRO:-}" ]; then
  for d in jazzy humble; do [ -f "/opt/ros/$d/setup.bash" ] && { set +u; source "/opt/ros/$d/setup.bash"; break; }; done
fi
[ -n "${WORKSPACE:-}" ] && [ -f "$WORKSPACE/install/setup.bash" ] && { set +u; source "$WORKSPACE/install/setup.bash"; }
echo "ROS_DISTRO=${ROS_DISTRO:-<none>} ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}"
[ -f .venv/bin/activate ] && source .venv/bin/activate
exec python3 -m agent.main "$@"
