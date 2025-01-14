
from types import *
from discord import *
from discord.ext import commands


async def is_admin(ctx : commands.Context ):
    return ctx.author.guild_permissions.administrator