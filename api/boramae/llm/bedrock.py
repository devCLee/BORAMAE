"""The bedrock-runtime client of the model parser (DEC-002, DES-015).

Credentials come from the default chain, which is the ECS task role in production, so
no key is read or stored here (SECURITY.md "Where keys live").
"""

from typing import TYPE_CHECKING

from boramae.config import Settings

if TYPE_CHECKING:
    from botocore.client import BaseClient

RUNTIME_SERVICE = "bedrock-runtime"
# ponytail: one attempt, because the rules answer a failed call (TR-F-005) and a retry
# spends more of the parse time budget and a second model call. Retry a throttled
# call if the measured fallback rate is too high.
MAX_ATTEMPTS = 1


def make_runtime_client(settings: Settings) -> "BaseClient":
    """A bedrock-runtime client for the configured Region with the parse timeout."""
    import boto3
    from botocore.config import Config

    timeout = settings.parse_model_timeout_s
    # ponytail: the timeout bounds the connect and each read, not the whole call, so a
    # slow answer can take up to twice the budget. Add a deadline if that ever matters.
    config = Config(
        connect_timeout=timeout,
        read_timeout=timeout,
        retries={"total_max_attempts": MAX_ATTEMPTS},
    )
    return boto3.client(RUNTIME_SERVICE, region_name=settings.aws_region, config=config)
