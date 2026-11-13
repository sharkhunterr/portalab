"""027 — single sign-on (OIDC): start sends to the provider with PKCE; the way back checks the ID token's
signature, audience and nonce, finds or creates the member (by a linked account, else the member signed in,
else the same e-mail — the Admin's only when the provider vouches for it), opens the session, and the state
is used once, in the browser that started it (#277)."""

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

from portalab.core.errors import Unavailable
from portalab.modules.identity.models import ExternalIdentity, User
from portalab.modules.identity.module import IdentityModule
from portalab.modules.identity.services.oidc import OidcSettings, SignOnFailed, browser_binding, safe_next
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


def ready(module: IdentityModule, provider: Provider, create: bool = True, trust: bool = False) -> None:
    async def settings() -> OidcSettings:
        return OidcSettings(True, ISSUER, "portal", "s3cret", "Authentik", create, trust)

    module.oidc.settings = settings  # type: ignore[method-assign]
    module.oidc.transport = httpx.MockTransport(provider.handle)


async def sign_on(
    module: IdentityModule,
    provider: Provider,
    claims: dict[str, Any],
    *,
    token: str | None = None,
    browser: str | None = "",
) -> tuple[Any, str]:
    url = urlparse(await module.oidc.start(REDIRECT, "/media"))
    query = parse_qs(url.query)
    assert query["code_challenge_method"] == ["S256"] and query["redirect_uri"] == [REDIRECT]
    provider.nonce = query["nonce"][0]
    provider.claims = claims
    signed, next_path = await module.oidc.finish(
        "code",
        query["state"][0],
        REDIRECT,
        client_ip="10.0.0.1",
        user_agent="test",
        previous_token=token,
        browser=browser_binding(query["state"][0]) if browser == "" else browser,
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
    signed, _ = await sign_on(
        module, provider, {"sub": "ak-2", "email": "grace@example.org", "email_verified": True}
    )
    assert signed.user_id == user_id
    with pytest.raises(SignOnFailed):  # nobody with this e-mail, and no account creation
        await sign_on(
            module, provider, {"sub": "ak-3", "email": "nobody@example.org", "email_verified": True}
        )


async def test_a_state_is_used_once_and_a_forged_token_refused(module: IdentityModule) -> None:
    provider = Provider()
    ready(module, provider)
    url = urlparse(await module.oidc.start(REDIRECT, "https://evil.example.org"))
    state = parse_qs(url.query)["state"][0]
    provider.nonce = "not the one"  # the ID token carries another nonce
    provider.claims = {"sub": "ak-4"}
    with pytest.raises(SignOnFailed):
        await module.oidc.finish(
            "c",
            state,
            REDIRECT,
            client_ip=None,
            user_agent=None,
            previous_token=None,
            browser=browser_binding(state),
        )
    with pytest.raises(SignOnFailed):  # already used
        await module.oidc.finish(
            "c",
            state,
            REDIRECT,
            client_ip=None,
            user_agent=None,
            previous_token=None,
            browser=browser_binding(state),
        )
    assert safe_next("https://evil.example.org") == "/" and safe_next("//evil") == "/"


async def test_an_e_mail_the_provider_disowns_links_nobody(module: IdentityModule) -> None:
    provider = Provider()
    ready(module, provider, create=False)
    user_id = await create_user(module, "hedy")
    async with module.ctx.database.unit_of_work() as uow:
        await uow.session.execute(update(User).where(User.id == user_id).values(email="hedy@example.org"))
    with pytest.raises(SignOnFailed):
        await sign_on(module, provider, {"sub": "ak-5", "email": "hedy@example.org", "email_verified": False})
    # issue 403: left out (Authentik's own users) — neither linked nor duplicated, unless trusted
    with pytest.raises(SignOnFailed):
        await sign_on(module, provider, {"sub": "ak-5", "email": "hedy@example.org"})
    ready(module, provider, create=True, trust=False)
    with pytest.raises(SignOnFailed):  # no second account with that e-mail either
        await sign_on(module, provider, {"sub": "ak-5", "email": "hedy@example.org"})
    ready(module, provider, create=False, trust=True)  # the administrator trusts the provider's e-mails
    with pytest.raises(SignOnFailed):  # still never one the provider disowns
        await sign_on(module, provider, {"sub": "ak-5", "email": "hedy@example.org", "email_verified": False})
    signed, _ = await sign_on(module, provider, {"sub": "ak-5", "email": "hedy@example.org"})
    assert signed.user_id == user_id


async def test_the_admin_is_found_by_e_mail_only_when_the_provider_vouches(
    module: IdentityModule, harness: IdentityHarness
) -> None:
    """#277: anyone able to set their e-mail at the provider would otherwise become the Admin."""
    provider = Provider()
    ready(module, provider, create=False)
    admin = await create_user(module, "root")
    harness.authority.admin = admin
    async with module.ctx.database.unit_of_work() as uow:
        await uow.session.execute(update(User).where(User.id == admin).values(email="root@example.org"))
    with pytest.raises(SignOnFailed):
        await sign_on(module, provider, {"sub": "ak-6", "email": "root@example.org"})
    ready(module, provider, create=False, trust=True)
    with pytest.raises(SignOnFailed):  # trusting the provider's e-mails never covers the Admin's
        await sign_on(module, provider, {"sub": "ak-6", "email": "root@example.org"})
    signed, _ = await sign_on(
        module, provider, {"sub": "ak-6", "email": "root@example.org", "email_verified": True}
    )
    assert signed.user_id == admin
    again, _ = await sign_on(module, provider, {"sub": "ak-6"})
    assert again.user_id == admin


async def test_the_way_back_is_refused_in_another_browser(module: IdentityModule) -> None:
    """#277: a victim sent the attacker's way back (code and state) is not signed in as the attacker."""
    provider = Provider()
    ready(module, provider)
    for browser in (None, "x" * 64, browser_binding("another state")):
        with pytest.raises(SignOnFailed):
            await sign_on(module, provider, {"sub": "ak-7"}, browser=browser)


async def test_a_provider_naming_another_issuer_is_refused(module: IdentityModule) -> None:
    """Issue 403: the discovery document's issuer is the one configured (OpenID Connect Discovery 4.3)."""
    provider = Provider()
    ready(module, provider)
    real = provider.handle

    def lying(request: httpx.Request) -> httpx.Response:
        answer = real(request)
        if request.url.path.endswith("/.well-known/openid-configuration"):
            body = answer.json()
            return httpx.Response(200, json={**body, "issuer": "https://evil.example.org/"})
        return answer

    module.oidc.transport = httpx.MockTransport(lying)
    module.oidc._discovery.clear()
    with pytest.raises(Unavailable):
        await module.oidc.start(REDIRECT, "/")
