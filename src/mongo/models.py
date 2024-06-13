"""
Contains all database models
"""

from beanie import Document


class Settings(Document):
    # TODO
    custom_bot_status_type: str
    custom_bot_status_text: str
    invitational_season: int

    class Settings:
        name = "settings"
        use_cache = True
