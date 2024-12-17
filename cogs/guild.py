import os
import threading
import discord
from types import *
from discord import *
from discord.ext import commands
from discord import app_commands
from classes import QbGuild, Queue


import atexit
from dbaccess import endProgram

GuildList : QbGuild = []

class GuildWrapper(commands.Cog):
    def __init__(self, bot : commands.Bot):
        self.bot = bot

    def findMatchingGuild(self, guildObj : discord.Guild):
        try:
            for guilds in GuildList:
                if guilds.discGuild == guildObj:
                    
                    return guilds
                else: pass
            print(f"Could not find matching guild: {guildObj.name}")
        except:
            print("Could not find matching guild")    

    def loadGuilds(self, loadList):
        for guild_data in loadList:
            guild_id = guild_data['GuildId']
            discordGuild = self.bot.get_guild(guild_id)

            if discordGuild:
                print(f"Loading {discordGuild.name}")

                # Create a Guild instance
                guild_instance = QbGuild(discordGuild)

                # Add queues to the Guild instance if available
                if 'queues' in guild_data:
                    for queue_data in guild_data['queues']:
                        queueId = queue_data['QueueId']
                        queueName = queue_data['QueueName']
                        queueType = queue_data['QueueType']
                        
                        newQueue = Queue(guild=discordGuild, name=queueName, type=queueType, identifier=queueId)
                        print(f"We found {guild_instance.discGuild.name} has queue {queueName} | {queueType} | {queueId}")
                        guild_instance.GuildQueues.append(newQueue)


                # Add the guild instance to the GuildList
                GuildList.append(guild_instance)

    def newGuild(self, newGuild):
        for checkGuild in GuildList:
            if newGuild.id == checkGuild.discGuild.id:
                print("Already enumerated!!")
                return
        
        newGuild = QbGuild(newGuild, self.bot)
        GuildList.append(newGuild)
        print(f"Added new guild: {GuildList[len(GuildList)-1].discGuild.name}")

    def checkUserQueues(self, user : discord.User, queue : Queue, guild : QbGuild):
        try:            
            for queue in guild.GuildQueues:
                if user in queue.PeopleInQueue:
                    return True
        except Exception as e:
            print("Could not read guild queue data")
            print(f"{e}")
            return (False, 1)
                
        return (False, 0)

    @commands.hybrid_command(
            name="addqueue",
            description = "Create a new queue"
    )
    async def addQueue(self, ctx, *, name: str, queue_type: str):
        Successful = None
        queuebitGuild = self.findMatchingGuild(ctx.guild)
        
        try:
            newIdentifier = len(queuebitGuild.GuildQueues)
            newQueue = Queue(guild=queuebitGuild, name=name, type=queue_type, identifier=newIdentifier)
            if newQueue.QueueType.lower() not in ['lfg', 'support', 'matchmatching']:
                await ctx.send(f"Cannot make list, please select appropriate list type", ephemeral=True)
                return
            queuebitGuild.GuildQueues.append(newQueue)
            Successful = True
        except Exception as e:
            Successful = False
            print(f"Error {e}")
        finally:
            if Successful:
                await ctx.send(f"Successfully added list {queuebitGuild.GuildQueues[-1].QueueName}", ephemeral=True)
    
    @commands.hybrid_command(
            name="joinqueue",
            description="Join a queue"
    )
    async def joinQueue(self, ctx, name):
        guildToList : QbGuild = self.findMatchingGuild(ctx.guild)
        queueToJoin : Queue = None
        for queue in guildToList.GuildQueues:
            if queue.QueueName.lower() == name.lower():
                queueToJoin = queue
                break
            else: 
                pass
        
        if not queueToJoin:
            await ctx.send("Couldn't join the queue! Are you sure this queue exists?", ephemeral=True)
            return
        
        if self.checkUserQueues(ctx.author, queueToJoin, guildToList):
            await ctx.send("You're already queuing! Leave the current queue before requeuing with /leavequeue.", ephemeral=True)
            return
        elif [1] != 0:
            queueToJoin.PeopleInQueue.append(ctx.author)
            if len(queueToJoin.PeopleInQueue) > queueToJoin.MaxSize*2:
                await ctx.send(f"You've joined {queueToJoin.QueueName}! \nThere aren't many people, though. \nThis may take a moment!", ephemeral=True)
            else:
                await ctx.send(f"You've joined {queueToJoin.QueueName}! Shouldn't take long.", ephemeral=True)
        else:
            await ctx.send("Couldn't join the queue due to an internal error! Seek help from support.", ephemeral=True)
    
    @joinQueue.autocomplete('name')
    async def queuename_autocomplete(
        self, 
        interaction : discord.Interaction,
        current : str
    ) -> list[app_commands.Choice[str]]:
        queueNames = []
        guildToList : QbGuild = self.findMatchingGuild(interaction.guild)
        for queue in guildToList.GuildQueues:
            queueNames.append(queue.QueueName)
        print(guildToList.GuildQueues[0].QueueName)
        return [ app_commands.Choice(name=name, value=name) 
            for name in queueNames if current.lower() in name.lower()]

    @commands.hybrid_command(
            name="leavequeue",
            description="Leave the current queue you are waiting in."
    )
    async def leaveQueue(self, ctx):
        guildToUse : QbGuild = self.findMatchingGuild(ctx.guild)
        for queues in guildToUse.GuildQueues:
            if ctx.author in queues.PeopleInQueue:
                queues.PeopleInQueue.remove(ctx.author)
                ctx.send(f"Removed you from the ")


    @commands.hybrid_command(
        name="listqueues",
        description = "List all queues for the server"
    )
    async def listQueue(self, ctx):
        listGuildQueues = ''
        guildToList : QbGuild = self.findMatchingGuild(ctx.guild)
        print(type(guildToList))
        for queue in guildToList.GuildQueues:
            listGuildQueues += f'{queue.QueueName}\n'
        try:
            if len(listGuildQueues) > 0:
                await ctx.send(listGuildQueues)
            else:
                await ctx.send("There are no queues! Create one with /addqueue")
            
        except Exception as e:
            print(f"Exception: {e}")

    @addQueue.autocomplete('queue_type')
    async def type_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        qTypes = ['LFG', 'Support', 'Matchmaking']
        return [
            app_commands.Choice(name=qType, value=qType)
            for qType in qTypes if current.lower() in qType.lower()
        ]




    '''@discClient.hybrid_command(
        name="add admin",
        description="Add a new administrator to the guild")
        '''


async def setup(bot):
    await bot.add_cog(GuildWrapper(bot))

atexit.register(endProgram, GuildList)
