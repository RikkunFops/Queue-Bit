import discord
from types import *
from discord import *
from discord.ext import commands
from discord import app_commands
from classes import QbGuild, Queue, Client 

async def is_admin(ctx : commands.Context ):
    return ctx.author.guild_permissions.administrator