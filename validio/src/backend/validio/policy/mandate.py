"""Spend Pass: the kitchen's signed permission as an SD-JWT, bound to the agent's key (ES256).

The agent fetches a fresh nonce for every order and shows only the fields a decision needs.
sd-jwt 0.10.4 does not check exp or nbf, so we do. Every failure is a MandateError (HTTP 401).
"""

import base64
import json
import secrets
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from jwcrypto.jwk import JWK
from jwcrypto.jws import JWS, InvalidJWSSignature
from sd_jwt.common import SDObj
from sd_jwt.holder import SDJWTHolder
from sd_jwt.issuer import SDJWTIssuer
from sd_jwt.verifier import SDJWTVerifier

ALG = "ES256"
AUDIENCE = "validio:agent-v1"

# Spend Pass M-1 from the blueprint: valid 14 Nov 10:00 to 17 Nov 00:00 Helsinki (UTC+2).
DEMO_CLAIMS: dict[str, Any] = {
    "iss": "kitchen:hotel-espoo",
    "sub": "agent:buyer-1",
    "jti": "M-1",
    "iat": 1794643200,
    "nbf": 1794643200,
    "exp": 1794866400,
    "autoLimitCents": 120000,
    "hardCapCents": 200000,
    "categories": ["104", "106", "418"],
    "diet": ["FREE_FROM_LACTOSE"],
    "deliverBy": "2026-11-16",
    "substitutes": "listed_and_rules_kept",
    "split": {"maxExtraCostPct": 5, "allowListedSubstitutes": True},
    "preferLabels": [],
    "approvers": ["owner:anna"],
}
DEMO_SD_FIELDS = frozenset({"autoLimitCents", "hardCapCents", "diet", "preferLabels", "approvers"})

_REGISTERED = {"iss", "sub", "jti", "iat", "nbf", "exp", "cnf", "_sd_alg"}


class MandateError(Exception):
    """The Spend Pass was not accepted. The message says why, never the token."""


@dataclass(frozen=True)
class Mandate:
    id: str
    issuer: str
    holder: str
    not_before: int
    expires: int
    categories: tuple[str, ...]
    deliver_by: str | None
    substitutes: str | None
    split_max_extra_bp: int  # basis points, 5 % = 500
    split_allow_listed: bool
    auto_limit_cents: int | None  # None when not disclosed
    hard_cap_cents: int | None
    diet: tuple[str, ...] | None
    prefer_labels: tuple[str, ...] | None
    disclosed: dict[str, Any]  # only the selectively disclosable fields the agent showed


# The only `substitutes` value that lets a listed substitute order alone. Anything else fails closed.
SUBSTITUTES_LISTED = "listed_and_rules_kept"


def effective_deadline(m: Mandate, requested: date | None) -> date | None:
    """The deadline that counts: the earlier of the signed `deliverBy` and the request. A request can
    move it earlier, never later. A `deliverBy` that does not parse lets nothing arrive in time."""
    signed = None
    if m.deliver_by is not None:
        try:
            signed = date.fromisoformat(str(m.deliver_by))
        except ValueError:
            return date.min
    dates = [d for d in (signed, requested) if d is not None]
    return min(dates) if dates else None


def load_or_create_key(path: Path) -> JWK:
    """A P-256 key for ES256, kept as a JWK file readable only by us (data/keys/ is gitignored)."""
    path = Path(path)
    if path.is_file():
        return JWK.from_json(path.read_text())
    key = JWK.generate(kty="EC", crv="P-256")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600)
    path.write_text(key.export_private())
    return key


def issue_mandate(
    claims: Mapping[str, Any], sd_fields: set[str] | frozenset[str], kitchen: JWK, agent_pub: JWK
) -> str:
    payload = {(SDObj(k) if k in sd_fields else k): v for k, v in claims.items()}
    issuer = SDJWTIssuer(payload, kitchen, holder_key=agent_pub, sign_alg=ALG)
    return issuer.sd_jwt_issuance


def present(mandate: str, disclose: set[str] | frozenset[str], agent: JWK, aud: str, nonce: str) -> str:
    holder = SDJWTHolder(mandate)
    holder.create_presentation(
        {k: True for k in disclose}, nonce=nonce, aud=aud, holder_key=agent, sign_alg=ALG
    )
    return holder.sd_jwt_presentation


