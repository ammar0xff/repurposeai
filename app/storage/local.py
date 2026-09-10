"""LocalFilesystemStorage. Deterministic layout under STORAGE_PATH."""
import shutil
from pathlib import Path

from .base import StorageProvider


class LocalFilesystemStorage(StorageProvider):
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents and p != self.root.resolve():
            raise ValueError("path traversal rejected")
        return p

    def put(self, key: str, data: bytes) -> str:
        p = self._p(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def put_file(self, key: str, src_path: str) -> str:
        p = self._p(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, p)
        return key

    def get(self, key: str) -> bytes:
        return self._p(key).read_bytes()

    def get_path(self, key: str) -> str:
        p = self._p(key)
        if not p.exists():
            raise FileNotFoundError(key)
        return str(p)

    def delete(self, key: str) -> None:
        self._p(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._p(key).exists()

    def list(self, prefix: str) -> list[str]:
        base = self._p(prefix)
        if not base.exists():
            return []
        root = self.root.resolve()
        return sorted(str(f.relative_to(root)) for f in base.rglob("*") if f.is_file())

    def url(self, key: str) -> str:
        return f"file://{self._p(key)}"
