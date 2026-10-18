"""030 T004 — kernel confinement (R2): the seccomp program's shape, and a real confined process that can no
longer reach the network, the portal's files, other processes or programs (Linux with Landlock ABI ≥ 4)."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from portalab.core import confinement
from portalab.core.confinement import DENIED, probe, seccomp_program

SUPPORT = probe()
needs_kernel = pytest.mark.skipif(not SUPPORT.ok, reason="kernel without Landlock ABI ≥ 4 or seccomp")


@pytest.mark.parametrize("arch", ["x86_64", "aarch64"])
def test_program_checks_the_architecture_first_and_allows_last(arch: str) -> None:
    program = seccomp_program(arch, 4242)
    assert program[0] == (0x20, 0, 0, 4)
    assert program[2] == (0x06, 0, 0, 0x80000000)  # another architecture: killed
    assert program[-1] == (0x06, 0, 0, 0x7FFF0000)
    numbers = confinement._ARCHES[arch].numbers
    compared = {k for code, _jt, _jf, k in program if code == 0x15}
    for name in DENIED:
        if name in numbers:
            assert numbers[name] in compared, name
    assert 4242 in compared  # kill / tgkill toward itself only


@pytest.mark.parametrize("arch", ["x86_64", "aarch64"])
def test_program_jumps_stay_inside(arch: str) -> None:
    program = seccomp_program(arch, 1)
    for index, (code, jt, jf, _k) in enumerate(program):
        if code in (0x15, 0x35, 0x45):
            assert index + 1 + max(jt, jf) < len(program)


PROBE = textwrap.dedent(
    """
    import json, os, signal, socket, sys
    from pathlib import Path
    from portalab.core.confinement import confine, default_read_paths
    scratch, secret, other = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    parent = int(sys.argv[4])
    applied = confine(read=default_read_paths(), scratch=scratch, memory_mb=256)
    out = {"applied": applied.as_dict()}
    def attempt(name, fn):
        try:
            fn()
            out[name] = "done"
        except BaseException as error:
            out[name] = type(error).__name__
    attempt("socket", lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM))
    attempt("unix_socket", lambda: socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
    attempt("socketpair", lambda: socket.socketpair())
    attempt("read_secret", lambda: secret.read_text())
    attempt("read_other", lambda: (other / "x").read_text())
    attempt("proc_environ", lambda: Path(f"/proc/{parent}/environ").read_bytes())
    attempt("etc_passwd", lambda: Path("/etc/passwd").read_text())
    attempt("write_scratch", lambda: (scratch / "ok.txt").write_text("ok"))
    attempt("write_code", lambda: Path(__import__("portalab").__file__).with_name("x.py").write_text("x"))
    attempt("fork", lambda: os.fork() == 0 and os._exit(0))
    attempt("exec", lambda: os.execv("/bin/true", ["true"]))
    attempt("signal_parent", lambda: os.kill(parent, 0))
    attempt("signal_self", lambda: os.kill(os.getpid(), 0))
    attempt("memory", lambda: bytearray(512 * 1024 * 1024))
    import threading
    t = threading.Thread(target=lambda: None); attempt("thread", t.start); t.join()
    import asyncio
    attempt("asyncio", lambda: asyncio.run(asyncio.sleep(0)))
    print(json.dumps(out))
    """
)


@needs_kernel
def test_a_confined_process_reaches_nothing(tmp_path: Path) -> None:
    scratch, other = tmp_path / "scratch", tmp_path / "other"
    scratch.mkdir()
    other.mkdir()
    (other / "x").write_text("another plugin's file")
    secret = tmp_path / "secret_key"
    secret.write_text("not for plugins")
    run = subprocess.run(  # noqa: S603 — this test's own interpreter and script
        [
            sys.executable,
            "-I",
            "-c",
            PROBE,
            str(scratch),
            str(secret),
            str(other),
            str(__import__("os").getpid()),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env={"PYTHONPATH": ":".join(p for p in sys.path if p), "MALLOC_ARENA_MAX": "2"},
    )
    assert run.returncode == 0, run.stderr[-2000:]
    out = json.loads(run.stdout.strip().splitlines()[-1])
    assert out["applied"]["seccomp"] is True and out["applied"]["landlock_abi"] >= 4
    refused = ["socket", "unix_socket", "read_secret", "read_other", "proc_environ", "etc_passwd",
               "write_code", "fork", "exec", "signal_parent", "memory"]  # fmt: skip
    for name in refused:
        assert out[name] != "done", (name, out)
    for name in ("socketpair", "write_scratch", "signal_self", "thread", "asyncio"):
        assert out[name] == "done", (name, out)
