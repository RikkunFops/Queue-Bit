import discord
from discord.ext.commands import Context
from collections import deque

class QbGuild():
    def __init__(self, guildObj, bot):
            self.discGuild : discord.Guild = guildObj
            self.bot = bot
            self.owner : discord.User = self.discGuild.owner
            self.guildAdmins = { self.owner : ["All", "Owner"] }
            self.isSetup = False
            self.GuildQueues = []

class Queue():
    def __init__(self, guild, name, type, identifier):
        self.guild : QbGuild = guild
        self.QueueName = name
        self.QueueID = identifier
        self.QueueType = type
        self.MaxSize = 2
        self.MinSize = 2
        self.QueueMods = {
            # discord.User : Permissions
        }
        self.PeopleInQueue = [
            # classes.Client
        ]
        self.isActive = False

    def queueLength(self):
        return len(self.PeopleInQueue)

    async def removeFromList(self, client):
        self.PeopleInQueue.remove(client)

    async def tryQueue(self):
        currentLobby = []
        if len(self.PeopleInQueue) >= self.MinSize:

            for _ in range(self.MinSize):
                currentLobby.append(self.PeopleInQueue.pop(0))
            
            if len(currentLobby) < self.MaxSize and len(self.PeopleInQueue) > 0:
                currentLobby.append(self.PeopleInQueue.pop(0))

            if len(currentLobby) > 0:
                await self.gatherLobby(currentLobby)
        
                                 
    async def gatherLobby(self, lobby):
         gatherMsg = "We've found a group, it's time to rally!"
         
         for client in lobby:
              gatherMsg += f"\n<@{client.user.id}>"
         for client in lobby:
              await client.ctx.send(gatherMsg, ephemeral = True)
             
class Client():
     def __init__(self, user : discord.User, queue, ctx : Context, guild : QbGuild):
          self.user :discord.User = user
          self.qbGuild : QbGuild = guild
          self.activeQueue : Queue = queue
          self.ctx = ctx

class Party(Client):
    def __init__(self, users):
        # self.user = Party leader
        self.members = []
    
    def addMember(self, user : Client):
        self.members.append(user)