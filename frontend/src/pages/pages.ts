export interface PageDef { id: string; title: string; icon: string; summary: string; phase: number; ready: boolean }
export const PAGES: PageDef[] = [
  { id: "overview", title: "Overview", icon: "dashboard", phase: 2, ready: true, summary: "Connection status, ROS environment summary and recent events." },
  { id: "explorer", title: "ROS Explorer", icon: "graph", phase: 2, ready: true, summary: "Nodes, topics, services and actions of the connected ROS 2 environment." },
  { id: "inspector", title: "Topic Inspector", icon: "inspect", phase: 2, ready: true, summary: "Live messages, frequency, bandwidth and QoS for one topic." },
  { id: "signals", title: "Signals", icon: "signals", phase: 2, ready: true, summary: "Plot numeric fields from any topic in real time." },
  { id: "motion", title: "Motion", icon: "motion", phase: 3, ready: false, summary: "Command versus measured velocity, wheel and motor speed, odometry path through configurable field mappings." },
  { id: "viz", title: "Visualizations", icon: "eye", phase: 3, ready: false, summary: "Camera, LaserScan, IMU, battery, odometry and TF tree." },
  { id: "bags", title: "Bag Studio", icon: "bag", phase: 4, ready: false, summary: "Record, open, inspect, seek, play and analyse ROS bags without a robot." },
  { id: "diagnostics", title: "Diagnostics", icon: "health", phase: 5, ready: false, summary: "Findings with evidence, QoS and TF checks, dropout detection and logs." },
  { id: "host", title: "Host Metrics", icon: "cpu", phase: 2, ready: true, summary: "CPU, memory, disk, network, temperature and GPU of the robot host." },
  { id: "tests", title: "Test Tools", icon: "flask", phase: 6, ready: false, summary: "Optional, disabled-by-default publish, service and velocity tests." },
  { id: "settings", title: "Settings", icon: "settings", phase: 3, ready: false, summary: "Connection, bag directories, buffer limits and saved layouts." },
];
