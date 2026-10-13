"""Bounded sensor previews. No robot-specific topic names; consumed by live/bag renderers."""
import base64
import io
import math
from .fields import describe

SUPPORTED = {"sensor_msgs/msg/" + t for t in ("Image", "CompressedImage", "LaserScan", "Imu", "BatteryState")}
SUPPORTED |= {"nav_msgs/msg/Odometry", "geometry_msgs/msg/Twist", "geometry_msgs/msg/TwistStamped", "tf2_msgs/msg/TFMessage", "diagnostic_msgs/msg/DiagnosticArray"}


def field(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def stamp(msg):
    s = field(field(msg, "header"), "stamp")
    sec, ns = field(s, "sec"), field(s, "nanosec")
    return int(sec) * 1_000_000_000 + int(ns) if sec is not None and ns is not None else None


def preview(msg, type_name):
    if type_name not in SUPPORTED:
        return {"error": f"No visualization adapter for {type_name}"}
    try:
        if type_name.endswith(("/Image", "/CompressedImage")):
            return camera(msg, type_name)
        if type_name.endswith("/LaserScan"):
            ranges = field(msg, "ranges", [])
            step = max(1, math.ceil(len(ranges) / 2048))
            minimum, maximum = field(msg, "range_min", 0), field(msg, "range_max", 0)
            angle, inc = field(msg, "angle_min", 0), field(msg, "angle_increment", 0)
            if not all(math.isfinite(x) for x in (minimum, maximum, angle, inc)) or maximum < minimum:
                raise ValueError("Invalid scan angle or range limits")
            points = []
            for i in range(0, len(ranges), step):
                r = float(ranges[i])
                if math.isfinite(r) and minimum <= r <= maximum:
                    a = angle + i * inc
                    points.append([r * math.cos(a), r * math.sin(a)])
            return {"kind": "scan", "points": points, "total": len(ranges), "stride": step,
                    "frame_id": field(field(msg, "header"), "frame_id", "")}
        return {"kind": "message", "data": describe(msg, max_items=256)}
    except Exception as e:
        return {"error": f"Preview unavailable: {type(e).__name__}: {e}"}


def camera(msg, type_name):
    # Optional dependency: other viewers remain usable without Pillow.
    from PIL import Image
    data = field(msg, "data", b"")
    if len(data) > 16 * 1024 * 1024:
        raise ValueError("Image exceeds the 16 MiB input limit")
    data = bytes(data)
    if type_name.endswith("/CompressedImage"):
        image = Image.open(io.BytesIO(data))
        if image.format not in ("JPEG", "PNG"):
            raise ValueError("Only JPEG and PNG compressed images are supported")
        if image.width * image.height > 16_000_000:
            raise ValueError("Image exceeds the 16 megapixel decode limit")
    else:
        w, h, stride = int(field(msg, "width", 0)), int(field(msg, "height", 0)), int(field(msg, "step", 0))
        enc = field(msg, "encoding", "").lower()
        formats = {"rgb8": ("RGB", "RGB", 3), "bgr8": ("RGB", "BGR", 3), "rgba8": ("RGBA", "RGBA", 4),
                   "bgra8": ("RGBA", "BGRA", 4), "mono8": ("L", "L", 1)}
        if enc not in formats:
            raise ValueError(f"Unsupported raw encoding {enc!r}; supported: {', '.join(formats)}")
        mode, rawmode, channels = formats[enc]
        if not (0 < w * h <= 16_000_000) or w <= 0 or h <= 0 or stride < w * channels or len(data) < stride * h:
            raise ValueError("Invalid image dimensions, stride or data length")
        image = Image.frombytes(mode, (w, h), data, "raw", rawmode, stride)
    original = [image.width, image.height]
    image.thumbnail((640, 480))
    image = image.convert("RGB")
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=75)
    return {"kind": "image", "mime": "image/jpeg", "base64": base64.b64encode(output.getvalue()).decode("ascii"),
            "width": image.width, "height": image.height, "original": original,
            "frame_id": field(field(msg, "header"), "frame_id", "")}
