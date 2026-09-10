"""Storage abstraction. No raw filesystem calls outside providers."""
from abc import ABC, abstractmethod
from pathlib import PurePosixPath


class StorageProvider(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes) -> str: ...
    @abstractmethod
    def put_file(self, key: str, src_path: str) -> str: ...
    @abstractmethod
    def get(self, key: str) -> bytes: ...
    @abstractmethod
    def get_path(self, key: str) -> str:
        """Local filesystem path (local backend) or cached download (remote)."""
    @abstractmethod
    def delete(self, key: str) -> None: ...
    @abstractmethod
    def exists(self, key: str) -> bool: ...
    @abstractmethod
    def list(self, prefix: str) -> list[str]: ...
    @abstractmethod
    def url(self, key: str) -> str: ...


def project_key(project_id: str, *parts: str) -> str:
    safe = str(PurePosixPath(*parts))
    if ".." in safe.split("/"):
        raise ValueError("path traversal rejected")
    return f"projects/{project_id}/{safe}"
