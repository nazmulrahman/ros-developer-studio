"""Verify native SQLite bag sensor snapshots without publishing to ROS."""
import tempfile
from pathlib import Path
import rosbag2_py
from rclpy.serialization import serialize_message
from sensor_msgs.msg import LaserScan
from backend.bags.studio import BagLibrary

def main():
    with tempfile.TemporaryDirectory(prefix="studio-scan-") as root:
        bag = Path(root) / "scan"
        writer = rosbag2_py.SequentialWriter()
        writer.open(rosbag2_py.StorageOptions(uri=str(bag),storage_id="sqlite3"),rosbag2_py.ConverterOptions("",""))
        writer.create_topic(rosbag2_py.TopicMetadata(name="/scan",type="sensor_msgs/msg/LaserScan",serialization_format="cdr"))
        msg=LaserScan();msg.header.frame_id="laser";msg.range_min=.1;msg.range_max=10.;msg.angle_increment=.1;msg.ranges=[1.,2.,3.]
        writer.write("/scan",serialize_message(msg),1_000_000_000)
        msg.ranges=[2.,3.,4.];writer.write("/scan",serialize_message(msg),2_000_000_000)
        del writer
        library=BagLibrary([root]);meta=library.summary(bag);identifier=meta["bag_id"]
        assert library.snapshot(identifier,"/scan",0) is None
        first=library.snapshot(identifier,"/scan",1_500_000_000)
        assert first["visual"]["kind"] == "scan" and len(first["visual"]["points"]) == 3
        assert first["stamps"]["receive_ns"] is None and first["stamps"]["record_ns"] == "1000000000"
        last=library.snapshot(identifier,"/scan",2_000_000_000)
        assert last["visual"]["points"][0][0] == 2.
        assert library.snapshot(identifier,"/scan",1_000_000_000)["visual"]["points"][0][0] == 1.
        assert library.topic_detail(identifier,"/scan")["fields"]
        print("PASS: recorded LaserScan preview, clocks, seek and numeric schema; no ROS graph used")
if __name__ == "__main__": main()
