"""027 — single sign-on (OIDC): start sends to the provider with PKCE; the way back checks the ID token's
signature, audience and nonce, finds or creates the member (by a linked account, else the same e-mail),
opens the session, and the state is used once."""

import base64
import hashlib
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select, update

from portalab.modules.identity.models import ExternalIdentity, User
from portalab.modules.identity.module import IdentityModule
from portalab.modules.identity.services.oidc import OidcSettings, SignOnFailed, safe_next
from tests.identity_fakes import IdentityHarness
from tests.integration.identity.helpers import create_user

ISSUER = "https://sso.example.org/application/o/portalab"
REDIRECT = "https://portal.example.org/api/v1/auth/oidc/callback"


class Provider:
    """A fake Authentik: discovery, token endpoint, keys; signs ID tokens with an RSA key."""

    def __init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.claims: dict[str, Any] = {}
        self.nonce = ""
        self.verifier = ""

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/authorize",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/jwks",
                },
            )
        if path.endswith("/jwks"):
            jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
            return httpx.Response(200, json={"keys": [{**jwk, "kid": "k1"}]})
        if path.endswith("/token"):
            form = parse_qs(request.content.decode())
            self.verifier = form["code_verifier"][0]
            token = jwt.encode(
                {
                    "iss": ISSUER,
                    "aud": "portal",
                    "iat": 1,
                    "exp": 4_000_000_000,
                    "nonce": self.nonce,
                    **self.claims,
                },
                self.key,
                algorithm="RS256",
                headers={"kid": "k1"},
            )
            return httpx.Response(200, json={"id_token": token, "access_token": "x"})
        return httpx.Response(404)


@pytest.fixture
def module(harness: IdentityHarness) -> IdentityModule:
    return IdentityModule(harness.context)


def ready(module: IdentityModule, provider: Provider, create: bool = True) -> None:
    async def settings() -> OidcSettings:
        return OidcSettings(True, ISSUER, "portal", "s3cret", "Authentik", create)

    module.oidc.settings = settings  # type: ignore[method-assign]
    module.oidc.transport = httpx.MockTransport(provider.handle)


async def sign_on(module: IdentityModule, provider: Provider, claims: dict[str, Any]) -> tuple[Any, str]:
    url = urlparse(await module.oidc.start(REDIRECT, "/media"))
    query = parse_qs(url.query)
    assert query["code_challenge_method"] == ["S256"] and query["redirect_uri"] == [REDIRECT]
    provider.nonce = query["nonce"][0]
    provider.claims = claims
    signed, next_path = await module.oidc.finish(
        "code", query["state"][0], REDIRECT, client_ip="10.0.0.1", user_agent="test", previous_token=None
    )
    challenge = base64.urlsafe_b64encode(hashlib.sha256(provider.verifier.encode()).digest()).rstrip(b"=")
    assert query["code_challenge"] == [challenge.decode()]  # the verifier sent matches the challenge
    return signed, next_path


async def test_first_sign_on_creates_the_member_then_finds_them_again(module: IdentityModule) -> None:
    provider = Provider()
    ready(module, provider)
    claims = {"sub": "ak-1", "email": "Ada@Example.org", "preferred_username": "ada", "name": "Ada L."}
    signed, next_path = await sign_on(module, provider, claims)
    assert next_path == "/media" and signed.issued.token
    again, _ = await sign_on(module, provider, {**claims, "email": "new@example.org"})
    assert again.user_id == signed.user_id  # the linked provider account, whatever its e-mail became
    async with module.ctx.database.session() as session:
        user = await session.get(User, signed.user_id)
        links = list((await session.execute(select(ExternalIdentity))).scalars())
    assert user is not None and user.login == "ada" and user.email == "ada@example.org"
    assert [(link.issuer, link.subject) for link in links] == [(ISSUER, "ak-1")]


async def test_same_email_links_the_existing_member(module: IdentityModule) -> None:
    provider = Provider()
    ready(module, provider, create=False)
    user_id = await create_user(module, "grace")
    async with module.ctx.database.unit_of_work() as uow:
        await uow.session.execute(update(User).where(User.id == user_id).values(email="grace@example.org"))
    signed, _ = await sign_on(module, provider, {"sub": "ak-2", "email": "grace@example.org"})
    assert signed.user_id == user_id
    with pytest.raises(SignOnFailed):  # nobody with this e-mail, and no account creation
        await sign_on(module, provider, {"sub": "ak-3", "email": "nobody@example.org"})


async def test_a_state_is_used_once_and_a_forged_token_refused(module: IdentityModule) -> None:
    provider = Provider()
    ready(module, provider)
    url = urlparse(await module.oidc.start(REDIRECT, "https://evil.example.org"))
    state = parse_qs(url.query)["state"][0]
    provider.nonce = "not the one"  # the ID token carries another nonce
    provider.claims = {"sub": "ak-4"}
    with pytest.raises(SignOnFailed):
        await module.oidc.finish("c", state, REDIRECT, client_ip=None, user_agent=None, previous_token=None)
    with pytest.raises(SignOnFailed):  # already used
        await module.oidc.finish("c", state, REDIRECT, client_ip=None, user_agent=None, previous_token=None)
    assert safe_next("https://evil.example.org") == "/" and safe_next("//evil") == "/"
