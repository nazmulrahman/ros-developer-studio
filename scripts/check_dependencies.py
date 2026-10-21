"""Read-only installation check: python -m scripts.check_dependencies."""
import importlib
import json
import shutil
import sys

def main():
    checks = {}
    for name in ("fastapi", "pydantic", "uvicorn", "yaml", "psutil", "PIL", "rclpy", "rosbag2_py", "rosidl_runtime_py"):
        try:
            module = importlib.import_module(name)
            checks[name] = {"available": True, "version": getattr(module, "__version__", None)}
        except Exception as exc:
            checks[name] = {"available": False, "reason": str(exc)}
    checks["ros2_cli"] = {"available": shutil.which("ros2") is not None}
    print(json.dumps({"python": sys.version, "checks": checks, "note": "Source ROS and custom-message workspaces before checking. Hardware and distribution compatibility require runtime acceptance."}, indent=2))
    return 0 if all(checks[x]["available"] for x in ("fastapi", "pydantic", "uvicorn", "yaml", "psutil")) else 1

if __name__ == "__main__":
    raise SystemExit(main())
