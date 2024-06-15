from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

import discord
from discord import app_commands
from discord.ext import commands

import commandchecks
import src.discord.globals
from env import env
from src.discord.globals import (
    EMOJI_LOADING,
    ROLE_STAFF,
    ROLE_VIP,
)
from src.mongo.models import Event

if TYPE_CHECKING:
    from bot import PiBot


class StaffEvents(commands.Cog):
    def __init__(self, bot: PiBot):
        self.bot = bot

    event_commands_group = app_commands.Group(
        name="event",
        description="Updates the bot's list of events.",
        guild_ids=env.slash_command_guilds,
        default_permissions=discord.Permissions(manage_roles=True),
    )

    @event_commands_group.command(
        name="add",
        description="Staff command. Adds a new event.",
    )
    @app_commands.checks.has_any_role(ROLE_STAFF, ROLE_VIP)
    @app_commands.describe(
        event_name="The name of the new event.",
        event_aliases="The aliases for the new event. Format as 'alias1, alias2'.",
    )
    async def event_add(
        self,
        interaction: discord.Interaction,
        event_name: str,
        event_aliases: str | None = None,
    ):
        # Check for staff permissions
        commandchecks.is_staff_from_ctx(interaction)

        # Send user notice that process has begun
        await interaction.response.send_message(
            f"{EMOJI_LOADING} Attempting to add `{event_name}` as a new event...",
        )

        # Check to see if event has already been added.
        if event_name in [e.name for e in src.discord.globals.EVENT_INFO]:
            return await interaction.edit_original_response(
                content=f"The `{event_name}` event has already been added.",
            )

        # Construct dictionary to represent event; will be stored in database
        # and local storage
        aliases_array = []
        if event_aliases:
            aliases_array = re.findall(r"\w+", event_aliases)
        new_dict = Event(name=event_name, aliases=aliases_array, emoji=None)

        # Add dict into events container
        await new_dict.insert()
        src.discord.globals.EVENT_INFO.append(new_dict)

        # Create role on server
        server = self.bot.get_guild(env.server_id)
        assert isinstance(server, discord.Guild)
        await server.create_role(
            name=event_name,
            color=discord.Color(0x82A3D3),
            reason=f"Created by {interaction.user!s} using /eventadd with Pi-Bot.",
        )

        # Notify user of process completion
        await interaction.edit_original_response(
            content=f"The `{event_name}` event was added.",
        )

    @event_commands_group.command(
        name="remove",
        description="Removes an event's availability and optionally, its role from all users.",
    )
    @app_commands.checks.has_any_role(ROLE_STAFF, ROLE_VIP)
    @app_commands.describe(
        event_name="The name of the event to remove.",
        delete_role="Whether to delete the event role from all users. 'no' allows role to remain.",
    )
    async def event_remove(
        self,
        interaction: discord.Interaction,
        event_name: str,
        delete_role: Literal["no", "yes"] = "no",
    ):
        # Check for staff permissions
        commandchecks.is_staff_from_ctx(interaction)

        # Send user notice that process has begun
        await interaction.response.send_message(
            f"{EMOJI_LOADING} Attempting to remove the `{event_name}` event...",
        )

        # Check to make sure event has previously been added
        event_not_in_list = event_name not in [
            e.name for e in src.discord.globals.EVENT_INFO
        ]

        # Check to see if role exists on server
        server = self.bot.get_guild(env.server_id)
        potential_role = discord.utils.get(server.roles, name=event_name)

        if event_not_in_list and potential_role:
            # If no event in list and no role exists on server
            return await interaction.edit_original_response(
                content=f"The `{event_name}` event does not exist.",
            )

        # If staff member has selected to delete role from all users, delete role entirely
        if delete_role == "yes":
            server = self.bot.get_guild(env.server_id)
            role = discord.utils.get(server.roles, name=event_name)
            assert isinstance(role, discord.Role)
            await role.delete()
            if event_not_in_list:
                return await interaction.edit_original_response(
                    content=f"The `{event_name}` role was completely deleted from the server. All members with the role no longer have it.",
                )

        # Complete operation of removing event
        event = next(e for e in src.discord.globals.EVENT_INFO if e.name == event_name)
        await event.delete()
        src.discord.globals.EVENT_INFO.remove(event)

        # Notify staff member of completion
        if delete_role == "yes":
            await interaction.edit_original_response(
                content=f"The `{event_name}` event was deleted entirely. The role has been removed from all users, "
                f"and can not be added to new users. ",
            )
        else:
            await interaction.edit_original_response(
                content=f"The `{event_name}` event was deleted partially. Users who have the role currently will keep "
                f"it, but new members can not access the role.\n\nTo delete the role entirely, re-run the "
                f"command with `delete_role = yes`. ",
            )


async def setup(bot: PiBot):
    await bot.add_cog(StaffEvents(bot))