class NonceStore:
    """Single-use nonces from /agent/v1/nonce. A nonce is good once and only for `ttl`."""

    def __init__(self, ttl: timedelta = timedelta(minutes=5)):
        self.ttl = ttl
        self._issued: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def issue(self, now: datetime) -> str:
        nonce = secrets.token_urlsafe(24)
        with self._lock:
            self._issued = {n: t for n, t in self._issued.items() if now - t <= self.ttl}
            self._issued[nonce] = now
        return nonce

    def check(self, nonce: str, now: datetime) -> None:
        with self._lock:
            t = self._issued.get(nonce)
        if t is None:
            raise MandateError("unknown or reused nonce")
        if now - t > self.ttl:
            raise MandateError("stale nonce")

    def consume(self, nonce: str, now: datetime) -> None:
        with self._lock:
            t = self._issued.pop(nonce, None)
        if t is None:
            raise MandateError("unknown or reused nonce")
        if now - t > self.ttl:
            raise MandateError("stale nonce")


def _b64json(segment: str) -> dict[str, Any]:
    return json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))


def _kb_nonce(token: str) -> str:
    try:
        kb = token.rsplit("~", 1)[1]
        nonce = _b64json(kb.split(".")[1])["nonce"]
    except (IndexError, KeyError, ValueError) as e:
        raise MandateError("no key binding") from e
    if not isinstance(nonce, str):
        raise MandateError("no key binding")
    return nonce


def verify_presentation(
    token: str, *, kitchen_pub: JWK, issuer: str, aud: str, nonces: NonceStore, now: datetime
) -> Mandate:
    """Signature, ES256, issuer, key binding, audience, single-use nonce, nbf and exp."""
    nonce = _kb_nonce(token)
    nonces.check(nonce, now)
    try:
        issuer_jwt = token.split("~", 1)[0]
        if _b64json(issuer_jwt.split(".")[0]).get("alg") != ALG:
            raise MandateError("wrong algorithm")
        # checked here first, so a failing signature below can only be the agent's key binding
        jws = JWS()
        jws.deserialize(issuer_jwt)
        try:
            jws.verify(kitchen_pub, alg=ALG)
        except InvalidJWSSignature as e:
            raise MandateError("issuer signature does not verify") from e
        verifier = SDJWTVerifier(
            token,
            lambda iss, _hdr: kitchen_pub if iss == issuer else _raise(MandateError("unknown issuer")),
            expected_aud=aud,
            expected_nonce=nonce,
        )
        payload = verifier.get_verified_payload()
    except MandateError:
        raise
    except InvalidJWSSignature as e:
        raise MandateError("holder key binding does not verify") from e
    except ValueError as e:
        msg = str(e)
        if "Invalid audience" in msg:
            raise MandateError("wrong audience") from e
        if "Invalid digest" in msg:
            raise MandateError("disclosures do not match the key binding") from e
        raise MandateError(f"invalid Spend Pass ({type(e).__name__})") from e
    except Exception as e:  # sd-jwt raises KeyError or other jwcrypto errors
        raise MandateError(f"invalid Spend Pass ({type(e).__name__})") from e

    ts = int(now.timestamp())
    nbf, exp = payload.get("nbf"), payload.get("exp")
    if not isinstance(nbf, int) or not isinstance(exp, int):
        raise MandateError("Spend Pass without validity window")
    if ts < nbf:
        raise MandateError("Spend Pass not valid yet")
    if ts >= exp:
        raise MandateError("Spend Pass expired")
    nonces.consume(nonce, now)
    return _mandate(payload)


def _raise(e: Exception):
    raise e


def _ints(v: Any) -> int | None:
    if v is None:
        return None
    if type(v) is not int:
        raise MandateError("money must be whole cents")
    return v


def _mandate(p: dict[str, Any]) -> Mandate:
    split = p.get("split") or {}
    disclosed = {k: p[k] for k in DEMO_SD_FIELDS if k in p}
    diet, labels = p.get("diet"), p.get("preferLabels")
    return Mandate(
        id=p.get("jti", ""),
        issuer=p.get("iss", ""),
        holder=p.get("sub", ""),
        not_before=p["nbf"],
        expires=p["exp"],
        categories=tuple(p.get("categories") or ()),
        deliver_by=p.get("deliverBy"),
        substitutes=p.get("substitutes"),
        split_max_extra_bp=round(float(split.get("maxExtraCostPct", 0)) * 100),
        split_allow_listed=bool(split.get("allowListedSubstitutes", False)),
        auto_limit_cents=_ints(p.get("autoLimitCents")),
        hard_cap_cents=_ints(p.get("hardCapCents")),
        diet=tuple(diet) if diet is not None else None,
        prefer_labels=tuple(labels) if labels is not None else None,
        disclosed=disclosed,
    )
