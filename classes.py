import discord
from discord.ext.commands import Context
import datetime
import settings

standard_logger = settings.logging.getLogger("discord")
error_logger = settings.logging.getLogger("bot")


class QbGuild():
    def __init__(self, guildObj, bot):
            self.discGuild : discord.Guild = guildObj
            self.bot = bot
            self.owner : discord.User = self.discGuild.owner
            self.GuildQueues = []
            self.GuildParties = {}
            self.ActiveMembers = {
                # discord.User : classes.Client
            }

class Queue():
    def __init__(self, guild, name, type, identifier, min, max, globalQueue):
        self.guild : QbGuild = guild
        self.QueueName = name
        self.QueueIndex = identifier
        self.GlobalId = 0
        self.IsGlobal = globalQueue
        self.QueueType = type
        self.MaxSize = max
        self.MinSize = min
        self.QueueMods = []
        self.PeopleInQueue = [
            # classes.Client
        ]
        self.isActive = False
        self.noPeopleinQueue = 0

    def info(self):
        infoStr = f"Queue Name: {self.QueueName}\nLobby Size: {self.MinSize} - {self.MaxSize}\nPeople in Queue: {self.noPeopleinQueue}\n"
        if len(self.QueueMods) > 0:
            for mod in self.QueueMods:
                infoStr += f"\n<{mod.user.name}>"
        else:
            infoStr += "No mods assigned"

        return infoStr

    def queueLength(self):
        return len(self.PeopleInQueue)

    async def removeFromList(self, client):
        self.PeopleInQueue.remove(client)

    async def tryQueue(self):
        standard_logger.info(f"Trying to queue {self.QueueName}")
        currentLobby = []
        if len(self.PeopleInQueue) >= self.MinSize:
            standard_logger.info(f"Enough people in queue to form a lobby for {self.QueueName}")

            for _ in range(self.MinSize):
                client = self.PeopleInQueue.pop(0)
                currentLobby.append(client)
                standard_logger.info(f"Added {client.user.name} to the lobby for {self.QueueName}")

            if len(currentLobby) > 0:
                await self.gatherLobby(currentLobby)
                standard_logger.info(f"Gathered lobby for {self.QueueName}")
        else:
            standard_logger.info(f"Not enough people in queue to form a lobby for {self.QueueName}")
        
                                 
    async def gatherLobby(self, lobby):
        gatherMsg = "We've found a group, it's time to rally!"
        startGather = datetime.datetime.now()
        for client in lobby:
            try:
                gatherMsg += f"\n<@{client.user.id}>"
            except:
                pass
            print(f"Client {client.user.name} gathered in {(datetime.datetime.now() - client.timeJoined).total_seconds()} seconds")         
            for client in lobby:
                try:
                    await client.ctx.send(gatherMsg, ephemeral = True)
                except:
                    pass

        print(f"Group gathered in {(datetime.datetime.now() - startGather).total_seconds()} seconds")
             
class Client():
     def __init__(self, user : discord.User, ctx : Context, guild : QbGuild, **kwargs):
          self.user :discord.User = user
          self.qbGuild : QbGuild = guild
          self.ctx = ctx
          self.timeJoined = datetime.datetime.now()
          try: 
            if kwargs['queue'] is not None:
                self.activeQueue : Queue = kwargs['queue']
          except:
                pass

class Party(Client):
    def __init__(self, secret, user, qbGuild, ctx):
        super().__init__(user, ctx, qbGuild)
        self.size = 1
        self.members =[]
        self.partyName = secret
        self.activeQueue : Queue = None
        self.timeJoined = datetime.datetime.now()
    
    async def addMember(self, member : Client):
        standard_logger.info(f"Adding {member.user.name} to party {self.partyName}")
        self.size += 1
        await self.ctx.send(f"New member joined your party! <@{member.user.id}>", ephemeral = True)
        for member in self.members:
            await member.ctx.send(f"New member joined your party! <@{member.user.id}>", ephemeral = True)
        self.members.append(member)

    async def removeMember(self, user : Client):
        clientToRemove = None
        for member in self.members:
            if member.user.id == user.user.id:
                clientToRemove = member
                break
        standard_logger.info(f"Removing {user.user.name} from party {self.partyName}")
        self.size -= 1
        self.members.remove(clientToRemove)
        await self.ctx.send(f"<@{user.user.id}> has left the party.", ephemeral=True)
        for member in self.members:
            await member.ctx.send(f"<@{user.user.id}> has left the party.", ephemeral=True)
    
    async def disband(self):
        standard_logger.info(f"Disbanding party {self.partyName}")
        for member in self.members:
            await member.ctx.send(f"Your party has been disbanded! @{member.user.name}", ephemeral=True)
            standard_logger.info(f"Notified {member.user.name} about disbanding {self.partyName}")
        self.qbGuild.GuildParties.pop(self.partyName)
        standard_logger.info(f"Party {self.partyName} removed from guild parties")