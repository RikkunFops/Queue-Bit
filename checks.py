
from discord.ext import commands

async def is_admin(ctx: commands.Context):
    """Check if the user has administrator permissions."""
    return ctx.author.guild_permissions.administrator

def owner_or_permissions(**perms):
    """Check for owner or admin permissions"""
    original = commands.has_permissions(**perms).predicate
    async def extended_check(ctx):
        if ctx.guild is None:
            return False
        return ctx.guild.owner_id == ctx.author.id or await original(ctx)
    return commands.check(extended_check)
