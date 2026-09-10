"""Password auth: scrypt hashing (stdlib), DB-backed tokens with expiry.
Single local account for dev; multi-user ready via user_id scoping."""
import hashlib
import hmac
import secrets
import time

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${dk.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        cand = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt),
                              n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(cand, bytes.fromhex(dk))
    except (ValueError, TypeError):
        return False


def new_token() -> tuple[str, str]:
    """(public token, sha256 for storage). Raw token shown once, never stored."""
    raw = "rpa_" + secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return raw, digest


def token_expiry(days: int = 30) -> float:
    return time.time() + days * 86400
