import json, time
import httpx, pytest
from websockets.sync.client import connect
from .fakes import AgentThread, BackendThread, FakeRos


class Stack:
    def __init__(self, with_agent=True):
        self.ros = FakeRos()
        self.agent = AgentThread(self.ros).start() if with_agent else None
        self.port = self.agent.port if with_agent else __import__("tests.fakes", fromlist=["free_port"]).free_port()
        self.backend = BackendThread(f"ws://127.0.0.1:{self.port}")
        self.http = httpx.Client(base_url=self.backend.url, headers={"Authorization": "Bearer tok"}, timeout=5)

    def wait_agent(self, state="connected", timeout=6):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.http.get("/api/live/status").json()["agent"]["state"] == state: return
            time.sleep(0.1)
        raise AssertionError(f"agent never reached {state}: {self.http.get('/api/live/status').json()}")

    def ws(self):
        return Browser(connect(self.backend.ws_url))

    def close(self):
        self.http.close(); self.backend.stop()
        if self.agent and self.agent.thread.is_alive(): self.agent.stop()


class Browser:
    def __init__(self, ws): self.ws = ws; self.seen = []
    def send(self, **m): self.ws.send(json.dumps(m))
    def wait(self, pred, timeout=4):
        end = time.time() + timeout
        while time.time() < end:
            try: ev = json.loads(self.ws.recv(timeout=max(0.05, end - time.time())))
            except TimeoutError: break
            self.seen.append(ev)
            if pred(ev): return ev
        raise AssertionError(f"timed out; saw {[e.get('ch') for e in self.seen][-10:]}")
    def drain(self, secs):
        end = time.time() + secs; out = []
        while time.time() < end:
            try: out.append(json.loads(self.ws.recv(timeout=0.05)))
            except TimeoutError: pass
        return out
    def close(self): self.ws.close()


@pytest.fixture
def stack():
    s = Stack(); s.wait_agent(); yield s; s.close()

@pytest.fixture
def stack_no_agent():
    s = Stack(with_agent=False); yield s; s.close()
