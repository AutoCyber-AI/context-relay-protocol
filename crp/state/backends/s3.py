# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""S3Backend — cold storage for large documents (SPEC-038 §3).

Optional dependency: ``boto3`` package. Falls back to import-time error
with helpful message if unavailable.
"""

from __future__ import annotations

import json
from typing import Any

from crp.state.backends.base import StorageBackend, StorageBackendError


class S3Backend(StorageBackend):
    """S3-backed storage for large / archival objects.

    TTL is simulated via object metadata (S3 does not natively support
    per-object TTL). Expired objects are skipped on get/keys.
    """

    name = "s3"

    def __init__(self, bucket: str, prefix: str = "crp/", region: str = "us-east-1") -> None:
        try:
            import boto3
        except ImportError as exc:
            raise StorageBackendError(
                "S3Backend requires 'boto3' package. Install: pip install boto3"
            ) from exc
        self._client = boto3.client("s3", region_name=region)
        self._bucket = bucket
        self._prefix = prefix

    def _make_key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get(self, key: str) -> Any:
        """Execute get and return the result.
        
            Args:
                key (str): The key value.
        
            Returns:
                ``Any``.
        """
        import time
        s3_key = self._make_key(key)
        try:
            obj = self._client.get_object(Bucket=self._bucket, Key=s3_key)
            meta = obj.get("Metadata", {})
            expiry = meta.get("crp-expiry")
            if expiry and float(expiry) <= time.time():
                return None
            return json.loads(obj["Body"].read().decode("utf-8"))
        except self._client.exceptions.NoSuchKey:
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Execute set and return the result.
        
            Args:
                key (str): The key value.
                value (Any): The value value.
                ttl (int | None): The ttl value.
        
            Returns:
                ``None``.
        """
        import time
        s3_key = self._make_key(key)
        meta: dict[str, str] = {}
        if ttl is not None:
            meta["crp-expiry"] = str(time.time() + ttl)
        self._client.put_object(
            Bucket=self._bucket,
            Key=s3_key,
            Body=json.dumps(value).encode("utf-8"),
            Metadata=meta,
        )

    def delete(self, key: str) -> None:
        """Execute delete and return the result.
        
            Args:
                key (str): The key value.
        
            Returns:
                ``None``.
        """
        s3_key = self._make_key(key)
        self._client.delete_object(Bucket=self._bucket, Key=s3_key)

    def keys(self) -> list[str]:
        """Execute keys and return the result.
        
            Returns:
                ``list[str]``.
        """
        import time
        paginator = self._client.get_paginator("list_objects_v2")
        result: list[str] = []
        prefix_len = len(self._prefix)
        for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"][prefix_len:]
                # Skip expired
                head = self._client.head_object(Bucket=self._bucket, Key=obj["Key"])
                expiry = head.get("Metadata", {}).get("crp-expiry")
                if expiry and float(expiry) <= time.time():
                    continue
                result.append(key)
        return result

    def size(self) -> int:
        """Return the current size count.
        
            Returns:
                ``int``.
        """
        return len(self.keys())
