import os
from pathlib import Path

# Security: Set a hard limit on output size (approx 16k tokens)
MAX_OUTPUT_CHARS = 64000 

def is_safe_path(base_dir: str, target_path: str) -> bool:
    """
    Ensures target_path resolves to somewhere inside base_dir.
    Prevents ../../../etc/passwd attacks.
    """
    try:
        base = Path(base_dir).resolve()
        target = (base / target_path).resolve()
        # The target must start with the base path
        return base in target.parents or base == target
    except Exception:
        return False

def truncate_output(content: str, max_chars: int = MAX_OUTPUT_CHARS) -> dict:
    """
    Truncates text to fit within context window limits.
    """
    if len(content) <= max_chars:
        return {"content": content, "truncated": False}
    
    return {
        "content": content[:max_chars] + "\n... [TRUNCATED DUE TO SIZE]",
        "truncated": True,
        "original_length": len(content)
    }

def slice_lines(content: str, start_line: int, end_line: int) -> str:
    """
    Returns a specific range of lines (1-based indexing).
    """
    lines = content.splitlines()
    # Adjust for 0-based index vs 1-based input
    start = max(0, start_line - 1)
    end = min(len(lines), end_line)
    
    return "\n".join(lines[start:end])