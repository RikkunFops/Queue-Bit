
from discord.ext import commands

async def is_admin(ctx: commands.Context):
    """Check if the user has administrator permissions."""
    return ctx.author.guild_permissions.administrator