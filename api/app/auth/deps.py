from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import Principal
from app.auth.service import Authenticator, unauthenticated

PROVIDER_HEADER = "X-Auth-Provider"

bearer = HTTPBearer(auto_error=False)


def get_authenticator(request: Request) -> Authenticator:
    return request.app.state.authenticator


async def current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    authenticator: Annotated[Authenticator, Depends(get_authenticator)],
) -> Principal:
    if credentials is None:
        raise unauthenticated("Missing bearer token")
    return await authenticator.authenticate(
        credentials.credentials, request.headers.get(PROVIDER_HEADER)
    )


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]
