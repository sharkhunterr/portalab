"""Kernel confinement of a plugin process (spec 030, research R2) — unprivileged, irreversible, no library.

A confined plugin's process calls :func:`confine` before it imports any plugin code. Afterwards it cannot
open a socket (only ``socketpair``, which asyncio needs), connect or bind over TCP, read or write any file
outside the folders it was given, run a program, start a process, trace or signal another process, mount,
change namespaces, load kernel code or use io_uring. Memory, file size and open files are bounded.

Landlock (ABI 4 or later: files and TCP) and seccomp are reached through ``ctypes`` syscalls; :func:`probe`
says what the running kernel offers, so Portalab can hold confined plugins (or run them in the weaker mode
the Admin accepted) where it cannot confine.
"""

import ctypes
import errno
import os
import platform
import resource
import struct
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

MIN_LANDLOCK_ABI = 4  # files + TCP bind/connect

# --- Landlock ------------------------------------------------------------------------------------------
_LANDLOCK_CREATE_RULESET_VERSION = 1
_LANDLOCK_RULE_PATH_BENEATH = 1

_FS_EXECUTE = 1 << 0
_FS_WRITE_FILE = 1 << 1
_FS_READ_FILE = 1 << 2
_FS_READ_DIR = 1 << 3
_FS_REMOVE_DIR = 1 << 4
_FS_REMOVE_FILE = 1 << 5
_FS_MAKE_CHAR = 1 << 6
_FS_MAKE_DIR = 1 << 7
_FS_MAKE_REG = 1 << 8
_FS_MAKE_SOCK = 1 << 9
_FS_MAKE_FIFO = 1 << 10
_FS_MAKE_BLOCK = 1 << 11
_FS_MAKE_SYM = 1 << 12
_FS_REFER = 1 << 13  # ABI 2
_FS_TRUNCATE = 1 << 14  # ABI 3
_FS_IOCTL_DEV = 1 << 15  # ABI 5
_NET_BIND_TCP = 1 << 0  # ABI 4
_NET_CONNECT_TCP = 1 << 1
_SCOPE_ABSTRACT_UNIX = 1 << 0  # ABI 6
_SCOPE_SIGNAL = 1 << 1

_FILE_RIGHTS = _FS_EXECUTE | _FS_WRITE_FILE | _FS_READ_FILE | _FS_TRUNCATE | _FS_IOCTL_DEV
_READ = _FS_READ_FILE | _FS_READ_DIR
_READ_EXEC = _READ | _FS_EXECUTE
_SCRATCH = (
    _READ
    | _FS_WRITE_FILE
    | _FS_REMOVE_DIR
    | _FS_REMOVE_FILE
    | _FS_MAKE_DIR
    | _FS_MAKE_REG
    | _FS_TRUNCATE
    | _FS_REFER
)

# --- seccomp -------------------------------------------------------------------------------------------
_SECCOMP_SET_MODE_FILTER = 1
_SECCOMP_FILTER_FLAG_TSYNC = 1
_RET_KILL_PROCESS = 0x80000000
_RET_ERRNO = 0x00050000
_RET_ALLOW = 0x7FFF0000
_LD_W_ABS = 0x20
_JEQ_K = 0x15
_JGE_K = 0x35
_JSET_K = 0x45
_RET_K = 0x06
_CLONE_THREAD = 0x00010000
_X32_BIT = 0x40000000
_PR_SET_NO_NEW_PRIVS = 38
_PR_GET_SECCOMP = 21


@dataclass(frozen=True)
class _Arch:
    audit: int
    numbers: dict[str, int]
    seccomp: int
    landlock: tuple[int, int, int] = (444, 445, 446)
    x32: bool = False


