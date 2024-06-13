"""
Contains all database models
"""
from datetime import datetime
from typing import Literal

from beanie import Document


class Invitational(Document):
    official_name: str
    channel_name: str
    emoji: str | None
    aliases: list[str]
    tourney_date: datetime
    open_days: int
    closed_days: int
    voters: list[int]  # FIXME: is this a list of ids? if so, are they str or ints?
    status: Literal["voting", "open", "archived"]  # FIX: Are there any more statuses?

    class Settings:
        name = "invitationals"
        use_cache = True
