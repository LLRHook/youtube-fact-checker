"""Small, versioned ctypes bridge to the required in-process Rust processor."""

import ctypes
from functools import lru_cache
import json
import math
from pathlib import Path
import sys

_LIBRARY_NAME = (
    "factcheck_core.dll" if sys.platform == "win32" else
    "libfactcheck_core.dylib" if sys.platform == "darwin" else
    "libfactcheck_core.so"
)
_LIBRARY_PATH = Path(__file__).resolve().parents[1] / "_native" / _LIBRARY_NAME
_MAX_REQUEST_BYTES = 8 * 1024 * 1024


class NativeInputError(ValueError):
    """The processor rejected input; the message is a stable error code."""


@lru_cache(maxsize=1)
def _load_native():
    try:
        lib = ctypes.CDLL(str(_LIBRARY_PATH))
        lib.factcheck_core_abi_version.argtypes = []
        lib.factcheck_core_abi_version.restype = ctypes.c_uint32
        if lib.factcheck_core_abi_version() != 1:
            raise RuntimeError("Unsupported factcheck-core ABI; rebuild the native library.")
        lib.factcheck_core_process.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        lib.factcheck_core_process.restype = ctypes.c_void_p
        lib.factcheck_core_free.argtypes = [ctypes.c_void_p]
        lib.factcheck_core_free.restype = None
        return lib
    except (OSError, AttributeError) as exc:
        raise RuntimeError(
            "Rust processor unavailable. Run python scripts/build_native.py before starting the backend."
        ) from exc


def ensure_native():
    """Fail at application startup if the required library is missing/incompatible."""
    _load_native()


def wire_value(value):
    """Adapt SDK attributes to JSON without interpreting/normalizing their contents."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return None


def segment_entries(segments):
    """Batch SDK/Python objects into one native call, never one call per caption."""
    return [
        {key: wire_value(getattr(segment, key, None)) for key in ("text", "start", "duration")}
        for segment in segments
    ]


def process(op: str, **payload):
    lib = _load_native()
    data = json.dumps({"op": op, **payload}, ensure_ascii=True, allow_nan=False).encode("utf-8")
    if len(data) > _MAX_REQUEST_BYTES:
        raise NativeInputError("invalid_request")
    pointer = lib.factcheck_core_process(data, len(data))
    if not pointer:
        raise RuntimeError("Rust processor returned no response.")
    try:
        response = json.loads(ctypes.string_at(pointer))
    finally:
        lib.factcheck_core_free(pointer)
    if "error" in response:
        raise NativeInputError(response["error"])
    return response["result"]
