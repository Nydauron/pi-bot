from abc import ABC, abstractmethod
from enum import Enum

import discord
from typing import Dict, Union, Any
from bot import PiBot

from pydantic import BaseModel

class Action(Enum):
    MUTE = 1
    UNMUTE = 2

class CronAction(BaseModel, ABC):
    action_type: Action
    data: Dict[str, Any]

    class Config:
        allow_mutation = False
        arbitrary_types_allowed = True

    @abstractmethod
    async def exec(self, bot: PiBot):
        pass

class MuteAction(CronAction):
    action_type = Action.MUTE

    def __init__(self, user: Union[discord.User, int]): #discord.User
        data = {
            "data": {
                "user": user.id if isinstance(user, discord.User) else user
            }
        }
        super().__init__(**data)

    async def exec(self, bot: PiBot):
        # calls the either bot.dispatch or some other coroutine
        print("executed task!")

class UnmuteAction(CronAction):
    action_type = Action.UNMUTE

    def __init__(self, user: Union[discord.User, int]):
        data = {
            "data": {
                "user":  user.id if isinstance(user, discord.User) else user
            }
        }
        super().__init__(**data)

    async def exec(self, bot: PiBot):
        # calls the either bot.dispatch or some other coroutine
        print("executed task 2!")
