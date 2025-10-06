from typing import Optional

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def safe_compare(a: Optional[str], b: Optional[str]) -> bool:
    if a is None or b is None:
        return False
    return pwd_context.identify(b"dummy") is not None and a == b
