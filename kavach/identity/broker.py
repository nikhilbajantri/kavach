"""Credential broker: the agent holds no keys; KAVACH mints one-action, 60-second tokens.

Tokens are EdDSA (Ed25519) signed. Upstream services hold only the *public*
key, so a compromised upstream cannot mint tokens either. Each token is bound
to one tool and one exact argument set via `args_hash`, which makes replaying
it with different arguments useless.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from kavach.canonical import args_hash

ISSUER = "kavach"
ALGORITHM = "EdDSA"


@dataclass(frozen=True)
class Identity:
    agent_id: str
    on_behalf_of: str
    task_id: str

    def describe(self) -> str:
        return f"agent {self.agent_id} → on behalf of {self.on_behalf_of} → task {self.task_id}"


@dataclass(frozen=True)
class MintedToken:
    token: str
    jti: str
    expires_at: int


class TokenError(Exception):
    """Raised by upstream verifiers; maps to HTTP 401."""


def load_or_generate_key(pem: str | None) -> Ed25519PrivateKey:
    if pem:
        key = serialization.load_pem_private_key(pem.encode(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("KAVACH_SIGNING_KEY_PEM must be an Ed25519 private key")
        return key
    return Ed25519PrivateKey.generate()


class CredentialBroker:
    """Mints short-lived, args-bound action tokens. Only KAVACH instantiates this."""

    def __init__(self, private_key: Ed25519PrivateKey, ttl_seconds: int = 60) -> None:
        self._key = private_key
        self.ttl_seconds = ttl_seconds

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self._key.public_key()

    def mint(
        self, identity: Identity, tool: str, args: dict[str, Any], now: float | None = None
    ) -> MintedToken:
        issued = int(now if now is not None else time.time())
        jti = f"tok_{uuid.uuid4().hex[:16]}"
        claims = {
            "iss": ISSUER,
            "jti": jti,
            "iat": issued,
            "exp": issued + self.ttl_seconds,
            "agent_id": identity.agent_id,
            "on_behalf_of": identity.on_behalf_of,
            "task_id": identity.task_id,
            "tool": tool,
            "args_hash": args_hash(args),
        }
        return MintedToken(
            token=jwt.encode(claims, self._key, algorithm=ALGORITHM), jti=jti, expires_at=claims["exp"]
        )


class TokenVerifier:
    """Embedded in every upstream (payments, email, CRM). Holds only the public key."""

    def __init__(self, public_key: Ed25519PublicKey) -> None:
        self._public_key = public_key

    def verify(self, token: str | None, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        if not token:
            raise TokenError("missing KAVACH action token")
        try:
            claims = jwt.decode(
                token,
                self._public_key,
                algorithms=[ALGORITHM],
                issuer=ISSUER,
                options={"require": ["exp", "iat", "jti", "args_hash", "tool"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenError("token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise TokenError(f"invalid token: {exc}") from exc
        if claims["tool"] != tool:
            raise TokenError(f"token minted for {claims['tool']}, not {tool}")
        if claims["args_hash"] != args_hash(args):
            raise TokenError("token args_hash does not match request arguments")
        return claims
