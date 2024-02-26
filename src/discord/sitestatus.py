import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

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
STATUS_MAJOR_OUTAGE_SYMBOL = "🔴"
STATUS_MINOR_OUTAGE_SYMBOL = "🟡"
STATUS_WARN_SYMBOL = ":warning:"
STATUS_OFFLINE_SYMBOL = "⚫"
STATUS_POLLING_RATE = timedelta(minutes=10)

StatusHistoryLength = Literal[
    "4 hours",
    "6 hours",
    "12 hours",
    "1 day",
    "2 days",
    "4 days",
    "8 days",
]
UptimeResult = Literal["good", "bad", "client_error"]


def history_length_to_time_delta(length: StatusHistoryLength) -> timedelta:
    match length:
        case "4 hours":
            return timedelta(hours=4)
        case "6 hours":
            return timedelta(hours=6)
        case "12 hours":
            return timedelta(hours=12)
        case "1 day":
            return timedelta(days=1)
        case "2 days":
            return timedelta(days=2)
        case "4 days":
            return timedelta(days=4)
        case "8 days":
            return timedelta(days=8)


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
        history_length: StatusHistoryLength,
    ):
        """
        Generates a site status embed report showing the past few hours
        """

        lookback_range = history_length_to_time_delta(history_length)
        # FIXME: Gets stuck on db call if there are 0 entries
        all_status_results = (
            await SiteStatusResult.find(
                SiteStatusResult.dt >= datetime.now(timezone.utc) - lookback_range,
            )
            .aggregate(
                [
                    {"$sort": {"dt": 1}},
                    {
                        "$group": {
                            "_id": "$domain",
                            "results": {
                                "$push": {
                                    "ping": "$ping",
                                    "http": "$http",
                                    "recordedAt": "$dt",
                                },
                            },
                        },
                    },
                ],
                projection_model=AggregateStatusList,
            )
            .to_list()
        )

        latest_results: dict[str, list[AggregateStatus]] = {}
        updatedAt = datetime.now(timezone.utc)
        for results in all_status_results:
            latest_results[results.domain] = results.results

        SECONDS_TO_HOURS = 60 * 60
        HOURS_TO_DAYS = 24
        SHOW_HOURS_THRES = 48
        history_hours = int(round(lookback_range.total_seconds() / SECONDS_TO_HOURS))
        if history_hours <= SHOW_HOURS_THRES:
            history_duration_string = f"{history_hours} hours"
        else:
            history_duration_string = f"{history_hours / HOURS_TO_DAYS} days"
        status_embed = discord.Embed(
            title=f"scioly.org Site Uptime Status (Last {history_duration_string})",
        )

        EMBED_FIELD_LENGTH = 24

        def construct_status_field(embed: Embed, domain: str):
            CIRCLE_INTERVAL = lookback_range / EMBED_FIELD_LENGTH
            status_string = ""
            uptime_num = 0
            circle_datetimes = [
                updatedAt - lookback_range + CIRCLE_INTERVAL * n
                for n in range(1, EMBED_FIELD_LENGTH + 1)
            ]
            latest_uptime_status = None
            if domain in latest_results:
                total_results = len(latest_results[domain])
                latest_uptime_status = latest_results[domain][
                    -1
                ]  # FIXME: Prone to out-of-bounds err
                for idx, circle_dt in enumerate(circle_datetimes):
                    if len(latest_results[domain]) == 0:
                        # Add offline circles and break
                        status_string += STATUS_OFFLINE_SYMBOL * (
                            EMBED_FIELD_LENGTH - idx
                        )
                        break
                    oldest_statuses: list[AggregateStatus] = []
                    while (
                        len(latest_results[domain]) > 0
                        and latest_results[domain][0].recordedAt <= circle_dt
                    ):
                        oldest_statuses.append(latest_results[domain].pop(0))

                    if len(oldest_statuses) == 0:
                        status_string += STATUS_OFFLINE_SYMBOL
                        continue

                    # If all entries are ok, then the icon is Green
                    # If at least one entry is minor or major outage
                    good_status = 0
                    bad_status = 0
                    client_error_status = 0
                    for status in oldest_statuses:
                        result = SiteStatus.uptime_status(status)
                        match result:
                            case "good":
                                good_status += 1
                            case "bad":
                                bad_status += 1
                            case "client_error":
                                client_error_status += 1

                    uptime_num += good_status
                    if bad_status == 0 and good_status == 0 and client_error_status > 0:
                        status_string += STATUS_WARN_SYMBOL
                        continue
                    if bad_status == 0 and good_status > 0:
                        status_string += STATUS_GOOD_SYMBOL
                        continue
                    if good_status > bad_status:
                        status_string += STATUS_MINOR_OUTAGE_SYMBOL
                        continue
                    if bad_status >= good_status:
                        status_string += STATUS_MAJOR_OUTAGE_SYMBOL
                        continue

            if len(status_string) < EMBED_FIELD_LENGTH:
                status_string = (
                    STATUS_OFFLINE_SYMBOL * (EMBED_FIELD_LENGTH - len(status_string))
                ) + status_string

            latest_result_str = STATUS_OFFLINE_SYMBOL
            if latest_uptime_status:
                latest_result = SiteStatus.uptime_status(latest_uptime_status)
                latest_result_str = "{}<t:{}:t>".format(
                    SiteStatus.uptime_icon(latest_result),
                    int(latest_uptime_status.recordedAt.timestamp()),
                )
            embed.add_field(
                name="{} - {} - Uptime: {:.1f}%".format(
                    domain,
                    latest_result_str,
                    uptime_num / total_results * 100,
                ),
                value=f"{status_string}\n",
                inline=False,
            )

        construct_status_field(status_embed, "scioly.org")
        construct_status_field(status_embed, "w.scioly.org")
        construct_status_field(status_embed, "f.scioly.org")

        SHOW_CIRCLE_MINUTES_THRES = 60
        MINUTES_TO_HOURS = 60
        circle_time = history_hours / EMBED_FIELD_LENGTH * MINUTES_TO_HOURS
        if circle_time <= SHOW_CIRCLE_MINUTES_THRES:
            circle_duration_string = f"{round(circle_time):.0f} minutes"
        else:
            circle_duration_string = (
                f"{round(circle_time / MINUTES_TO_HOURS):.0f} hours"
            )
        status_embed.description = (
            f"Each circle represents {circle_duration_string} of time\n"  # TODO: Change to say median once it does do that
            f"{STATUS_OFFLINE_SYMBOL} = No data\n"
            f"{STATUS_GOOD_SYMBOL} = Operational\n"
            f"{STATUS_MAJOR_OUTAGE_SYMBOL} = Major outage. Host went down for a majority of the interval\n"
            f"{STATUS_MINOR_OUTAGE_SYMBOL} = Minor outage. Host went down for a small portion of the interval\n"
            f"{STATUS_WARN_SYMBOL} = Unexpected response. Indicates a problem with status polling"
        )
        status_embed.set_footer(
            text="Admins are automatically contacted when a site goes down. If "
            "a site has been down for multiple days, please contact an admin. "
            "Please be respectful towards mods and admins as they are volunteers.",
        )
        status_embed.timestamp = updatedAt
        await interaction.response.send_message(embed=status_embed)

    @classmethod
    def uptime_status(cls, uptime_report: AggregateStatus) -> UptimeResult:
        if (
            uptime_report.ping is None
            or uptime_report.http is None
            or uptime_report.http.status_code >= 500  # Server error
        ):
            return "bad"
        if (
            uptime_report.http.status_code >= 400
        ):  # Client error. Probably need to update detection code
            return "client_error"
        return "good"

    @classmethod
    def uptime_icon(cls, result: UptimeResult) -> str:
        match result:
            case "good":
                return STATUS_GOOD_SYMBOL
            case "bad":
                return STATUS_MAJOR_OUTAGE_SYMBOL
            case "client_error":
                return STATUS_WARN_SYMBOL

    @tasks.loop(
        time=[
            (
                datetime(
                    month=1,
                    day=1,
                    year=2024,
                    hour=0,
                    minute=0,
                    second=0,
                    tzinfo=timezone.utc,
                )
                + STATUS_POLLING_RATE * n
            ).timetz()
            for n in range(timedelta(hours=24) // STATUS_POLLING_RATE)
        ],
    )
    async def check_site_status(self):
        logger.info("Running site uptime checker")
        domains = {
            "scioly.org": [],
            "f.scioly.org": ["https://scioly.org/forums/"],
            "w.scioly.org": ["https://scioly.org/wiki/"],
        }

        now = datetime.now(timezone.utc)
        res = await asyncio.gather(
            *[self.check_site(domain, domains[domain], now) for domain in domains],
        )
        await SiteStatusResult.insert_many(res)
        logger.info("New site uptime results saved")

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
