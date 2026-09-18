from ipaddress import ip_address
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, SecretStr

from app.local_runner.credentials import CredentialResolver


router = APIRouter(prefix="/local-credentials", tags=["local-credentials"])


class CredentialWrite(BaseModel):
    secret: SecretStr


class CredentialStatus(BaseModel):
    reference: str
    available: bool


def get_resolver(request: Request) -> CredentialResolver:
    try:
        if not ip_address(request.app.state.settings.api_bind_host).is_loopback:
            raise HTTPException(
                status_code=403,
                detail="Local credential API requires loopback binding",
            )
    except ValueError as exception:
        raise HTTPException(
            status_code=403,
            detail="Local credential API requires loopback binding",
        ) from exception
    return request.app.state.credential_resolver


ResolverDependency = Annotated[CredentialResolver, Depends(get_resolver)]


def _disable_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.put("/{reference}", response_model=CredentialStatus)
def enroll_credential(
    reference: str,
    payload: CredentialWrite,
    response: Response,
    resolver: ResolverDependency,
):
    value = payload.secret.get_secret_value()
    try:
        resolver.enroll(reference, value)
    finally:
        value = ""
    _disable_cache(response)
    return CredentialStatus(reference=reference, available=True)


@router.get("/{reference}/status", response_model=CredentialStatus)
def credential_status(
    reference: str, response: Response, resolver: ResolverDependency
):
    _disable_cache(response)
    return CredentialStatus(reference=reference, available=resolver.available(reference))


@router.delete("/{reference}", response_model=CredentialStatus)
def delete_credential(
    reference: str, response: Response, resolver: ResolverDependency
):
    resolver.delete(reference)
    _disable_cache(response)
    return CredentialStatus(reference=reference, available=False)

