"""Shared utility for parsing JSON from LLM responses."""

import json


def parse_llm_json(text: str) -> dict | list | None:
    """Strip markdown fences and parse JSON from an LLM response.

    Returns the parsed object, or None if parsing fails entirely.
    """
    text = text.strip()

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    if text.startswith("```"):
        # Remove opening fence line
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: extract the outermost JSON structure, preferring whichever starts first
    candidates = []
    for open_ch, close_ch in [("{", "}"), ("[", "]")]:
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end > start:
            candidates.append((start, text[start : end + 1]))

    candidates.sort(key=lambda c: c[0])
    for _, fragment in candidates:
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            continue

    return None
