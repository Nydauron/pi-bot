"""
Contains all database models
"""

from beanie import Document
from pydantic import BaseModel


class TagPermissions(BaseModel):
    launch_helpers: bool
    members: bool
    staff: bool


class Tag(Document):
    name: str
    permissions: TagPermissions
    output: str

    class Settings:
        name = "tags"
        use_cache = False
