"""
Contains all database models
"""

from beanie import Document


class Event(Document):
    name: str
    aliases: list[str]
    emoji: str | None

    class Settings:
        name = "events"
        use_cache = True
