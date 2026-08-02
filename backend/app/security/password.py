from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Returns False (never raises) for any mismatch, or a malformed/corrupt
    stored hash — either way the caller's answer is simply "not authenticated".

    Note: argon2-cffi's InvalidHashError subclasses ValueError, not
    Argon2Error, so it needs to be listed separately.
    """
    try:
        return _hasher.verify(password_hash, password)
    except (Argon2Error, InvalidHashError):
        return False