# Only what the filter names; anything else is allowed (and Landlock bounds files and TCP).
_X86_64 = _Arch(
    audit=0xC000003E,
    seccomp=317,
    x32=True,
    numbers={
        "socket": 41, "clone": 56, "fork": 57, "vfork": 58, "execve": 59, "kill": 62, "ptrace": 101,
        "tkill": 200, "tgkill": 234, "mount": 165, "umount2": 166, "pivot_root": 155, "chroot": 161,
        "setns": 308, "unshare": 272, "bpf": 321, "perf_event_open": 298, "keyctl": 250, "add_key": 248,
        "request_key": 249, "userfaultfd": 323, "io_uring_setup": 425, "io_uring_enter": 426,
        "io_uring_register": 427, "clone3": 435, "execveat": 322, "process_vm_readv": 310,
        "process_vm_writev": 311, "pidfd_open": 434, "pidfd_send_signal": 424, "pidfd_getfd": 438,
        "init_module": 175, "finit_module": 313, "delete_module": 176, "kexec_load": 246,
        "kexec_file_load": 320, "open_by_handle_at": 304, "rt_sigqueueinfo": 129, "rt_tgsigqueueinfo": 297,
        "mount_setattr": 442, "open_tree": 428, "move_mount": 429, "fsopen": 430, "fsconfig": 431,
        "fsmount": 432, "fspick": 433, "quotactl": 179, "swapon": 167, "swapoff": 168, "reboot": 169,
        "acct": 163, "settimeofday": 164, "personality": 135, "modify_ldt": 154, "iopl": 172, "ioperm": 173,
    },
)  # fmt: skip
_AARCH64 = _Arch(
    audit=0xC00000B7,
    seccomp=277,
    numbers={
        "socket": 198, "clone": 220, "execve": 221, "kill": 129, "ptrace": 117, "tkill": 130, "tgkill": 131,
        "mount": 40, "umount2": 39, "pivot_root": 41, "chroot": 51, "setns": 268, "unshare": 97, "bpf": 280,
        "perf_event_open": 241, "keyctl": 219, "add_key": 217, "request_key": 218, "userfaultfd": 282,
        "io_uring_setup": 425, "io_uring_enter": 426, "io_uring_register": 427, "clone3": 435,
        "execveat": 281, "process_vm_readv": 270, "process_vm_writev": 271, "pidfd_open": 434,
        "pidfd_send_signal": 424, "pidfd_getfd": 438, "init_module": 105, "finit_module": 273,
        "delete_module": 106, "kexec_load": 104, "kexec_file_load": 294, "open_by_handle_at": 265,
        "rt_sigqueueinfo": 138, "rt_tgsigqueueinfo": 240, "mount_setattr": 442, "open_tree": 428,
        "move_mount": 429, "fsopen": 430, "fsconfig": 431, "fsmount": 432, "fspick": 433, "quotactl": 60,
        "swapon": 224, "swapoff": 225, "reboot": 142, "acct": 89, "settimeofday": 170, "personality": 92,
    },
)  # fmt: skip
_ARCHES = {"x86_64": _X86_64, "amd64": _X86_64, "aarch64": _AARCH64, "arm64": _AARCH64}

# Refused outright (EPERM); kill/tgkill only toward itself, clone only for threads, clone3 says ENOSYS so
# the C library falls back to clone (whose flags the filter can read).
DENIED = (
    "socket", "fork", "vfork", "execve", "execveat", "ptrace", "tkill", "mount", "umount2", "pivot_root",
    "chroot", "setns", "unshare", "bpf", "perf_event_open", "keyctl", "add_key", "request_key",
    "userfaultfd", "io_uring_setup", "io_uring_enter", "io_uring_register", "process_vm_readv",
    "process_vm_writev", "pidfd_open", "pidfd_send_signal", "pidfd_getfd", "init_module", "finit_module",
    "delete_module", "kexec_load", "kexec_file_load", "open_by_handle_at", "rt_sigqueueinfo",
    "rt_tgsigqueueinfo", "mount_setattr", "open_tree", "move_mount", "fsopen", "fsconfig", "fsmount",
    "fspick", "quotactl", "swapon", "swapoff", "reboot", "acct", "settimeofday", "personality",
    "modify_ldt", "iopl", "ioperm",
)  # fmt: skip


class ConfinementError(RuntimeError):
    """The kernel refused a step of the confinement (the process must not go on)."""


@dataclass(frozen=True)
class Support:
    """What this kernel offers to confine a process."""

    landlock_abi: int
    seccomp: bool
    arch: str

    @property
    def ok(self) -> bool:
        return self.landlock_abi >= MIN_LANDLOCK_ABI and self.seccomp

    def as_dict(self) -> dict[str, object]:
        return {"landlock_abi": self.landlock_abi, "seccomp": self.seccomp, "arch": self.arch, "ok": self.ok}


@dataclass
class Applied:
    """What :func:`confine` did (reported by the plugin process; Portalab refuses less than required)."""

    landlock_abi: int = 0
    seccomp: bool = False
    rlimits: dict[str, int] = field(default_factory=dict)
    scoped: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "landlock_abi": self.landlock_abi,
            "seccomp": self.seccomp,
            "rlimits": dict(self.rlimits),
            "scoped": self.scoped,
        }


