from __future__ import annotations

from collections.abc import Iterable

from .publisher_core import PublicationRejected


def ensure_trusted_gate_inputs_unchanged(
    changed_paths: Iterable[str],
    protected_paths: Iterable[str],
) -> None:
    changed = {path for path in changed_paths if isinstance(path, str) and path}
    protected = {path for path in protected_paths if isinstance(path, str) and path}
    overlap = sorted(changed & protected)
    if overlap:
        preview = ", ".join(overlap[:10])
        if len(overlap) > 10:
            preview += f", ... ({len(overlap) - 10} more)"
        raise PublicationRejected(
            "protected deterministic-review input changed; trusted publication refused: "
            + preview
        )
