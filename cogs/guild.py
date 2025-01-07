import os
import threading
import discord
from types import *
from discord import *
from discord.ext import commands
from discord import app_commands
from classes import QbGuild, Queue, Client, Party
import time
from checks import *
import datetime
from unittest.mock import MagicMock, AsyncMock
import settings
import atexit
from dbaccess import endProgram, saveProgram

standard_logger = settings.logging.getLogger("discord")
error_logger = settings.logging.getLogger("bot")

global GuildList
GuildList : QbGuild = {}
GlobalQueues : Queue = {}

def saveGuilds():
    while True:
        time.sleep(600)
        saveProgram(GuildList)


class GuildWrapper(commands.Cog):
    __cog_name__ = 'Guild Commands'
    def __init__(self, bot : commands.Bot):
        self.bot = bot
        self.save_thread = None
        
        
    def loadGuilds(self, loadDict):

            for guild_id, guild_data in loadDict.items():
                discordGuild: QbGuild = self.bot.get_guild(guild_id)

                if discordGuild:
                    # Create a Guild instance
                    guild_instance = QbGuild(discordGuild, self.bot)
                    standard_logger.info(f"Loading {guild_instance.discGuild.name}")
                    
                    # Add queues to the Guild instance if available
                    if 'queues' in guild_data:
                        standard_logger.info(f"Listing queues in {guild_instance.discGuild.id}")
                        standard_logger.info(" Queue name | Queue type | Queue ID")
                        for queue_data in guild_data['queues']:
                            queueId = queue_data['QueueId']
                            queueName = queue_data['QueueName']
                            queueType = queue_data['QueueType']
                            queueMax = queue_data['QueueMax']
                            queueMin = queue_data['QueueMin']
                            isGlobal = queue_data['IsGlobal']
                            boolGlob = bool(isGlobal)
                            globalID = queue_data['GlobalID']

                            if boolGlob:
                                newQueue = Queue(guild=discordGuild, name=queueName, type=queueType, identifier=queueId, min=queueMin, max=queueMax, globalQueue=True)
                                standard_logger.info(f"{newQueue.QueueName:^12}|{newQueue.QueueType:^12}|{newQueue.QueueIndex:^12}")
                                guild_instance.GuildQueues.append(newQueue)
                            else:
                                newQueue = Queue(guild=discordGuild, name=queueName, type=queueType, identifier=queueId, min=queueMin, max=queueMax, globalQueue=False)
                                standard_logger.info(f"{newQueue.QueueName:^12}|{newQueue.QueueType:^12}|{newQueue.QueueIndex:^12}")
                                guild_instance.GuildQueues.append(newQueue)

                    # Add the guild instance to the GuildList
                    GuildList[guild_id] = guild_instance 

            self.save_thread = threading.Thread(target=saveGuilds, daemon=True)
            self.save_thread.start()
    def newGuild(self, newGuild):
        for checkGuild in list(GuildList.values()):
            if newGuild.id == checkGuild.discGuild.id:
                return
        newGuild = QbGuild(newGuild, self.bot)
        GuildList[newGuild.discGuild.id] = newGuild
        standard_logger.info(f"Added new guild: {GuildList[newGuild.discGuild.id]}")
    def checkUserQueues(self, client : Client):
        guildToSearch = client.qbGuild
        for queues in guildToSearch.GuildQueues:
            for user in queues.PeopleInQueue:
                if user.user == client.user:
                    return True
        return False
    def checkUserParties(self, client : Client):
        guildToSearch = client.qbGuild
        for party in list(guildToSearch.GuildParties.values()):
            if client.user == party.user:
                return (True, True, party)
            for user in party.members:
                if user.user == client.user:
                    return (True, False, party)
        return (False)
    def genGlobalId(self, queue, queueBits = 8):
        guild = queue.guild
        queueId = queue.QueueIndex

        if queueId >= (1 << queueBits):
            raise ValueError("Queue ID exceeds the maximum value for the given number of bits")
        
        return (guild.id << queueBits) | queueId  
    def decodeGlobalId(self, bitwiseId, queueBits = 8):
        guildId = bitwiseId >> queueBits
        queueId = bitwiseId & ((1 << queueBits) - 1)
        
        return guildId, queueId

    '''
    @commands.hybrid_command(
            name="testqueue", 
            description="Test the queue system", 
            brief="Test the queue system")
    async def testQueue(self, ctx, queue: str, num: int):
        print(f"Testing queue {queue} {num} times")
        startTest = datetime.datetime.now()
        
        for i in range(num):
            # Simulate a message and context for each test user
            message = MagicMock()
            message.content = f"!joinqueue {queue}"
            message.author = MagicMock(name=f"TestUser{i}")
            message.channel = MagicMock(name="test")

            test_ctx = commands.Context(bot=self.bot, prefix="!", message=message, command=None, view=discord.ui.View)
            test_ctx.send = AsyncMock()
            test_ctx.author = message.author
            test_ctx.channel = message.channel
            test_ctx.guild = ctx.guild

            # Call the joinQueue command
            self.joinQueue(test_ctx, name=queue)

            # Print the call arguments to verify the output
            print(test_ctx.send.call_args)

        endTest = datetime.datetime.now()
        print(f"Test completed in {(endTest - startTest).total_seconds()} seconds")
        await ctx.send(f"Test completed in {(endTest - startTest).total_seconds()} seconds", ephemeral=True)
    '''
    # Test function. Should not be used in production.

    @commands.hybrid_command(
            name="addqueue",
            description = "Admins can add a queue to the server.",
            brief="Admin only -- Create a new queue"    
    )
    @commands.has_permissions(administrator=True)
    async def addQueue(self, 
    ctx : commands.Context, *, 
    name: str = commands.parameter(description="Name of your queue."), 
    queue_type: str = commands.parameter(description="What are we queueing for?"), 
    lobbysize : int = commands.parameter(description="Minimum lobby size")):
        Successful = None
        queuebitGuild = GuildList[ctx.guild.id]
        try:
            newIdentifier = len(queuebitGuild.GuildQueues)
            newQueue = Queue(guild=queuebitGuild, name=name, type=queue_type, identifier=newIdentifier, min=lobbysize, max=lobbysize, globalQueue=False)
            queuebitGuild.GuildQueues.append(newQueue)
            Successful = True
        except Exception as e:
            Successful = False
            error_logger.error(f"Error {e}")
        finally:
            if Successful:
                await ctx.send(f"Successfully added list {queuebitGuild.GuildQueues[-1].QueueName}", ephemeral=True)   
    
    @commands.hybrid_command(
            name="joinqueue",
            description="Join a queue. If the queue you want to join isn't listed, ask an admin to add it for you.",
            brief="Join a queue"
    )
    async def joinQueue(self, 
    ctx : commands.Context, 
    name : str = commands.parameter(description="Which queue?")):
        guildToList : QbGuild = GuildList[ctx.guild.id]
        queueToJoin : Queue = None
        testClient = Client(user=ctx.author, queue=queueToJoin, ctx=ctx, guild=guildToList)
        partyStatus = self.checkUserParties(testClient)
        newClient = None
        if not partyStatus:
            newClient = Client(user=ctx.author, queue=queueToJoin, ctx=ctx, guild=guildToList)
            pass
        elif partyStatus[0]:
            if not partyStatus[1]:
                await ctx.send("Only a party leader can join the queue!", ephemeral=True)
                return
            elif partyStatus[1]:
                newClient = partyStatus[2]                
        for queue in guildToList.GuildQueues:
            if queue.QueueName.lower() == name.lower():
                queueToJoin = queue
                break
            else: 
                pass
        if not queueToJoin:
            await ctx.send("Couldn't join the queue! Are you sure this queue exists?", ephemeral=True)
            error_logger.error(f"Queue '{name}' does not exist in guild '{ctx.guild.name}'")
            return
        
        if self.checkUserQueues(newClient):
            await ctx.send("You're already queuing! Leave the current queue before requeuing with /leavequeue.", ephemeral=True)
            error_logger.warning(f"User '{ctx.author}' is already in a queue in guild '{ctx.guild.name}'")
            return
        else:
            queueToJoin.PeopleInQueue.append(newClient)
            if type(newClient) == Party:
                newClient.activeQueue = queueToJoin
                queueToJoin.noPeopleinQueue += newClient.size
            elif type(newClient) == Client:
                queueToJoin.noPeopleinQueue += 1

            if len(queueToJoin.PeopleInQueue) != queueToJoin.MaxSize * 5:
                await ctx.send(f"You've joined {queueToJoin.QueueName}! \nThere aren't many people, though. \nThis may take a moment! {queueToJoin.noPeopleinQueue}", ephemeral=True)
                standard_logger.info(f"User '{ctx.author}' joined queue '{queueToJoin.QueueName}' in guild '{ctx.guild.name}' with {queueToJoin.noPeopleinQueue} people in queue")
            else:
                await ctx.send(f"You've joined {queueToJoin.QueueName}! Shouldn't take long. {queueToJoin.noPeopleinQueue}", ephemeral=True)
                standard_logger.info(f"User '{ctx.author}' joined queue '{queueToJoin.QueueName}' in guild '{ctx.guild.name}' with {queueToJoin.noPeopleinQueue} people in queue")
            await queueToJoin.tryQueue()
    @joinQueue.autocomplete('name')
    async def queuename_autocomplete(
        self, 
        interaction : discord.Interaction,
        current : str
    ) -> list[app_commands.Choice[str]]:
        queueNames = []
        guildToList : QbGuild = GuildList[interaction.guild.id]
        for queue in guildToList.GuildQueues:
            name = queue.QueueName
            type = queue.QueueType
            queueNames.append(queue.QueueName)
        return [ app_commands.Choice(name=name, value=name) 
            for name in queueNames if current.lower() in name.lower()]
    
    @commands.hybrid_command(
            name="leavequeue",
            brief="Leave a queue",
            description="Leave the current queue you are waiting in."
    )
    async def leaveQueue(self, 
                         ctx : commands.Context):
        guildToUse : QbGuild = GuildList[ctx.guild.id]
        ClientToCheck = Client(user=ctx.author, ctx=ctx, guild=guildToUse)
        results = self.checkUserParties(ClientToCheck)
        if not results:
            for queues in guildToUse.GuildQueues:
                for users in queues.PeopleInQueue:
                    if ctx.author == users.user:
                        await queues.removeFromList(users)
                        queues.noPeopleinQueue -= 1
                        standard_logger.info(f"User '{ctx.author}' left queue '{queues.QueueName}' in guild '{ctx.guild.name}'")
                        await ctx.send(f"You have left the queue: {queues.QueueName}.", ephemeral=True)
                        return
            
            await ctx.send(f"You aren't in a queue!", ephemeral=True)
            error_logger.warning(f"User '{ctx.author}' attempted to leave a queue in guild '{ctx.guild.name}' but is not in any queue")
        else:
            clientToLeave = results[2]
            if results[1]:
                queueToLeave = clientToLeave.activeQueue
                if not queueToLeave:
                    await ctx.send("You're not in a queue!", ephemeral=True)
                    error_logger.warning(f"User '{ctx.author}' attempted to leave a queue in guild '{ctx.guild.name}' but is not in any queue")
                    return
                await queueToLeave.removeFromList(clientToLeave)
                queueToLeave.noPeopleinQueue -= (len(clientToLeave.members)+1)
                standard_logger.info(f"Party '{clientToLeave.partyName}' left queue '{queueToLeave.QueueName}' in guild '{ctx.guild.name}'")
                await ctx.send(f"Your party has left the queue: {queueToLeave.QueueName}.", ephemeral=True)
                return
            else:
                queueToLeave = clientToLeave.activeQueue
                if queueToLeave:
                    await ctx.send("Only a party leader can leave the queue!", ephemeral=True)
                    error_logger.warning(f"User '{ctx.author}' attempted to leave queue '{queueToLeave.QueueName}' in guild '{ctx.guild.name}' but is not the party leader")
                else:
                    await ctx.send("You're not in a queue! Plus, only the party leader can leave queues!", ephemeral=True)
                    error_logger.warning(f"User '{ctx.author}' attempted to leave queue but party is not in a queue in guild '{ctx.guild.name}'")
         
    @commands.hybrid_command(
        name="listqueues",
        brief="List all queues",
        description = "List all queues for this server."
    )
    async def listQueue(self, 
    ctx : commands.Context):
        listGuildQueues = ''
        guildToList: QbGuild = GuildList[ctx.guild.id]
        
        # Define column headers and widths
        headers = ['Queue Name', 'Minimum size', 'Maximum size', 'No. people in Queue']
        col_widths = [15, 15, 15, 20]  # Adjust these widths based on expected data length

        # Create the header row
        header_row = ''.join(f"{header:<{col_width}}" for header, col_width in zip(headers, col_widths))
        listGuildQueues += header_row
        
        # Add a separator row for better readability
        listGuildQueues += '\n' + '-' * sum(col_widths)
        
        # Add each queue's data
        for queue in guildToList.GuildQueues:
            row = ''.join([
                f"{queue.QueueName:<{col_widths[0]}}",
                f"{queue.MinSize:<{col_widths[1]}}",
                f"{queue.MaxSize:<{col_widths[2]}}",
                f"{len(queue.PeopleInQueue):<{col_widths[3]}}"
            ])
            listGuildQueues += '\n' + row

        try:
            if len(listGuildQueues.strip()) > 0:
                await ctx.send(f"```{listGuildQueues}```", ephemeral=True)
                standard_logger.info(f"Listed queues for guild '{ctx.guild.name}'")
            else:
                await ctx.send("There are no queues! Create one with /addqueue", ephemeral=True)
                standard_logger.info(f"No queues found for guild '{ctx.guild.name}'")
        except Exception as e:
            await ctx.send("Undefined error!")
            error_logger.error(f"Error listing queues for guild '{ctx.guild.name}': {e}")
 
    @commands.hybrid_command(
        name="changelobbysize",
        brief="Admin only -- Change the min/max size of a lobby",
        description = "**Admin only** -- Change the minimum and maxmimum number of people that can be queued into a lobby."
    )
    @commands.has_permissions(administrator=True)
    async def changelobbysize(self, 
    ctx : commands.Context, 
    queuename : str = commands.param(description="Queue to Change"), 
    size : int = commands.param(description="Minimum lobby size")):
        guildToCheck = GuildList[ctx.guild.id]
        
        for queue in guildToCheck.GuildQueues:
            if queue.QueueName == queuename:
                queue.MinSize = size
                await ctx.send("Successfully updated!", ephemeral=True)
                standard_logger.info(f"Queue '{queuename}' lobby size updated to {size} by '{ctx.author}' in guild '{ctx.guild.name}'")
                return
            
        await ctx.send("Couldn't update minmax! Please contact support for help.", ephemeral=True)
        error_logger.error(f"Failed to update lobby size for queue '{queuename}' in guild '{ctx.guild.name}'")
    @changelobbysize.autocomplete('queuename')
    async def queuename_autocomplete(
        self, 
        interaction : discord.Interaction,
        current : str
    ) -> list[app_commands.Choice[str]]:
        queueNames = []
        guildToList : QbGuild = GuildList[interaction.guild.id]
        if len(guildToList.GuildQueues) == 0:
            return [ app_commands.Choice(name="No queues found", value="No queues found")]
        for queue in guildToList.GuildQueues:
            name = queue.QueueName
            type = queue.QueueType
            queueNames.append(queue.QueueName)
        return [ app_commands.Choice(name=name, value=name) 
            for name in queueNames if current.lower() in name.lower()]

    '''@commands.hybrid_command(
        name="adminrole",
        brief="Owner only -- Add an admin role",
        description="Add an Administrator role. Only a server owner can use this."
    )
    @commands.is_owner()
    async def modrole(self, ctx, 
    role : discord.Role = commands.param(description="Which role should be the a moderator?"),
    queue : str = commands.param(description="Which queue should the role moderate?")):
    
        qbGuild : QbGuild= GuildList[ctx.guild.id]
        qbGuild.adminRole = role
        
        if qbGuild.adminRole.id == role.id:
            await ctx.send(f"Successfully set admin role! {qbGuild.adminRole.name}", ephemeral=True)
            standard_logger.info(f"Admin role '{role.name}' set for guild '{ctx.guild.name}' by '{ctx.author}'")
            return
        else:
            await ctx.send(f"Couldn't add role!")
            error_logger.error(f"Failed to set admin role '{role.name}' for guild '{ctx.guild.name}' by '{ctx.author}'")
            return'''

    @commands.hybrid_command(
        name="createparty",
        brief="Create a party",
        description="Create a party to queue together"
    )
    async def createParty(self, ctx : commands.Context, partyname : str):
        guildtoUse : QbGuild = GuildList[ctx.guild.id]
        clientCheck = Client(user=ctx.author, ctx=ctx, guild=guildtoUse)
        result = self.checkUserParties(clientCheck)
        if not (not result):
            await ctx.send(f"You're already in a party! \nPeople can join by using: `/joinparty {result[2].partyName}` \nOr you can leave by using: `/leaveparty`", ephemeral=True)
            standard_logger.info(f"User '{ctx.author}' attempted to create a party but is already in party '{result[2].partyName}' in guild '{ctx.guild.name}'")
            return
        else: 
            newParty = Party(secret=partyname, user=ctx.author, qbGuild=guildtoUse, ctx=ctx)
            if partyname in list(guildtoUse.GuildParties.keys()):
                await ctx.send("Party already exists!", ephemeral=True)
                error_logger.warning(f"User '{ctx.author}' attempted to create a party with an existing name '{partyname}' in guild '{ctx.guild.name}'")
                return
            
            guildtoUse.GuildParties[partyname] = newParty
            if guildtoUse.GuildParties[partyname]:
                await ctx.send(f"Party `{partyname}` created!", ephemeral=True)
                standard_logger.info(f"Party '{partyname}' created by user '{ctx.author}' in guild '{ctx.guild.name}'")
            else:
                await ctx.send("Couldn't create party!", ephemeral=True)
                error_logger.error(f"Failed to create party '{partyname}' by user '{ctx.author}' in guild '{ctx.guild.name}'")

    @commands.hybrid_command(
        name="joinparty",
        brief="Join a party",
        description="Join a party using the name" )
    async def joinParty(self, ctx, partyname):
        guildtoUse : QbGuild = GuildList[ctx.guild.id]
        if partyname in list(guildtoUse.GuildParties.keys()):
            newClient= Client(user=ctx.author, ctx=ctx, guild=guildtoUse)
            if newClient.user == guildtoUse.GuildParties[partyname].user or any(newClient.user == member.user for member in guildtoUse.GuildParties[partyname].members):
                await ctx.send("You're already in the party!", ephemeral=True)
                standard_logger.info(f"User '{ctx.author}' attempted to join party '{partyname}' but is already a member in guild: '{ctx.guild.name}'")
                return

            await guildtoUse.GuildParties[partyname].addMember(newClient)
            await ctx.send(f"Joined party: {partyname}!", ephemeral=True)
            standard_logger.info(f"User '{ctx.author}' joined party '{partyname}' in guild: '{ctx.guild.name}'")
        else:
            await ctx.send("Couldn't join party! Does it exist?", ephemeral=True)
            error_logger.warning(f"User '{ctx.author}' attempted to join non-existent party '{partyname}' in guild: '{ctx.guild.name}'")

    @commands.hybrid_command(
            name="leaveparty", 
            brief="Leave a party", 
            description="Leave the party you are in.")
    async def leaveParty(self, ctx):
        partyToLeave = self.checkUserParties(Client(user=ctx.author, ctx=ctx, guild=GuildList[ctx.guild.id]))
        if not partyToLeave:
            await ctx.send("You're not in a party!", ephemeral=True)
            standard_logger.info(f"User '{ctx.author}' attempted to leave a party but is not in a party in guild '{ctx.guild.name}'")
            return
        else:
            if partyToLeave[1]:
                await partyToLeave[2].disband()
                await ctx.send("The party disbanded!", ephemeral=True)
                standard_logger.info(f"User '{ctx.author}' disbanded party '{partyToLeave[2].partyName}' in guild '{ctx.guild.name}'")
            else:
                newClient = Client(user=ctx.author, ctx=ctx, guild=GuildList[ctx.guild.id])
                await partyToLeave[2].removeMember(newClient)
                await ctx.send("You've left the party!", ephemeral=True)
                standard_logger.info(f"User '{ctx.author}' left party '{partyToLeave[2].partyName}' in guild '{ctx.guild.name}'")

    @commands.hybrid_command(name="partyinfo", brief="Get party information", description="Get information on a party")
    async def partyinfo(self, ctx):
        PartyToCheck = self.checkUserParties(Client(user=ctx.author, ctx=ctx, guild=GuildList[ctx.guild.id]))
        if not PartyToCheck:
            await ctx.send("You're not in a party!", ephemeral=True)
            standard_logger.info(f"User '{ctx.author}' attempted to get party info but is not in a party in guild '{ctx.guild.name}'")
            return
        else:
            party = PartyToCheck[2]
            partyMembers = '```'

            headers = ['', 'User']
            colWidths = [3, 15]

            headerRow = ''.join(f"{header:^{colWidths}}" for header, colWidths in zip(headers, colWidths))
            partyMembers += headerRow
            partyMembers += '\n' + '-' * sum(colWidths)

            fRow = ''.join([
                f"* ",
                f"|{party.user.name:^{colWidths[1]}}"
            ])
            partyMembers += '\n' + fRow

            for member in party.members:
                row = ''.join([
                    f"  ",
                    f"| {member.user.name:^{colWidths[1]}}"
                ])
                partyMembers += '\n' + row
            partyMembers += '```'

            await ctx.send(partyMembers, ephemeral=True)
            standard_logger.info(f"User '{ctx.author}' requested party info for party '{party.partyName}' in guild '{ctx.guild.name}'")

    @commands.hybrid_command(
            name="queueinfo", 
            brief="Get queue information", 
            description="Get information on a queue")
    async def queueinfo(self, ctx, queuename):
        guildtoUse : QbGuild = GuildList[ctx.guild.id]
        for queue in guildtoUse.GuildQueues:
            if queue.QueueName == queuename:
                await ctx.send(queue.info(), ephemeral=True)
                standard_logger.info(f"Queue info for '{queuename}' requested by '{ctx.author}' in guild '{ctx.guild.name}'")
                return
        await ctx.send("Couldn't find queue!", ephemeral=True)
        error_logger.warning(f"Queue '{queuename}' not found in guild '{ctx.guild.name}' requested by '{ctx.author}'")
    @queueinfo.autocomplete('queuename')
    async def queuename_autocomplete(
        self, 
        interaction : discord.Interaction,
        current : str
    ) -> list[app_commands.Choice[str]]:
        queueNames = []
        guildToList : QbGuild = GuildList[interaction.guild.id]
        if len(guildToList.GuildQueues) == 0:
            return [ app_commands.Choice(name="No queues found", value="No queues found")]
        for queue in guildToList.GuildQueues:
            name = queue.QueueName
            type = queue.QueueType
            queueNames.append(queue.QueueName)
        return [ app_commands.Choice(name=name, value=name) 
            for name in queueNames if current.lower() in name.lower()]

    @commands.hybrid_command( 
            name="registerqueue", 
            brief="Register a queue", 
            description="Register a queue as global.")
    async def registerQueue(self, ctx, queuename):
        guildtoUse : QbGuild = GuildList[ctx.guild.id]
        for queue in guildtoUse.GuildQueues:
            if queue.QueueName == queuename:
                queue.GlobalId = self.genGlobalId(queue)
                GlobalQueues[queue.GlobalId] = queue
                await ctx.send(f"Registered {queuename} as global queue!", ephemeral=True)
                standard_logger.info(f"Queue '{queuename}' registered as global queue by '{ctx.author}' in guild '{ctx.guild.name}'")
                return
        await ctx.send("Couldn't find queue!", ephemeral=True)
        error_logger.warning(f"Queue '{queuename}' not found in guild '{ctx.guild.name}' requested by '{ctx.author}'")
    @registerQueue.autocomplete('queuename')
    async def queuename_autocomplete(
        self, 
        interaction : discord.Interaction,
        current : str
    ) -> list[app_commands.Choice[str]]:
        queueNames = []
        guildToList : QbGuild = GuildList[interaction.guild.id]
        if len(guildToList.GuildQueues) == 0:
            return [ app_commands.Choice(name="No queues found", value="No queues found")]
        for queue in guildToList.GuildQueues:
            name = queue.QueueName
            type = queue.QueueType
            if not queue.IsGlobal:
                queueNames.append(queue.QueueName)
            else :
                pass
        return [ app_commands.Choice(name=name, value=name) 
            for name in queueNames if current.lower() in name.lower()]

    @commands.hybrid_command(name="listglobal", brief="List global queues", description="List all global queues.")
    async def listGlobal(self, ctx):
        globalQueueList = ''
        
        # Define column headers and widths
        headers = ['Queue Name', 'Queue Subject', 'Lobby Size', 'No. people in Queue', 'Queue ID']
        col_widths = [15, 20, 15, 20, 25]  # Adjust these widths based on expected data length

        # Initialize the globalQueueList with headers
        globalQueueList = ''.join([f"{header:^{col_widths[i]}}" for i, header in enumerate(headers)])
        if len(GlobalQueues) == 0:
            await ctx.send("No global queues found!", ephemeral=True)
            return
        
        # Add each queue's information
        for queue in GlobalQueues.values():

            row = ''.join([
                f"{queue.QueueName:^{col_widths[0]}}",
                f"{queue.QueueType:^{col_widths[1]}}",
                f"{queue.MinSize:^{col_widths[2]}}",
                f"{len(queue.PeopleInQueue):^{col_widths[3]}}",
                f"{queue.GlobalId:^{col_widths[4]}}"
            ])
            globalQueueList += '\n' + row

            await ctx.send(f"```{globalQueueList}```", ephemeral=True)

    @addQueue.error
    async def addQueue_error(self, ctx, error):
        if isinstance(error, commands.CommandError):
            await ctx.send(f"Sorry. Only admins can add queues.", ephemeral=True)
      



    '''@discClient.hybrid_command(
        name="add admin",
        description="Add a new administrator to the guild")
        '''


async def setup(bot):
    await bot.add_cog(GuildWrapper(bot))



atexit.register(endProgram, GuildList)