def _libc() -> ctypes.CDLL:
    return ctypes.CDLL(None, use_errno=True)


def _arch() -> _Arch | None:
    return _ARCHES.get(platform.machine().lower())


def landlock_abi() -> int:
    arch = _arch()
    if arch is None or platform.system() != "Linux":
        return 0
    libc = _libc()
    libc.syscall.restype = ctypes.c_long
    value = libc.syscall(arch.landlock[0], None, ctypes.c_size_t(0), ctypes.c_uint32(1))
    return int(value) if value > 0 else 0


def probe() -> Support:
    """What the running kernel offers (Landlock ABI, seccomp filters), without changing anything."""
    arch = _arch()
    seccomp = False
    if arch is not None and platform.system() == "Linux":
        seccomp = _libc().prctl(_PR_GET_SECCOMP, 0, 0, 0, 0) >= 0  # kernel built with seccomp
    return Support(landlock_abi=landlock_abi(), seccomp=seccomp, arch=platform.machine())


# --- seccomp program -----------------------------------------------------------------------------------
def _insn(code: int, jt: int, jf: int, k: int) -> bytes:
    return struct.pack("HBBI", code, jt, jf, k & 0xFFFFFFFF)


def seccomp_program(arch_name: str, own_pid: int) -> list[tuple[int, int, int, int]]:
    """The filter as ``(code, jt, jf, k)`` instructions (exposed for tests)."""
    arch = _ARCHES[arch_name]
    n = arch.numbers
    eperm = _RET_ERRNO | errno.EPERM
    out: list[tuple[int, int, int, int]] = [
        (_LD_W_ABS, 0, 0, 4),  # seccomp_data.arch
        (_JEQ_K, 1, 0, arch.audit),
        (_RET_K, 0, 0, _RET_KILL_PROCESS),
        (_LD_W_ABS, 0, 0, 0),  # seccomp_data.nr
    ]
    if arch.x32:
        out += [(_JGE_K, 0, 1, _X32_BIT), (_RET_K, 0, 0, eperm)]
    for name in DENIED:
        if name in n:
            out += [(_JEQ_K, 0, 1, n[name]), (_RET_K, 0, 0, eperm)]
    out += [(_JEQ_K, 0, 1, n["clone3"]), (_RET_K, 0, 0, _RET_ERRNO | errno.ENOSYS)]
    # clone: threads only (flags in args[0], low word at offset 16)
    out += [
        (_JEQ_K, 0, 4, n["clone"]),
        (_LD_W_ABS, 0, 0, 16),
        (_JSET_K, 0, 1, _CLONE_THREAD),
        (_RET_K, 0, 0, _RET_ALLOW),
        (_RET_K, 0, 0, eperm),
    ]
    # kill(pid, …) and tgkill(tgid, …): toward this process only
    for name in ("kill", "tgkill"):
        out += [
            (_JEQ_K, 0, 4, n[name]),
            (_LD_W_ABS, 0, 0, 16),
            (_JEQ_K, 0, 1, own_pid),
            (_RET_K, 0, 0, _RET_ALLOW),
            (_RET_K, 0, 0, eperm),
        ]
        out.append((_LD_W_ABS, 0, 0, 0))  # reload nr for the next comparison (skipped-to on a miss)
    out.append((_RET_K, 0, 0, _RET_ALLOW))
    return out


def _install_seccomp(arch: _Arch, arch_name: str) -> None:
    program = seccomp_program(arch_name, os.getpid())
    raw = b"".join(_insn(*i) for i in program)
    buffer = ctypes.create_string_buffer(raw, len(raw))

    class SockFprog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]

    prog = SockFprog(len(program), ctypes.cast(buffer, ctypes.c_void_p))
    libc = _libc()
    libc.syscall.restype = ctypes.c_long
    result = libc.syscall(
        arch.seccomp, _SECCOMP_SET_MODE_FILTER, _SECCOMP_FILTER_FLAG_TSYNC, ctypes.byref(prog)
    )
    if result != 0:
        raise ConfinementError(f"seccomp refused: {os.strerror(ctypes.get_errno())}")


# --- Landlock ruleset ----------------------------------------------------------------------------------
def _handled_fs(abi: int) -> int:
    rights = (1 << 13) - 1  # ABI 1: bits 0..12
    if abi >= 2:
        rights |= _FS_REFER
    if abi >= 3:
        rights |= _FS_TRUNCATE
    if abi >= 5:
        rights |= _FS_IOCTL_DEV
    return rights


