import discord

class QbGuild():
    def __init__(self, guildObj):
            self.discGuild : discord.Guild = guildObj
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
        self.MaxSize = 5
        self.MinSize = 4
        self.QueueMods = {
            # discord.User : Permissions
        }
        self.PeopleInQueue = [
            # discord.User
        ]
    