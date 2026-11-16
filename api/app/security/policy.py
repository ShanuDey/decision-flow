from app.limits import Limits
from app.security.ssrf import OutboundPolicy
from app.settings import Settings


def outbound_policy(settings: Settings, limits: Limits) -> OutboundPolicy:
    return OutboundPolicy(
        allow_private=settings.allow_private_networks,
        allowed_hosts=tuple(settings.http_allowed_hosts),
        max_bytes=limits.max_http_response_bytes,
        timeout_seconds=limits.http_timeout_seconds,
    )
