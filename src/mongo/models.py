"""
Contains all database models
"""
from typing import Annotated

from beanie import Document, Indexed


class Ping(Document):
    user_id: Annotated[int, Indexed()]
    word_pings: list[str]
    dnd: bool

    class Settings:
        name = "pings"
        use_cache = False
