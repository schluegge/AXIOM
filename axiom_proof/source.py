from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class SourceFile:
    path: str
    data: bytes
    text: str
    sha256: str

    @classmethod
    def load(cls, path: Path) -> "SourceFile":
        data = path.read_bytes()
        text = data.decode("utf-8", errors="strict")
        return cls(
            path=path.as_posix(),
            data=data,
            text=text,
            sha256=sha256(data).hexdigest(),
        )
