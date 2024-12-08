import discord

class CommandProcessor:
    def __init__(self, context):
        # Context, whether it is running from Main or within a Guild
        self.context = context

    def processCommand(command):
        pass


class Command:
    def __init__(self, userID, guildID, command, args):
        self.userID = userID
        self.guildID = guildID
        self.command = command
        self.args = args
        