"""Optional background serial I/O (stub sends AT; real pyserial optional)."""
from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from app.runtime_state import AppRuntime


def classify_modem_line(text: str) -> str:
    """Return log prefix: 'ERR' for failures, 'URC' for leading + unsolicited, else 'RX'."""
    t = text.strip()
    if not t:
        return "RX"
    up = t.upper()
    if up == "ERROR" or up == "FAIL":
        return "ERR"
    if "CME ERROR" in up or "CMS ERROR" in up:
        return "ERR"
    if "NO CARRIER" in up or "OPERATION NOT ALLOWED" in up:
        return "ERR"
    if re.match(r"^\+CM[ES]\s+ERROR", up):
        return "ERR"
    # Unsolicited result codes often start with + (but not +CME ERROR handled above)
    if t.startswith("+") and not t.upper().startswith("+CME ERROR") and not t.upper().startswith("+CMS ERROR"):
        return "URC"
    return "RX"


class SerialWorker:
    def __init__(
        self,
        runtime: AppRuntime,
        port: str,
        baud: int,
        mock: bool,
        on_line: Callable[[str], None] | None = None,
    ) -> None:
        self.runtime = runtime
        self.port = port
        self.baud = baud
        self.mock = mock
        self.on_line = on_line
        self._out_q: asyncio.Queue[str] = asyncio.Queue()
        self.ser = None

    async def start(self) -> None:
        if not self.mock:
            try:
                import serial

                self.ser = serial.Serial(self.port, self.baud, timeout=0.05)
            except Exception as e:
                async with self.runtime.lock:
                    self.runtime.at_log.append(f"[serial] open failed: {e!r}, using echo-only")
                self.ser = None

    async def reopen(self, port: str, baud: int, mock: bool) -> None:
        """Close the current port (if any) and open with new parameters. Used for live COM changes."""
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        self.port = port.strip() if port else self.port
        self.baud = int(baud)
        self.mock = bool(mock)
        await self.start()

    def _read_line_blocking(self) -> bytes:
        if not self.ser:
            return b""
        try:
            return self.ser.readline()
        except Exception:
            return b""

    async def reader_loop(self) -> None:
        """Read modem lines (OK, ERROR, +CME ERROR, URCs) into at_log."""
        loop = asyncio.get_event_loop()
        while True:
            if self.mock or self.ser is None:
                await asyncio.sleep(0.4)
                continue
            try:
                raw = await loop.run_in_executor(None, self._read_line_blocking)
            except Exception as e:
                async with self.runtime.lock:
                    self.runtime.at_log.append(f"[serial read] {e!r}")
                await asyncio.sleep(0.2)
                continue
            if not raw:
                await asyncio.sleep(0.01)
                continue
            text = raw.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            kind = classify_modem_line(text)
            if kind == "ERR":
                line = f"< ERR {text}"
            elif kind == "URC":
                line = f"< URC {text}"
            else:
                line = f"< {text}"
            async with self.runtime.lock:
                self.runtime.at_log.append(line)
                self.runtime.serial_rx_log.append(text)
                self.runtime.process_modem_measurement_line(text, kind)
            if self.on_line:
                self.on_line(text)

    async def writer_loop(self) -> None:
        while True:
            line = await self._out_q.get()
            if self.mock or self.ser is None:
                if self.mock:
                    # Intentional mock mode: echo fake OK so the UI sees responses.
                    async with self.runtime.lock:
                        self.runtime.at_log.append("< OK (mock)")
                        self.runtime.serial_rx_log.append("OK (mock)")
                    if self.on_line:
                        self.on_line("OK")
                # Serial failed to open: silently discard — scan loop backs off so this
                # queue should be empty in normal operation.
                continue
            loop = asyncio.get_event_loop()
            try:

                def _w() -> None:
                    self.ser.write(line.encode("utf-8", errors="replace"))
                    self.ser.flush()

                await loop.run_in_executor(None, _w)
                async with self.runtime.lock:
                    self.runtime.at_log.append(f"> sent {len(line)} B: {line!r}")
            except Exception as e:
                async with self.runtime.lock:
                    self.runtime.at_log.append(f"[serial write] {e!r}")

    def enqueue(self, cmd: str) -> None:
        self._out_q.put_nowait(cmd if cmd.endswith("\n") else cmd + "\r\n")
