"""Shared by the schedule pipeline steps: the request timeout and the plain-text table."""

TIMEOUT_SECONDS = 30.0


def format_table(headers: tuple[str, ...], rows: list[tuple]) -> str:
    """A plain-text table with one row per item."""
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows)] if rows else [
        len(h) for h in headers
    ]
    lines = [" | ".join(h.ljust(w) for h, w in zip(headers, widths))]
    lines.append("-+-".join("-" * w for w in widths))
    lines.extend(" | ".join(str(c).ljust(w) for c, w in zip(row, widths)) for row in rows)
    return "\n".join(lines)

