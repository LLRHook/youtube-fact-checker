"""Shared utility for parsing JSON from untrusted LLM responses in Rust."""

from backend.utils.native_core import NativeInputError, process


def parse_llm_json(text: str):
    """Strip fences, parse JSON, then try outermost fragments; return None on failure."""
    try:
        return process("parse_llm_json", text=text if isinstance(text, str) else None)
    except NativeInputError:
        return None
