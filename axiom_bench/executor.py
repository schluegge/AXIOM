from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Mapping, Sequence


@dataclass(frozen=True)
class ExecutionResult:
    argv: tuple[str, ...]
    cwd: str
    environment: dict[str, str]
    started_at: str
    finished_at: str
    duration_ms: int
    return_code: int | None
    timed_out: bool
    output_limited: bool
    termination: str
    stdout: bytes
    stderr: bytes


class _BoundedCapture:
    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError("output limit must be positive")
        self.limit = limit
        self.remaining = limit
        self.buffers: dict[str, bytearray] = {
            "stdout": bytearray(),
            "stderr": bytearray(),
        }
        self.lock = threading.Lock()
        self.overflow = threading.Event()

    def read_stream(self, name: str, stream: BinaryIO) -> None:
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                with self.lock:
                    keep = min(self.remaining, len(chunk))
                    if keep:
                        self.buffers[name].extend(chunk[:keep])
                        self.remaining -= keep
                    if keep < len(chunk):
                        self.overflow.set()
                # Continue draining while the parent terminates the trusted child.
        finally:
            stream.close()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def minimal_environment(workspace: Path, inherited: Mapping[str, str] | None = None) -> dict[str, str]:
    source = os.environ if inherited is None else inherited
    environment: dict[str, str] = {}
    for key in ("PATH", "SYSTEMROOT", "WINDIR", "PATHEXT", "COMSPEC"):
        value = source.get(key)
        if value:
            environment[key] = value

    temporary = workspace / ".tmp"
    home = workspace / ".home"
    temporary.mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True, exist_ok=True)
    environment.update(
        {
            "HOME": str(home),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONHASHSEED": "0",
            "TEMP": str(temporary),
            "TMP": str(temporary),
            "TMPDIR": str(temporary),
            "TZ": "UTC",
        }
    )
    return dict(sorted(environment.items()))


def _terminate(process: subprocess.Popen[bytes], grace_seconds: float = 0.5) -> str:
    if process.poll() is not None:
        return "natural"

    termination = "terminate"
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        return "natural"
    except OSError:
        process.terminate()

    try:
        process.wait(timeout=grace_seconds)
        return termination
    except subprocess.TimeoutExpired:
        termination = "kill"

    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass
    except OSError:
        process.kill()
    process.wait()
    return termination


def execute_bounded(
    argv: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    timeout_seconds: int,
    max_output_bytes: int,
) -> ExecutionResult:
    if not argv or any(not isinstance(item, str) for item in argv):
        raise ValueError("argv must be a non-empty string sequence")
    if timeout_seconds < 1:
        raise ValueError("timeout must be positive")

    started_text = _utc_now()
    started = time.monotonic()
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    process = subprocess.Popen(
        list(argv),
        cwd=cwd,
        env=dict(environment),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        start_new_session=(os.name == "posix"),
        creationflags=creationflags,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    capture = _BoundedCapture(max_output_bytes)
    threads = [
        threading.Thread(
            target=capture.read_stream,
            args=("stdout", process.stdout),
            name="axiom-bench-stdout",
            daemon=True,
        ),
        threading.Thread(
            target=capture.read_stream,
            args=("stderr", process.stderr),
            name="axiom-bench-stderr",
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()

    deadline = started + timeout_seconds
    timed_out = False
    output_limited = False
    termination = "natural"
    while process.poll() is None:
        if capture.overflow.is_set():
            output_limited = True
            termination = _terminate(process)
            break
        if time.monotonic() >= deadline:
            timed_out = True
            termination = _terminate(process)
            break
        time.sleep(0.01)

    if process.poll() is None:
        process.wait()
    for thread in threads:
        thread.join(timeout=2.0)
    if any(thread.is_alive() for thread in threads):
        termination = _terminate(process)
        for thread in threads:
            thread.join(timeout=1.0)

    finished = time.monotonic()
    return ExecutionResult(
        argv=tuple(argv),
        cwd=str(cwd),
        environment=dict(sorted(environment.items())),
        started_at=started_text,
        finished_at=_utc_now(),
        duration_ms=max(0, int(round((finished - started) * 1000))),
        return_code=process.returncode,
        timed_out=timed_out,
        output_limited=output_limited or capture.overflow.is_set(),
        termination=termination,
        stdout=bytes(capture.buffers["stdout"]),
        stderr=bytes(capture.buffers["stderr"]),
    )
