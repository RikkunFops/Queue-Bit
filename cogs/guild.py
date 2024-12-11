import os
import threading
import discord
from discord import *
from discord.ext import commands
from discord import app_commands
from classes import Guild, Queue


import atexit
from dbaccess import endProgram

GuildList : Guild = []

class GuildWrapper(commands.Cog):
    def __init__(self, bot : commands.Bot):
        self.bot = bot

    def findMatchingGuild(self, guildObj : discord.Guild):
        try:
            for guilds in GuildList:
                if guilds.discGuild == guildObj:
                    return guilds
                else: pass
        except:
            print("Could not find matching guild")    

    def loadGuilds(self, loadList):
        for guilds in loadList:
            print(f"Loading {self.bot.get_guild(guilds['GuildId']).name}")
            GuildList.append(Guild(self.bot.get_guild(guilds['GuildId'])))

    def newGuild(self, newGuild):
        for checkGuild in GuildList:
            if newGuild.id == checkGuild.discGuild.id:
                print("Already enumerated!!")
                return
        
        newGuild = Guild(newGuild, self.bot)
        GuildList.append(newGuild)
        print(f"Added new guild: {GuildList[len(GuildList)-1].discGuild.name}")

    @commands.hybrid_command(
            name="addqueue",
            description = "Create a new queue"
    )
    async def addQueue(self, ctx, *, queuename : str, queuetype : str):
        Successful = None
        queuebitGuild = self.findMatchingGuild(ctx.guild) 
        
        try:
            newIdentifier = len(queuebitGuild.GuildQueues)
            newQueue = Queue(guild=queuebitGuild, name=queuename, type=queuename, identifier=newIdentifier)
            queuebitGuild.GuildQueues.append(newQueue)
            Successful = True
        except Exception as e:
            Successful = False
            print(f"Error {e}")
        finally:
            if Successful:
                await ctx.send(f"Successfully added list {queuebitGuild.GuildQueues[len(queuebitGuild.GuildQueues)-1].QueueName}"),

    @commands.hybrid_command(
        name="listqueues",
        description = "List all queues for the server"
    )
    async def listQueue(self, ctx):
        listGuildQueues = ''
        guildToList = self.findMatchingGuild(ctx.guild)
        for queue in guildToList.GuildQueues:
            listGuildQueues += f'{queue.QueueName}\n'
        await ctx.send(listGuildQueues)





    '''@discClient.hybrid_command(
        name="add admin",
        description="Add a new administrator to the guild")
        '''


async def setup(bot):
    await bot.add_cog(GuildWrapper(bot))

atexit.register(endProgram, GuildList)
