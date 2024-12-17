import os

import discord
from discord import *
from discord.ext import commands
from discord import app_commands

from dotenv import load_dotenv

from cogs.guild import GuildWrapper
from cogs.guild import Guild

from dbaccess import getList


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
        print(f"Synced {len(synced)} commands")
        loadList = await getList()
        GuildManager.loadGuilds(loadList)
        for guilds in discClient.guilds:
             GuildManager.newGuild(guilds)
    except Exception as e:
        print(f"Failed to sync: {e}")

@discClient.event
async def on_guild_join(guild: discord.Guild):
        print("I joined a server!")
        GuildManager.newGuild(guild)
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
            mem = entry.user
            if entry.target.id == discClient.user.id:
                if mem == guild.owner:
                    await mem.send("Thank you for inviting me. \nHi, I'm QuBit! \nI'm a bot designed to help you create queues for members to join and band together.")
                else:
                        await mem.send("Thank you for inviting me")
                        await guild.owner.send("I was added to your server! \nHi, I'm QuBit! \nI'm a bot designed to help you create queues for members to join and band together.")

@discClient.hybrid_command(
        name="support",
        description="Get details on how to find bot support",
        )
async def support(ctx):
    await ctx.send("You can get support from @RikkunFops. \nPlease remember to be patient and respectful.", ephemeral=True)

@discClient.hybrid_command(
          name="update",
          description="secret dev command shhh"
)
async def update(ctx):
    synced = await discClient.tree.sync()
    if synced:
        await ctx.send("Successfully updated commands")
    else:
        await ctx.send("Could not update")
     

@discClient.hybrid_command()
async def ping(ctx): 
    await ctx.send("pong")


discClient.run(TOKEN)