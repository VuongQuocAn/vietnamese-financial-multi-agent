"""Bounded Linux Docker execution; no host execution or automatic image pull."""

import hashlib
import json
import os
import re
import subprocess
import threading
from time import monotonic, sleep
from uuid import uuid4


def digest(value):
    encoded = (
        value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False)
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


class PythonExecutor:
    def __init__(self, image=None, *, timeout_seconds=10):
        self.image = image or os.environ.get("PYTHON_WORKER_IMAGE", "")
        self.timeout_seconds = min(max(timeout_seconds, 0.1), 10)

    def _cli(self, args):
        return subprocess.run(["docker", *args], capture_output=True, timeout=10, check=True).stdout

    def preflight(self):
        try:
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.image):
                raise ValueError("immutable_worker_image_required")
            info = json.loads(self._cli(["info", "--format", "{{json .}} "]))
            if info["OSType"] != "linux" or not any(
                "seccomp" in s for s in info.get("SecurityOptions", [])
            ):
                raise ValueError("linux_seccomp_required")
            self._cli(["image", "inspect", self.image])
            probe = self._container(None)
            expected = dict(
                harness="python_worker_v1",
                uid=65534,
                capabilities="0000000000000000",
                seccomp="2",
                interfaces=["lo"],
                memory="268435456",
                swap="0",
                pids="32",
                cpu="100000 100000",
            )
            if probe.get("results") != expected:
                raise ValueError("worker_isolation_probe_failed")
            return dict(status="ready", image=self.image, isolation=expected)
        except (OSError, subprocess.SubprocessError, ValueError, KeyError):
            return dict(status="python_unavailable", reason="worker_preflight_failed")

    def execute(self, code, manifest, outputs, constants):
        ready = self.preflight()
        if ready["status"] != "ready":
            return ready
        request = dict(code=code, operands=manifest, outputs=outputs, constants=constants)
        if len(code.encode()) > 12288 or len(json.dumps(request).encode()) > 262144:
            return dict(status="input_limit")
        result = self._container(request)
        return dict(result, worker=ready)

    def _container(self, request):
        name = "financial-python-" + uuid4().hex
        try:
            result = self._run_container(name, request)
        finally:
            # Removing the container kills its entire process tree, even if CLI hangs.
            try:
                self._cli(["rm", "-f", name])
                cleaned = True
            except (OSError, subprocess.SubprocessError):
                cleaned = False
        if not cleaned:
            return dict(status="python_unavailable", reason="container_cleanup_failed")
        return result

    def _run_container(self, name, request):
        process = None
        try:
            self._cli(
                [
                    "create",
                    "--name",
                    name,
                    "--pull",
                    "never",
                    "--network",
                    "none",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--user",
                    "65534:65534",
                    "--cpus",
                    "1",
                    "--memory",
                    "256m",
                    "--memory-swap",
                    "256m",
                    "--pids-limit",
                    "32",
                    "--log-driver",
                    "none",
                    "--ipc",
                    "none",
                    "-i",
                    self.image,
                    *(["--probe"] if request is None else []),
                ]
            )
            config = json.loads(self._cli(["inspect", name]))[0]
            host = config["HostConfig"]
            if config["Mounts"] or host["NetworkMode"] != "none" or not host["ReadonlyRootfs"]:
                return dict(status="python_unavailable", reason="container_configuration_mismatch")
            process = subprocess.Popen(
                ["docker", "start", "-ai", name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            chunks, size, overflow = [], [0], threading.Event()
            lock = threading.Lock()

            def consume(stream):
                while data := stream.read(1024):
                    with lock:
                        size[0] += len(data)
                        if size[0] > 65536:
                            overflow.set()
                            return
                        chunks.append(data)

            readers = [
                threading.Thread(target=consume, args=(s,), daemon=True)
                for s in (process.stdout, process.stderr)
            ]
            for reader in readers:
                reader.start()
            process.stdin.write(json.dumps(request).encode() if request is not None else b"")
            process.stdin.close()
            deadline = monotonic() + (10 if request is None else self.timeout_seconds)
            while process.poll() is None and not overflow.is_set() and monotonic() < deadline:
                sleep(0.02)
            if process.poll() is None or overflow.is_set():
                return dict(status="output_limit" if overflow.is_set() else "timeout")
            for reader in readers:
                reader.join(timeout=1)
            if overflow.is_set():
                return dict(status="output_limit")
            state = json.loads(self._cli(["inspect", "--format", "{{json .State}}", name]))
            if state.get("OOMKilled"):
                return dict(status="memory_limit")
            if state["ExitCode"] != 0:
                return dict(status="worker_error", exit_code=state["ExitCode"])
            payload = json.loads(b"".join(chunks))
            if request is None:
                return dict(status="success", results=payload)
            if payload.get("status") not in {"success", "code_error"}:
                return dict(status="worker_error")
            return payload
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, BrokenPipeError):
            return dict(status="python_unavailable", reason="worker_execution_failed")
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=2)
                process.stdout.close()
                process.stderr.close()
