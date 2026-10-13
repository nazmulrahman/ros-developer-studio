"""Host metrics for the machine running the agent. Unsupported metrics are None -> UI shows 'Unavailable'."""
from __future__ import annotations
import glob, os, platform, shutil, socket, subprocess, time
from typing import Callable

import psutil


def _nvidia_smi(run=subprocess.run, which=shutil.which) -> dict | None:
    if not which("nvidia-smi"):
        return None
    try:
        r = run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=1.5, check=True)
        u, mu, mt, t = [float(x) for x in r.stdout.splitlines()[0].split(",")]
        return {"source": "nvidia-smi", "util_percent": u, "mem_used_mib": mu, "mem_total_mib": mt, "temp_c": t}
    except Exception:
        return None


def _read(path: str) -> str | None:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _jetson_sysfs() -> dict | None:
    """Best-effort Jetson GPU load/temperature from sysfs. Unverified on hardware."""
    load = None
    for p in ("/sys/devices/gpu.0/load", "/sys/devices/platform/gpu.0/load", "/sys/devices/platform/bus@0/17000000.gpu/load"):
        v = _read(p)
        if v and v.lstrip("-").isdigit():
            load = int(v) / 10.0
            break
    if load is None:
        return None
    temp = None
    for z in glob.glob("/sys/class/thermal/thermal_zone*"):
        if (_read(z + "/type") or "").upper().startswith("GPU"):
            raw = _read(z + "/temp")
            if raw and raw.lstrip("-").isdigit():
                temp = int(raw) / 1000.0
                break
    return {"source": "jetson-sysfs", "util_percent": load, "mem_used_mib": None, "mem_total_mib": None, "temp_c": temp}


class HostCollector:
    def __init__(self, gpu_probes: list[Callable[[], dict | None]] | None = None, disk_path: str | None = None):
        self.gpu_probes = gpu_probes if gpu_probes is not None else [_nvidia_smi, _jetson_sysfs]
        self.disk_path = disk_path or (os.path.abspath(os.sep))
        self._net = psutil.net_io_counters()
        self._net_t = time.monotonic()
        psutil.cpu_percent(interval=None, percpu=True)
        self.info = {"name": socket.gethostname(), "os": f"{platform.system()} {platform.release()}",
                     "machine": platform.machine(), "cores": psutil.cpu_count(logical=True)}

    def _temps(self) -> tuple[float | None, dict]:
        fn = getattr(psutil, "sensors_temperatures", None)
        if not fn:
            return None, {}
        try:
            groups = fn() or {}
        except Exception:
            return None, {}
        flat = {f"{g}:{t.label or i}": t.current for g, ts in groups.items() for i, t in enumerate(ts) if t.current is not None}
        return (max(flat.values()) if flat else None), flat

    def sample(self) -> dict:
        now = time.monotonic()
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        vm, sw = psutil.virtual_memory(), psutil.swap_memory()
        net = psutil.net_io_counters()
        dt = max(now - self._net_t, 1e-6)
        rx = max(0, net.bytes_recv - self._net.bytes_recv) * 8 / dt
        tx = max(0, net.bytes_sent - self._net.bytes_sent) * 8 / dt
        first = self._net_t is None
        self._net, self._net_t = net, now
        try:
            du = psutil.disk_usage(self.disk_path)
            disk = {"path": self.disk_path, "percent": du.percent, "used": du.used, "total": du.total, "free": du.free}
        except OSError:
            disk = None
        temp, temps = self._temps()
        gpu = next((g for g in (p() for p in self.gpu_probes) if g), None)
        try:
            freq = psutil.cpu_freq()
            freq_mhz = freq.current if freq else None
        except Exception:
            freq_mhz = None
        load = os.getloadavg() if hasattr(os, "getloadavg") else None
        return {
            "t_ns": time.time_ns(), "host": self.info, "uptime_s": time.time() - psutil.boot_time(),
            "cpu": {"percent": (sum(per_core) / len(per_core)) if per_core else None, "per_core": per_core,
                    "freq_mhz": freq_mhz, "load_avg": list(load) if load else None},
            "memory": {"percent": vm.percent, "used": vm.used, "total": vm.total},
            "swap": {"percent": sw.percent, "used": sw.used, "total": sw.total},
            "disk": disk, "network": {"rx_bps": rx, "tx_bps": tx},
            "temperature_c": temp, "temperatures": temps, "gpu": gpu,
        }
