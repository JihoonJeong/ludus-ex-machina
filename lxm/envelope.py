"""Envelope parsing and validation for LxM protocol."""

import json
import re
from pathlib import Path


def parse_from_file(filepath: str, protocol: str = "lxm-v0.2", match_id: str = "", agent_id: str = "", turn: int = 0) -> dict | None:
    """Read and parse a JSON file as an envelope.

    Handles two formats:
    1. New format: Complete JSON envelope with "protocol" field
    2. Old format: First line is protocol version, rest is JSON move object

    For old format, the envelope fields must be provided as parameters.
    """
    path = Path(filepath)
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")

        # Try parsing as complete JSON envelope (new format)
        try:
            obj = json.loads(content)
            if isinstance(obj, dict) and "protocol" in obj:
                return obj
        except json.JSONDecodeError:
            pass

        # Try old format: protocol on first line, JSON on remaining lines
        lines = content.strip().split('\n', 1)
        if len(lines) == 2:
            protocol_line = lines[0].strip()
            json_part = lines[1]

            # Check if first line looks like a protocol version
            if protocol_line.startswith('lxm-'):
                try:
                    move_obj = json.loads(json_part)
                    if isinstance(move_obj, dict):
                        # Wrap old format move in complete envelope
                        return {
                            "protocol": protocol,
                            "match_id": match_id,
                            "agent_id": agent_id,
                            "turn": turn,
                            "move": move_obj,
                        }
                except json.JSONDecodeError:
                    pass

        return None
    except (json.JSONDecodeError, OSError):
        return None


def parse_from_stdout(output: str) -> dict | None:
    """
    Extract the first valid JSON object containing a "protocol" field
    from stdout output that may contain thinking text, markdown fences, etc.
    """
    # Strategy 1: Look for ```json ... ``` fences
    fence_pattern = re.compile(r"```json\s*\n(.*?)\n\s*```", re.DOTALL)
    for match in fence_pattern.finditer(output):
        try:
            obj = json.loads(match.group(1))
            if isinstance(obj, dict) and "protocol" in obj:
                return obj
        except json.JSONDecodeError:
            continue

    # Strategy 2: Find any { ... } block that parses as JSON with "protocol"
    depth = 0
    start = None
    for i, ch in enumerate(output):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                candidate = output[start : i + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict) and "protocol" in obj:
                        return obj
                except json.JSONDecodeError:
                    pass
                start = None

    return None


def validate_envelope(envelope: dict, match_config: dict, active_agent: str, current_turn: int) -> dict:
    """
    Validate the universal envelope fields (NOT the game-specific move payload).

    Returns:
        {"valid": bool, "message": str or None}
    """
    protocol = match_config.get("protocol_version", "lxm-v0.2")

    if envelope.get("protocol") != protocol:
        return {"valid": False, "message": f"Wrong protocol: expected '{protocol}', got '{envelope.get('protocol')}'"}

    if envelope.get("match_id") != match_config.get("match_id"):
        return {"valid": False, "message": f"Wrong match_id: expected '{match_config.get('match_id')}', got '{envelope.get('match_id')}'"}

    if envelope.get("agent_id") != active_agent:
        return {"valid": False, "message": f"Wrong agent_id: expected '{active_agent}', got '{envelope.get('agent_id')}'"}

    if envelope.get("turn") != current_turn:
        return {"valid": False, "message": f"Wrong turn: expected {current_turn}, got {envelope.get('turn')}"}

    if not isinstance(envelope.get("move"), dict):
        return {"valid": False, "message": "'move' field must be a JSON object"}

    return {"valid": True, "message": None}
