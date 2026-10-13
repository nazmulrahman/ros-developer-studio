"""ROS Developer Studio backend."""
import sys

try:
    import pydantic
    _major = int(pydantic.VERSION.split(".")[0])
except ImportError:
    _major = 0
if _major < 2:
    sys.exit(
        "ROS Developer Studio needs pydantic >= 2 (found "
        + (pydantic.VERSION if _major else "none")
        + ").\nUbuntu 22.04 ships pydantic 1.x as a system package. Use a virtual environment:\n"
        "  python3 -m venv --system-site-packages .venv && source .venv/bin/activate\n"
        "  pip install -r requirements.txt\n"
        "(--system-site-packages keeps ROS 2's rclpy importable; packages installed in the venv take priority.)"
    )