def _install_landlock(arch: _Arch, abi: int, rules: Iterable[tuple[Path, int]]) -> bool:
    libc = _libc()
    libc.syscall.restype = ctypes.c_long
    handled = _handled_fs(abi)
    scoped = abi >= 6
    attr = struct.pack(
        "QQQ",
        handled,
        _NET_BIND_TCP | _NET_CONNECT_TCP,
        (_SCOPE_ABSTRACT_UNIX | _SCOPE_SIGNAL) if scoped else 0,
    )
    size = 24 if scoped else 16
    attr_buf = ctypes.create_string_buffer(attr[:size], size)
    ruleset = libc.syscall(arch.landlock[0], attr_buf, ctypes.c_size_t(size), ctypes.c_uint32(0))
    if ruleset < 0:
        raise ConfinementError(f"landlock ruleset refused: {os.strerror(ctypes.get_errno())}")
    try:
        for path, rights in rules:
            try:
                fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            except OSError:
                continue  # an optional folder that does not exist here
            try:
                allowed = rights & handled
                if not path.is_dir():
                    allowed &= _FILE_RIGHTS
                rule = struct.pack("=Qi", allowed, fd)
                buf = ctypes.create_string_buffer(rule, len(rule))
                if libc.syscall(arch.landlock[1], ruleset, _LANDLOCK_RULE_PATH_BENEATH, buf, 0) != 0:
                    raise ConfinementError(
                        f"landlock rule refused for {path}: {os.strerror(ctypes.get_errno())}"
                    )
            finally:
                os.close(fd)
        # no TCP rule at all: every bind and connect is denied
        if libc.syscall(arch.landlock[2], ruleset, 0) != 0:
            raise ConfinementError(f"landlock restrict refused: {os.strerror(ctypes.get_errno())}")
    finally:
        os.close(ruleset)
    return scoped


# --- the whole -----------------------------------------------------------------------------------------
def default_read_paths() -> list[Path]:
    """Python, its standard library and installed packages, the shared libraries (nothing of the portal's
    data, secrets or configuration lives there)."""
    import sys

    paths = {Path(sys.prefix), Path(sys.base_prefix) / "lib", Path(sys.exec_prefix)}
    for entry in sys.path:
        if entry and Path(entry).exists():
            paths.add(Path(entry))
    for system in ("/usr/lib", "/lib", "/lib64", "/usr/lib64", "/usr/local/lib"):
        paths.add(Path(system))
    paths.add(Path(sys.executable).resolve().parent)
    return sorted(paths)


def confine(
    *,
    read: Iterable[Path],
    scratch: Path,
    memory_mb: int = 384,
    weak: bool = False,
) -> Applied:
    """Confine this process for good: rlimits, no new privileges, Landlock, seccomp.

    ``read``: folders and files readable (and executable: Python's own); ``scratch``: the only folder it may
    write. With ``weak`` (the Admin accepted the weaker mode), what the kernel lacks is skipped instead of
    refused.
    """
    applied = Applied()
    limits = {
        "RLIMIT_AS": memory_mb * 1024 * 1024,
        "RLIMIT_FSIZE": 16 * 1024 * 1024,
        "RLIMIT_NOFILE": 64,
        "RLIMIT_CORE": 0,
    }
    for name, value in limits.items():
        which = getattr(resource, name)
        _soft, hard = resource.getrlimit(which)
        target = value if hard == resource.RLIM_INFINITY else min(value, hard)
        resource.setrlimit(which, (target, target))
        applied.rlimits[name] = target
    libc = _libc()
    if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise ConfinementError("no_new_privs refused")
    arch = _arch()
    if arch is None:
        if weak:
            return applied
        raise ConfinementError(f"unsupported architecture {platform.machine()}")
    abi = landlock_abi()
    if abi >= MIN_LANDLOCK_ABI:
        rules = [(Path(p), _READ_EXEC) for p in read]
        rules += [(scratch, _SCRATCH), (Path("/dev/null"), _FS_READ_FILE | _FS_WRITE_FILE)]
        rules += [(Path("/dev/urandom"), _FS_READ_FILE), (Path("/etc/ld.so.cache"), _FS_READ_FILE)]
        applied.scoped = _install_landlock(arch, abi, rules)
        applied.landlock_abi = abi
    elif not weak:
        raise ConfinementError(f"landlock ABI {abi} < {MIN_LANDLOCK_ABI}")
    try:
        _install_seccomp(arch, platform.machine().lower())
        applied.seccomp = True
    except ConfinementError:
        if not weak:
            raise
    return applied
