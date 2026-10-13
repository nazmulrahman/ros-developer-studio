#!/usr/bin/env bash
# Dependency check (read-only). Reports what is present; installs nothing.
ok(){ printf '  [ok]   %s\n' "$1"; }; no(){ printf '  [miss] %s\n' "$1"; }
echo "Python"; python3 -c 'import sys;assert sys.version_info>=(3,10)' 2>/dev/null && ok "python >= 3.10" || no "python >= 3.10"
for m in fastapi uvicorn pydantic msgpack psutil; do python3 -c "import $m" 2>/dev/null && ok "py:$m" || no "py:$m (pip install -e .)"; done
echo "ROS 2 (needed for Live mode / agent, and for bag decoding)"
[ -n "${ROS_DISTRO:-}" ] && ok "ROS_DISTRO=$ROS_DISTRO" || no "ROS environment not sourced"
for m in rclpy rosbag2_py; do python3 -c "import $m" 2>/dev/null && ok "py:$m" || no "py:$m"; done
echo "Frontend"; command -v node >/dev/null && ok "node $(node -v)" || no "node (>=18)"
