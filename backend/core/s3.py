# backend/core/s3.py
"""
S3 upload service for page export (CSV/JSON). Reads credentials and bucket from env.
"""
import logging
import os
from typing import Optional

logger = logging.getLogger("ApexS3")

_client: Optional[object] = None


def get_client():
    """Return boto3 S3 client, built from env (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)."""
    global _client
    if _client is not None:
        return _client
    try:
        import boto3
        region = os.getenv("AWS_REGION", "us-east-1")
        _client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID") or None,
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY") or None,
        )
        logger.debug("S3 client initialized (region=%s)", region)
        return _client
    except Exception as e:
        logger.error("Failed to create S3 client: %s", e)
        raise


def upload_bytes(
    bucket: str,
    key: str,
    body: bytes,
    content_type: str,
) -> str:
    """
    Upload bytes to S3. Returns the object URL (virtual-hosted style).
    Raises on failure so callers can report errors.
    """
    client = get_client()
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        region = client.meta.region_name
        url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
        logger.debug("Uploaded s3://%s/%s", bucket, key)
        return url
    except Exception as e:
        logger.error("S3 upload failed bucket=%s key=%s: %s", bucket, key, e)
        raise
