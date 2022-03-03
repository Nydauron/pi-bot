import discord
from discord.commands import slash_command

from discord.ext import commands
from discord.commands import Option, permissions
import commandchecks

from src.discord.globals import CENSOR, SLASH_COMMAND_GUILDS, INVITATIONAL_INFO, CHANNEL_BOTSPAM, CATEGORY_ARCHIVE, ROLE_AT, ROLE_MUTED, EMOJI_GUILDS, TAGS, EVENT_INFO, EMOJI_LOADING
from src.discord.globals import SERVER_ID, CHANNEL_WELCOME, ROLE_UC, ROLE_LH, ROLE_STAFF, ROLE_VIP

class StaffEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("Initialized staff events cog.")

    @discord.commands.slash_command(
        guild_ids = [SLASH_COMMAND_GUILDS],
        name = "eventadd",
        description = "Staff command. Adds a new event."
    )
    @permissions.has_any_role(ROLE_STAFF, ROLE_VIP, guild_id = SERVER_ID)
    async def event_add(self,
        ctx,
        event_name: Option(str, "The name of the new event.", required = True),
        event_aliases: Option(str, "The aliases for the new event. Format as 'alias1, alias2'.")
        ):
        commandchecks.is_staff_from_ctx(ctx)

        if event_name in [e['name'] for e in src.discord.globals.EVENT_INFO]:
            return await ctx.interaction.response.send_message(content = f"The `{event_name}` event has already been added.")

        aliases_array = re.findall(r'\w+', event_aliases)
        new_dict = {
            'name': event_name,
            'aliases': aliases_array
        }

        src.discord.globals.EVENT_INFO.append(new_dict)
        await insert("data", "events", new_dict)

        server = self.bot.get_guild(SERVER_ID)
        await server.create_role(
            name = event_name,
            color = discord.Color(0x82A3D3),
            reason = f"Created by {str(ctx.author)} using /eventadd with Pi-Bot."
            )
        await ctx.interaction.response.send_message(content = f"The `{event_name}` event was added.")

    @discord.commands.slash_command(
        guild_ids = [SLASH_COMMAND_GUILDS],
        name = 'eventremove',
        description = "Removes an event's availability and optionally, its role from all users."
    )
    @permissions.has_any_role(ROLE_STAFF, ROLE_VIP, guild_id = SERVER_ID)
    async def event_remove(self,
        ctx,
        event_name: Option(str, "The name of the event to remove.", required = True),
        delete_role: Option(str, "Whether to delete the event role from all users. 'no' allows role to remain.", choices = ["no", "yes"], default = "no", required = True)
        ):
        commandchecks.is_staff_from_ctx(ctx)

        if event_name not in [e['name'] for e in src.discord.globals.EVENT_INFO]:
            return await ctx.interaction.response.send_message(content = f"The `{event_name}` event does not exist.")

        if delete_role == "yes":
            server = self.bot.get_guild(SERVER_ID)
            role = discord.utils.get(server.roles, name = event_name)
            await role.delete()

        event = [e for e in src.discord.globals.EVENT_INFO if e['name'] == event_name][0]
        src.discord.globals.EVENT_INFO.remove(event)
        await delete("data", "events", event['_id'])
        await ctx.interaction.response.send_message(content = f"The `{event_name}` event was deleted.")

def setup(bot):
    bot.add_cog(StaffEvents(bot))
