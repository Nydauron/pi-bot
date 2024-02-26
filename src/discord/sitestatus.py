import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
import httpx
from discord import Embed, app_commands
from discord.ext import commands, tasks
from icmplib import async_ping

from bot import PiBot
from commandchecks import is_in_bot_spam
from src.discord.globals import SLASH_COMMAND_GUILDS
from src.discord.sitestatusmodels import (
    AggregateStatus,
    AggregateStatusList,
    SiteHTTPResult,
    SiteStatusResult,
)

logger = logging.getLogger(__name__)


STATUS_GOOD_SYMBOL = "🟢"
STATUS_BAD_SYMBOL = "🔴"
STATUS_WARN_SYMBOL = "🟡"
STATUS_OFFLINE_SYMBOL = "⚫"


class SiteStatus(commands.Cog, name="SiteStatus"):
    """
    Cog for managing fun application commands and needed functionality.
    """

    # pylint: disable=no-self-use

    def __init__(self, bot: PiBot):
        self.bot = bot
        self.check_site_status.start()

    # FIXME: Fix magic numbers
    @app_commands.command(description="Check scioly.org site uptime")
    @app_commands.guilds(*SLASH_COMMAND_GUILDS)
    @app_commands.check(is_in_bot_spam)
    async def sitestatus(
        self,
        interaction: discord.Interaction,
    ):
        """
        Generates a site status embed report showing the past few hours
        """

        # TODO: Probably add an aggregation here to limit to 8 elements per group
        all_status_results = (
            await SiteStatusResult.find(
                SiteStatusResult.dt >= datetime.now(timezone.utc) - timedelta(hours=4),
            )
            .aggregate(
                [
                    {
                        "$group": {
                            "_id": "$domain",
                            "results": {"$push": {"ping": "$ping", "http": "$http"}},
                            "updatedAt": {"$max": "$dt"},
                        },
                    },
                ],
                projection_model=AggregateStatusList,
            )
            .to_list()
        )

        latest_results: dict[str, list[AggregateStatus | None]] = {}
        updatedAt = max([r.updatedAt for r in all_status_results])
        for results in all_status_results:
            latest_results[results.domain] = results.results

        status_embed = discord.Embed(title="scioly.org Site Status (Last 4 Hours)")

        def construct_status_field(embed: Embed, domain: str):
            EMBED_FIELD_LENGTH = 8
            status_string = ""
            uptime_num = 0
            if domain in latest_results:
                for result in latest_results[domain]:
                    if result is None:
                        status_string += STATUS_OFFLINE_SYMBOL
                        continue
                    if (
                        result.ping is None
                        or result.http is None
                        or result.http.status_code >= 500  # Server error
                    ):
                        status_string += STATUS_BAD_SYMBOL
                        continue
                    if (
                        result.http.status_code >= 400
                    ):  # Client error. Probably need to update detection code
                        status_string += STATUS_WARN_SYMBOL
                        continue
                    status_string += STATUS_GOOD_SYMBOL
                    uptime_num += 1

            if len(status_string) < EMBED_FIELD_LENGTH:
                status_string = (
                    STATUS_OFFLINE_SYMBOL * (EMBED_FIELD_LENGTH - len(status_string))
                ) + status_string
            embed.add_field(
                name=domain,
                value="{}\nUptime: {:.1f}%".format(
                    status_string,
                    uptime_num / len(latest_results[domain]) * 100,
                ),
                inline=True,
            )

        construct_status_field(status_embed, "scioly.org")
        construct_status_field(status_embed, "w.scioly.org")
        construct_status_field(status_embed, "f.scioly.org")
        status_embed.set_footer(
            text="Admins are automatically contacted when a site goes down. If "
            "a site has been down for multiple days, please contact an admin.",
        )
        status_embed.timestamp = updatedAt
        await interaction.response.send_message(embed=status_embed)

    # FIXME: Change interval to 10 minutes
    @tasks.loop(minutes=30)
    async def check_site_status(self):
        logger.info("Running site checker")
        domains = {
            "scioly.org": [],
            "f.scioly.org": ["https://scioly.org/forums/"],
            "w.scioly.org": ["https://scioly.org/wiki/"],
        }

        now = datetime.now(timezone.utc)
        res = await asyncio.gather(
            *[self.check_site(domain, domains[domain], now) for domain in domains],
        )
        ack = await SiteStatusResult.insert_many(res)
        logger.info("New site statuses saved")
        logger.info(ack)

    async def check_site(
        self,
        domain: str,
        alternateHTTPURLs: list[str],
        current_time: datetime = datetime.now(timezone.utc),
    ) -> SiteStatusResult:
        host = await async_ping(domain, privileged=False)
        if not host.is_alive:
            return SiteStatusResult(
                domain=domain,
                dt=current_time,
                ping=None,
                http=None,
            )
        logger.info(f"Pinged {domain}")

        http_urls = alternateHTTPURLs.copy()
        http_urls.insert(0, f"https://{domain}")

        HTTP_TIMEOUT = 20
        http_tasks = [
            asyncio.create_task(self.check_http(url, HTTP_TIMEOUT)) for url in http_urls
        ]
        done, pending = await asyncio.wait(
            http_tasks,
            return_when=asyncio.FIRST_COMPLETED,
            timeout=HTTP_TIMEOUT + 3,  # Allow async tasks to raise exceptions
        )

        for p in pending:
            p.cancel()

        if len(done) == 0:
            return SiteStatusResult(
                domain=domain,
                dt=current_time,
                ping=host.avg_rtt,
                http=None,
            )

        completed_http_task = done.pop()
        http_result = await completed_http_task
        return SiteStatusResult(
            domain=domain,
            dt=current_time,
            ping=host.avg_rtt,
            http=http_result,
        )

    async def check_http(self, url: str, timeout: float) -> SiteHTTPResult:
        async with httpx.AsyncClient() as client:
            try:
                http_res = await client.head(url, timeout=timeout)
                logger.info(f"Received HTTP response from {url}")
                return SiteHTTPResult(url=url, status_code=http_res.status_code)
            except httpx.TimeoutException as e:
                logger.warning(e)
                raise asyncio.TimeoutError


async def setup(bot: PiBot):
    """
    Sets up the site status uptime cog.

    Args:
        bot (PiBot): The bot to use with the cog.
    """
    await bot.add_cog(SiteStatus(bot))
