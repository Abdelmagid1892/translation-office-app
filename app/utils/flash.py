from typing import Optional

from fastapi import Request


FLASH_KEY = "flash_message"


def set_flash(request: Request, message: str, category: str = "success") -> None:
    request.session[FLASH_KEY] = {"message": message, "category": category}


def pop_flash(request: Request) -> Optional[dict]:
    data = request.session.get(FLASH_KEY)
    if data:
        request.session.pop(FLASH_KEY, None)
    return data
