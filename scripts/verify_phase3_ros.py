"""Isolated synthetic ROS 2 smoke check; never uses the robot's ROS domain.
Run: source /opt/ros/humble/setup.bash; .venv/bin/python -m scripts.verify_phase3_ros
Use --serve to keep the labelled test fixture open for browser checks (Ctrl-C stops it).
"""
import os
os.environ["ROS_DOMAIN_ID"] = "187"
os.environ["ROS_LOCALHOST_ONLY"] = "1"
os.environ["ROS_LOG_DIR"] = "/tmp/rds-phase3-ros-logs"
os.environ["STUDIO_PREFERENCES"] = "/tmp/rds-phase3-test-preferences.json"
import argparse
import math
import time
import threading
import httpx
import rclpy
from rclpy.qos import QoSProfile, QoSDurabilityPolicy
from sensor_msgs.msg import Image, LaserScan, Imu, BatteryState
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist, TransformStamped
from tf2_msgs.msg import TFMessage
from agent.ros_graph.backend import RclpyBackend
from tests.fakes import AgentThread, BackendThread
from tests.conftest import Browser
from websockets.sync.client import connect


def main():
    args = argparse.ArgumentParser(); args.add_argument("--serve", action="store_true"); args = args.parse_args()
    ros = RclpyBackend()
    node = rclpy.create_node("synthetic_phase3_fixture", namespace="/studio_test")
    node.declare_parameter("fixture_label", "Synthetic test data; no robot connected")
    ros._executor.add_node(node)
    messages = {}
    image = Image(); image.width = 320; image.height = 240; image.encoding = "rgb8"; image.step = 960
    image.data = [30, 90, 130] * (320 * 240); messages["camera"] = image
    scan = LaserScan(); scan.range_min = 0.1; scan.range_max = 10.0; scan.angle_min = -math.pi; scan.angle_increment = math.pi / 180
    scan.ranges = [2.0 + 0.5 * math.sin(i * 0.1) for i in range(360)]; messages["scan"] = scan
    imu = Imu(); imu.orientation.w = 1.0; imu.linear_acceleration.z = 9.81; messages["imu"] = imu
    battery = BatteryState(); battery.present = True; battery.voltage = 24.2; battery.percentage = 0.75; messages["battery"] = battery
    odom = Odometry(); odom.pose.pose.orientation.w = 1.0; odom.child_frame_id = "test_base"; messages["odom"] = odom
    twist = Twist(); twist.linear.x = 0.4; messages["feedback"] = twist
    pubs = {key: node.create_publisher(type(msg), "/studio_test/" + key, 10) for key, msg in messages.items()}
    static_tf = TFMessage(); transform = TransformStamped(); transform.header.frame_id = "test_world"; transform.child_frame_id = "test_base"; transform.transform.rotation.w = 1.0; static_tf.transforms = [transform]
    dynamic_tf = TFMessage(); moving = TransformStamped(); moving.header.frame_id = "test_base"; moving.child_frame_id = "test_camera"; moving.transform.rotation.w = 1.0; dynamic_tf.transforms = [moving]
    tf_pub = node.create_publisher(TFMessage, "/tf", 10)
    static_pub = node.create_publisher(TFMessage, "/tf_static", QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL))
    static_pub.publish(static_tf)  # published before any subscriber exists
    stop = threading.Event()
    def emit():
        while not stop.wait(0.05):
            t = time.monotonic()
            odom.pose.pose.position.x = math.cos(t * 0.2); odom.pose.pose.position.y = math.sin(t * 0.2)
            for key, msg in messages.items():
                if hasattr(msg, "header"):
                    msg.header.stamp = node.get_clock().now().to_msg(); msg.header.frame_id = "test_world"
                pubs[key].publish(msg)
            moving.header.stamp = node.get_clock().now().to_msg(); tf_pub.publish(dynamic_tf)
    producer = threading.Thread(target=emit, daemon=True); producer.start()
    agent = AgentThread(ros).start(); backend = BackendThread(f"ws://127.0.0.1:{agent.port}")
    try:
        with httpx.Client(base_url=backend.url, headers={"Authorization": "Bearer tok"}, timeout=10) as http:
            for _ in range(60):
                status = http.get("/api/live/status").json()
                if status["agent"]["state"] == "connected": break
                time.sleep(0.1)
            params = http.get("/api/live/parameters", params={"name": "/studio_test/synthetic_phase3_fixture"})
            assert params.status_code == 200, params.text
            assert any(p["value"] == "Synthetic test data; no robot connected" for p in params.json()["parameters"])
            browser = Browser(connect(backend.ws_url))
            for topic in ["/studio_test/" + key for key in messages] + ["/tf", "/tf_static"]:
                browser.send(op="watch", topic=topic, hz=2, visual=True)
            samples = {}
            end = time.monotonic() + 10
            while len(samples) < 8 and time.monotonic() < end:
                event = browser.wait(lambda e: e["ch"] in ("sample", "watch_error"), timeout=5)
                assert event["ch"] == "sample", event
                assert "error" not in event.get("visual", {}), event
                samples[event["topic"]] = event
            assert len(samples) == 8, samples.keys()
            assert samples["/studio_test/camera"]["visual"]["width"] == 320
            assert samples["/tf_static"]["visual"]["data"]["transforms"][0]["child_frame_id"] == "test_base"
            assert samples["/studio_test/imu"]["stamps"]["header_ns"] is not None
            late = Browser(connect(backend.ws_url))
            late.send(op="watch", topic="/tf_static", hz=2, visual=True)
            cached = late.wait(lambda e: e["ch"] == "sample", timeout=3)
            assert cached["visual"]["data"]["transforms"][0]["child_frame_id"] == "test_base"
            merged = http.get("/api/live/tf").json()
            assert merged["roots"] == ["test_world"] and {edge["child"] for edge in merged["edges"]} == {"test_base", "test_camera"}
            late.close(); browser.close()
            print("PASS: Humble real graph, namespaced read-only parameters, camera, scan, IMU, battery, odometry, Twist and late static TF.", flush=True)
            print(f"Synthetic test fixture UI: {backend.url} · test token: tok · isolated ROS domain 187", flush=True)
            if args.serve:
                while True: time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set(); producer.join(2); backend.stop(); agent.stop()
        ros._executor.remove_node(node); node.destroy_node(); ros.close()

if __name__ == "__main__": main()
