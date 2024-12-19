import os
import threading
import discord
from types import *
from discord import *
from discord.ext import commands
from discord import app_commands
from classes import QbGuild, Queue, Client
import asyncio

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
            discordGuild : QbGuild = self.bot.get_guild(guild_id)

            if discordGuild:
                # Create a Guild instance
                guild_instance = QbGuild(discordGuild, self.bot)
                print(f"Loading {guild_instance.discGuild.name}")
                # Add queues to the Guild instance if available
                if 'queues' in guild_data:
                    print(f"Listing queues in {guild_instance.discGuild.name}\n Queue name | Queue type | Queue ID")
                    for queue_data in guild_data['queues']:
                        queueId = queue_data['QueueId']
                        queueName = queue_data['QueueName']
                        queueType = queue_data['QueueType']
                        
                        newQueue = Queue(guild=discordGuild, name=queueName, type=queueType, identifier=queueId)
                        print(f"{newQueue.QueueName:^12}|{newQueue.QueueType:^12}|{newQueue.QueueID:^12}")
                        guild_instance.GuildQueues.append(newQueue)
                        

                # Add the guild instance to the GuildList
                GuildList.append(guild_instance)
    def newGuild(self, newGuild):
        for checkGuild in GuildList:
            if newGuild.id == checkGuild.discGuild.id:
                return
        
        newGuild = QbGuild(newGuild, self.bot)
        GuildList.append(newGuild)
        print(f"Added new guild: {GuildList[len(GuildList)-1].discGuild.name}")
    def checkUserQueues(self, client : Client):
        guildToSearch = client.qbGuild
        discGuild = guildToSearch.discGuild
        for queues in guildToSearch.GuildQueues:
            for user in queues.PeopleInQueue:
                if user.user == client.user:
                    return True
        return False
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
        
        newClient = Client(ctx.author, queueToJoin, ctx, guildToList)

        if not queueToJoin:
            await ctx.send("Couldn't join the queue! Are you sure this queue exists?", ephemeral=True)
            return
        
        if self.checkUserQueues(newClient):
            await ctx.send("You're already queuing! Leave the current queue before requeuing with /leavequeue.", ephemeral=True)
            return
        else:
            queueToJoin.PeopleInQueue.append(newClient)
            if len(queueToJoin.PeopleInQueue) != queueToJoin.MaxSize*5:
                await ctx.send(f"You've joined {queueToJoin.QueueName}! \nThere aren't many people, though. \nThis may take a moment! {len(queueToJoin.PeopleInQueue)}", ephemeral=True)
            else:
                await ctx.send(f"You've joined {queueToJoin.QueueName}! Shouldn't take long. {len(queueToJoin.PeopleInQueue)}", ephemeral=True)      
            await queueToJoin.tryQueue()
    @joinQueue.autocomplete('name')
    async def queuename_autocomplete(
        self, 
        interaction : discord.Interaction,
        current : str
    ) -> list[app_commands.Choice[str]]:
        queueNames = []
        guildToList : QbGuild = self.findMatchingGuild(interaction.guild)
        for queue in guildToList.GuildQueues:
            name = queue.QueueName
            type = queue.QueueType
            queueNames.append(queue.QueueName)
        return [ app_commands.Choice(name=name, value=name) 
            for name in queueNames if current.lower() in name.lower()]
    @commands.hybrid_command(
            name="leavequeue",
            description="Leave the current queue you are waiting in."
    )
    async def leaveQueue(self, ctx):
        guildToUse : QbGuild = self.findMatchingGuild(ctx.guild)
        for queues in guildToUse.GuildQueues:
            for users in queues.PeopleInQueue:
                if ctx.author == users.user:
                    await queues.removeFromList(users)
                    await ctx.send(f"You have left the queue: {queues.QueueName}.", ephemeral=True)
                    return
        await ctx.send(f"You aren't in a queue!")
    @commands.hybrid_command(
        name="listqueues",
        description = "List all queues for the server"
    )
    async def listQueue(self, ctx):
        listGuildQueues = ''
        guildToList : QbGuild = self.findMatchingGuild(ctx.guild)
        print(type(guildToList))
        for queue in guildToList.GuildQueues:
            listGuildQueues += f'{queue.QueueName:<8}| {len(queue.PeopleInQueue)} people in queue\n'
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
