"""LiveSource transport: request/response + events to the rclpy agent over a loopback WebSocket, with reconnect."""
from __future__ import annotations
import asyncio, itertools, json, logging
from typing import Awaitable, Callable

import websockets

log = logging.getLogger("agent-client")


class AgentUnavailable(Exception):
    pass


class AgentError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class AgentClient:
    def __init__(self, url: str, token: str | None, on_event: Callable[[dict], Awaitable[None]],
                 on_state: Callable[[str], Awaitable[None]]):
        self.url = url + (("?token=" + token) if token else "")
        self.public_url = url
        self.on_event, self.on_state = on_event, on_state
        self.state = "disconnected"
        self.info: dict | None = None
        self.last_error: str | None = None
        self._ws = None
        self._pending: dict[int, asyncio.Future] = {}
        self._ids = itertools.count(1)
        self._task: asyncio.Task | None = None

    async def start(self):
        if not self._task:
            self._task = asyncio.create_task(self._run())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._set("disconnected")

    async def _set(self, state: str):
        if state != self.state:
            self.state = state
            if state != "connected":
                self.info = None
            await self.on_state(state)

    async def _run(self):
        backoff = 0.5
        while True:
            reader = None
            try:
                await self._set("connecting")
                async with websockets.connect(self.url, max_size=8 << 20, open_timeout=3) as ws:
                    self._ws = ws
                    reader = asyncio.create_task(self._read(ws))
                    self.info = await self._request("hello", {}, 5.0)
                    self.last_error = None
                    backoff = 0.5
                    await self._set("connected")
                    await reader
                    self.last_error = "Connection to agent closed"
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"
            finally:
                if reader:
                    reader.cancel()
                self._ws = None
                for f in self._pending.values():
                    if not f.done():
                        f.set_exception(AgentUnavailable("Agent disconnected"))
                self._pending.clear()
            await self._set("disconnected")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 5.0)

    async def _read(self, ws):
        async for raw in ws:
            msg = json.loads(raw)
            if "id" in msg:
                f = self._pending.pop(msg["id"], None)
                if f and not f.done():
                    if msg.get("ok"):
                        f.set_result(msg.get("result"))
                    else:
                        e = msg.get("error") or {}
                        f.set_exception(AgentError(e.get("code", "error"), e.get("message", "Agent error")))
            elif "ch" in msg:
                try:
                    await self.on_event(msg)
                except Exception:
                    log.exception("event handler failed")

    async def _request(self, op: str, args: dict, timeout: float):
        if self._ws is None:
            raise AgentUnavailable("Agent is not connected")
        rid = next(self._ids)
        fut = asyncio.get_running_loop().create_future()
        self._pending[rid] = fut
        try:
            await self._ws.send(json.dumps({"id": rid, "op": op, "args": args}))
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            raise AgentUnavailable(f"Agent did not answer {op} within {timeout}s")
        except websockets.exceptions.ConnectionClosed:
            raise AgentUnavailable("Agent disconnected")
        finally:
            self._pending.pop(rid, None)

    async def request(self, op: str, args: dict | None = None, timeout: float = 8.0):
        if self.state != "connected":
            raise AgentUnavailable("Agent is not connected")
        return await self._request(op, args or {}, timeout)
