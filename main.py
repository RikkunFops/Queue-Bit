import os
import time
import settings
import discord
from discord.ext import commands
from dotenv import load_dotenv
from cogs.guild import GuildWrapper
from dbaccess import get_list

standard_logger = settings.logging.getLogger("discord")
error_logger = settings.logging.getLogger("bot")

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('GUILD_TOKEN')

disc_intents = discord.Intents.all()
disc_intents.members = True
disc_intents.message_content = True
disc_intents.guilds = True
disc_client = commands.Bot(command_prefix='!', intents=disc_intents)
guild_manager = GuildWrapper(disc_client)


@disc_client.event
async def on_ready():
    # pylint: disable=W0718
    """When the bot is ready."""
    await disc_client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Discord's Matchmaker"))
    try:
        await disc_client.add_cog(GuildWrapper(disc_client))
        synced = await disc_client.tree.sync()
        standard_logger.info("Synced: %d commands", len(synced))

        # Load guild data from the database
        load_dict = await get_list()  # Ensures compatibility with MySQL
        guild_manager.load_guilds(load_dict)

        # Initialize guilds in the client
        for guild in disc_client.guilds:
            guild_manager.new_guild(guild)

        standard_logger.info("Ready")
    except discord.DiscordException as e:
        error_logger.error("Discord exception occurred: %s", e)




@disc_client.event
async def on_guild_join(guild: discord.Guild):
    """ When the bot joins a guild """
    standard_logger.info("I joined a server! %s | %d", guild.name, guild.id)
    guild_manager.new_guild(guild)
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
        mem = entry.user
        if entry.target.id == disc_client.user.id:
            if mem == guild.owner:
                await mem.send(
                    "Thank you for inviting me. \nHi, I'm QuBit! \nI'm a bot designed to help you and your members matchmake and queue up for games. \nJoin the support server at https://discord.gg/qfNehTqwcH for help and updates."
                )
            else:
                await mem.send("Thank you for inviting me")
                await guild.owner.send(
                    "I was added to your server! \nHi, I'm QuBit! \nI'm a bot designed to help you and your members matchmake and queue up for games. \nJoin the support server at https://discord.gg/qfNehTqwcH for help and updates."
                )


@disc_client.hybrid_command(
    name="support",
    brief="Get support",
    description="Get details on how to find bot support",
)
async def support(ctx: commands.Context):
    """ Get support """
    await ctx.send(
        "You can get support from @RikkunDev in https://discord.gg/qfNehTqwcH. \nPlease remember to be patient and respectful.",
        ephemeral=True,
    )

@disc_client.hybrid_command(
        name="quickstart",
        brief="Learn the essential commands",
        description="Get a list of all the essential commands, and how to use them."
)
async def quickstart(ctx: commands.Context):
    """ Post the quickstart info """
    await ctx.send(
        "To add a queue, use /addqueue like this;\n     `/addqueue [queuename] [activity] [lobbysize]`\nTo join a queue, use\n      `/joinqueue [queuename]`\nTo subscribe to a global queue, use\n     `/subqueue [code]`\nTo register a queue globally, use\n      `/regqueue [queuename]`",
        ephemeral=True
    )

@disc_client.hybrid_command()
async def ping(ctx: commands.Context):
    """ Get the bot's latency """
    await ctx.send(f"Pinged <t:{int(time.mktime(ctx.interaction.created_at.timetuple()))}:T> ago")


disc_client.run(TOKEN, root_logger=True)
