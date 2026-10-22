"""Хеширование паролей (PBKDF2) и токены доступа JWT (HS256) на стандартной библиотеке."""
import base64
import hashlib
import hmac
import json
import secrets
import time

from common.errors import Unauthorized

PBKDF2_ROUNDS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ROUNDS).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    salt, _, digest = stored.partition("$")
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ROUNDS).hex()
    return hmac.compare_digest(candidate, digest)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(secret: str, signing_input: str) -> str:
    return _b64(hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest())


def create_token(secret: str, username: str, role: str, ttl_seconds: int = 3600) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({"sub": username, "role": role, "exp": int(time.time()) + ttl_seconds}).encode())
    return f"{header}.{payload}.{_sign(secret, f'{header}.{payload}')}"


def decode_token(secret: str, token: str) -> dict:
    try:
        header, payload, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(secret, f"{header}.{payload}")):
            raise ValueError("signature")
        claims = json.loads(_unb64(payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise Unauthorized("Недействительный токен доступа") from exc
    if claims.get("exp", 0) < time.time():
        raise Unauthorized("Срок действия токена истёк")
    return claims
