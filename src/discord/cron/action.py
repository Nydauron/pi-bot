from abc import ABC, abstractmethod
from enum import Enum

import discord
from typing import Dict, Union, Any
from bot import PiBot

class Action(Enum):
    MUTE = 1
    UNMUTE = 2

import asyncio
from beanie import Document
from datetime import datetime, timedelta
from src.discord.globals import SERVER_TZ

class CronJob(Document, ABC):
    action_type: Action
    data: Dict[str, Any]

    exec_at: datetime

    class Settings:
        name = "cron"

    async def wait(self, bot: PiBot):
        # When exec is called, we are assuming that self.exec_datetime - datetime.now() is <= 30 days

        # Since there is an upper limit of 48 days for asyncio.sleep(), we need to find a way to circumvent this for larger wait times
        # An easy solution might be to just poll once every 30 days to see if there are any upcoming jobs and schedule them

        diff = self.exec_at - SERVER_TZ.localize(datetime.now())
        while diff > timedelta():
            await asyncio.sleep(diff.total_seconds())
            diff = self.exec_at - SERVER_TZ.localize(datetime.now())

        await self.exec(bot)

    @abstractmethod
    async def exec(self, bot: PiBot):
        pass

class MuteAction(CronJob):
    action_type = Action.MUTE

    @staticmethod
    def new(user: Union[discord.User, int], exec_at: datetime):
        data = {
            "data": {
                "user":  user.id if isinstance(user, discord.User) else user
            },
            "exec_at": exec_at
        }
        return MuteAction(**data)

    async def exec(self, bot: PiBot):
        # calls the either bot.dispatch or some other coroutine
        print("executed task!")

class UnmuteAction(CronJob):
    action_type = Action.UNMUTE

    @staticmethod
    def new(user: Union[discord.User, int], exec_at: datetime):
        data = {
            "data": {
                "user":  user.id if isinstance(user, discord.User) else user
            },
            "exec_at": exec_at
        }
        return UnmuteAction(**data)

    async def exec(self, bot: PiBot):
        # calls the either bot.dispatch or some other coroutine
        print("executed task 2!")

ACTION_BINDINGS = {
    Action.MUTE: MuteAction,
    Action.UNMUTE: UnmuteAction
}
