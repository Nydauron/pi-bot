"""
Contains all database models
"""

from beanie import Document


class Censor(Document):
    words: list[str]
    emojis: list[str]

    class Settings:
        name = "censor"
        use_cache = True
