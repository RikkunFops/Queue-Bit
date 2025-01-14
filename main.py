import os
import settings
import discord
from discord import *
from discord.ext import commands
from discord import app_commands
import time 
from dotenv import load_dotenv
from cogs.guild import GuildWrapper
from dbaccess import getList

standard_logger = settings.logging.getLogger("discord")
error_logger = settings.logging.getLogger("bot")

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('GUILD_TOKEN')

discIntents = Intents.all()
discIntents.members = True
discIntents.message_content = True
discIntents.guilds = True
discClient = commands.Bot(command_prefix='!', intents=discIntents)
GuildManager = GuildWrapper(discClient)


@discClient.event
async def on_ready():    
    try: 
        global GuildManager 
        await discClient.add_cog(GuildWrapper(discClient))
        
        
        synced = await discClient.tree.sync()
        standard_logger.info(f"Synced: {len(synced)} commands")
        loadDict = await getList()
        GuildManager.loadGuilds(loadDict)
        for guild in discClient.guilds:
             GuildManager.newGuild(guild)
    except Exception as e:
        standard_logger.error(f"Failed to sync: {e}")


@discClient.event
async def on_guild_join(guild: discord.Guild):
        standard_logger.info(f"I joined a server! {guild.name} | {guild.id}")
        GuildManager.newGuild(guild)
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
            mem = entry.user
            if entry.target.id == discClient.user.id:
                if mem == guild.owner:
                    await mem.send("Thank you for inviting me. \nHi, I'm QuBit! \nI'm a bot designed to help you and your members matchmake and queue up for games. \nJoin the support server at https://discord.gg/keAWNkTg for help and updates.")
                else:
                        await mem.send("Thank you for inviting me")
                        await guild.owner.send("I was added to your server! \nHi, I'm QuBit! \nI'm a bot designed to help you and your members matchmake and queue up for games. \nJoin the support server at https://discord.gg/keAWNkTg for help and updates.")

@discClient.hybrid_command(
        name="support",
        brief="Get support",
        description="Get details on how to find bot support",
        )
async def support(ctx):
    await ctx.send("You can get support from @RikkunDev in https://discord.gg/keAWNkTg. \nPlease remember to be patient and respectful.", ephemeral=True)   

@discClient.hybrid_command()
async def ping(ctx : commands.Context): 
    await ctx.send(f"Responded <t:{ int(time.mktime(ctx.interaction.created_at.timetuple()))}:T> ago")




discClient.run(TOKEN, root_logger=True)
