import discord

class Guild():
    def __init__(self, guildObj):
            self.discGuild : discord.Guild = guildObj
            self.owner : discord.User = self.discGuild.owner
            self.guildAdmins = { self.owner : ["All"] }
            self.isSetup = False
            self.GuildQueues : Queue = []

class Queue():
    def __init__(self, guild, name, type, identifier):
        self.guild : Guild = guild
        self.QueueName = name
        self.QueueID = identifier
        self.QueueType = type
        self.QueueMods = {
            # discord.User : Permissions
        }
        self.PeopleInQueue = [
            # discord.User
        ]
    