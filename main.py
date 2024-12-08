import os
import discord
from discord import *
from discord.ext import commands
from dotenv import load_dotenv
from commProcessor import CommandProcessor, Command

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('GUILD_TOKEN')

discIntents = Intents.default()
discIntents.members = True
discIntents.message_content = True
discClient = commands.Bot(command_prefix='/', intents=discIntents)

comProc = CommandProcessor(1)

prefix = '/'

@discClient.event
async def on_ready():
    print(f'{discClient.user} has Conntected to discord')
    newPresence = discord.Game('API in Development')
    await discClient.change_presence(status=discord.Status.idle, activity=newPresence)

    for guild in discClient.guilds:
        print(guild.id, guild.name)


@discClient.tree.context_menu(name='Show Join Date')
async def getJoinDate(interaction: discord.Interaction, member : discord.Member):
    await interaction.response.send_message(f"Member joined: {member.joined_at}", ephemeral= True)


    



discClient.run(TOKEN)