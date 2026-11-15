"""Result store in an S3 bucket. Create-once is a conditional put (If-None-Match: *).

Checked against the PutObject model of the installed botocore 1.44.3: IfNoneMatch
sends the If-None-Match header, an existing key gives 412 PreconditionFailed, and a
conflicting upload in progress gives 409 ConditionalRequestConflict. The real
bucket check belongs to package W8-DEPLOY (TDD.md Q-005).
"""

from botocore.client import BaseClient
from botocore.exceptions import ClientError

JSON_MEDIA_TYPE = "application/json"
ANY_ETAG = "*"
MISSING_KEY_CODE = "NoSuchKey"
# ponytail: botocore says to retry a 409, but the other upload writes the same bytes
# for the same key; read 409 as "exists", and ResultService falls back to its own body.
EXISTS_CODES = frozenset({"PreconditionFailed", "ConditionalRequestConflict"})


class S3Store:
    """ports.ObjectStore over one bucket. A store path is the object key."""

    def __init__(self, bucket: str, client: BaseClient) -> None:
        self.bucket = bucket
        self.client = client

    def get(self, path: str) -> bytes | None:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=path)
        except ClientError as exc:
            if _error_code(exc) == MISSING_KEY_CODE:
                return None
            raise
        return response["Body"].read()

    def create_once(self, path: str, body: bytes) -> bool:
        try:
            self._put(path, body, IfNoneMatch=ANY_ETAG)
        except ClientError as exc:
            if _error_code(exc) in EXISTS_CODES:
                return False
            raise
        return True

    def put(self, path: str, body: bytes) -> None:
        self._put(path, body)

    def _put(self, path: str, body: bytes, **condition: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=path,
            Body=body,
            ContentType=JSON_MEDIA_TYPE,
            **condition,
        )


def _error_code(exc: ClientError) -> str:
    return exc.response.get("Error", {}).get("Code", "")
