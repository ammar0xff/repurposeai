"""S3Storage. Requires boto3 + env (bucket/region/credentials)."""
from .base import StorageProvider


class S3Storage(StorageProvider):
    def __init__(self, bucket: str, prefix: str = "repurposeai/", region: str = ""):
        try:
            import boto3  # type: ignore
        except ImportError as e:
            raise RuntimeError("boto3 not installed; pip install repurposeai[s3]") from e
        import os
        self.bucket = bucket or os.environ.get("S3_STORAGE_BUCKET", "")
        if not self.bucket:
            raise RuntimeError("S3_STORAGE_BUCKET not configured")
        self.prefix = prefix
        self.s3 = boto3.client("s3", region_name=region or None)

    def _k(self, key: str) -> str:
        return f"{self.prefix}{key}".replace("//", "/")

    def put(self, key: str, data: bytes) -> str:
        self.s3.put_object(Bucket=self.bucket, Key=self._k(key), Body=data)
        return key

    def put_file(self, key: str, src_path: str) -> str:
        self.s3.upload_file(src_path, self.bucket, self._k(key))
        return key

    def get(self, key: str) -> bytes:
        return self.s3.get_object(Bucket=self.bucket, Key=self._k(key))["Body"].read()

    def get_path(self, key: str) -> str:
        import tempfile
        fd, tmp = tempfile.mkstemp(prefix="rpa-")
        import os as _os
        _os.close(fd)
        self.s3.download_file(self.bucket, self._k(key), tmp)
        return tmp

    def delete(self, key: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=self._k(key))

    def exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=self._k(key))
            return True
        except Exception:  # noqa: BLE001 - boto3 optional; any head failure means absent
            return False

    def list(self, prefix: str) -> list[str]:
        out, tok = [], None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": self._k(prefix)}
            if tok:
                kw["ContinuationToken"] = tok
            r = self.s3.list_objects_v2(**kw)
            out += [o["Key"][len(self.prefix):] for o in r.get("Contents", [])]
            tok = r.get("NextContinuationToken")
            if not tok:
                return out

    def url(self, key: str) -> str:
        return self.s3.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": self._k(key)},
            ExpiresIn=3600)
