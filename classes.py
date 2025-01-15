import datetime
import discord
from discord.ext.commands import Context
import settings

standard_logger = settings.logging.getLogger("discord")
error_logger = settings.logging.getLogger("bot")


class QbGuild:
    """ Guild object to store guild information """
    def __init__(self, guild_obj, bot):
        """ Initialize the guild object """
        self.disc_guild: discord.Guild = guild_obj
        self.bot = bot
        self.owner: discord.User = self.disc_guild.owner
        self.guild_queues = []
        self.guild_parties = {}
        self.active_members = {
            # discord.User : classes.Client
        }


class Queue:
    """ Queue object to store queue information """
    def __init__(self, guild, name, queue_type, identifier, min_size, max_size, global_queue, kwargs):
        """ Initialize the queue object """
        self.guild: QbGuild = guild
        self.queue_name = name
        self.queue_index = identifier
        self.global_id = 0
        self.is_global = global_queue
        self.queue_type = queue_type
        self.max_size = max_size
        self.min_size = min_size
        self.queue_mods = []
        self.people_in_queue = [
            # classes.Client
        ]
        self.is_active = False
        self.no_people_in_queue = 0

        if kwargs['global_id'] is not None:
            self.global_id = kwargs['global_id']

    def info(self):
        """ Return a string with the queue information """
        info_str = f"Queue Name: {self.queue_name}\nLobby Size: {self.min_size}"
        info_str += f" - {self.max_size}\nPeople in Queue: {self.no_people_in_queue}\n"
        if len(self.queue_mods) > 0:
            for mod in self.queue_mods:
                info_str += f"\n<{mod.user.name}>"
        else:
            info_str += "No mods assigned"

        return info_str

    def queue_length(self):
        """ Return the length of the queue """
        return len(self.people_in_queue)

    async def remove_from_list(self, client):
        """ Remove a client from the queue """
        self.people_in_queue.remove(client)

    async def try_queue(self):
        """ Attempt to form a lobby from the queue """
        standard_logger.info("Attempting to form a lobby for queue: %s", self.queue_name)
        current_lobby = []
        if len(self.people_in_queue) >= self.min_size:
            standard_logger.info("Enough people in queue to form a lobby for %s", self.queue_name)

            for _ in range(self.min_size):
                client = self.people_in_queue.pop(0)
                current_lobby.append(client)
                standard_logger.info("Added %s to the lobby for %s", client.user.name, self.queue_name)

            if len(current_lobby) > 0:
                await self.gather_lobby(current_lobby)
                standard_logger.info("Gathered lobby for %s", self.queue_name)
        else:
            log = "Not enough people in queue to form a lobby for " + self.queue_name
            standard_logger.info(log)

    async def gather_lobby(self, lobby):
        """ Gather the lobby and notify the members """
        gather_msg = "We've found a group, it's time to rally!"
        start_gather = datetime.datetime.now()
        for client in lobby:
            try:
                gather_msg += f"\n<@{client.user.id}>"
            except AttributeError:
                pass
            log = "Client " + client.user.name + " gathered in "
            log += str((datetime.datetime.now() - client.time_joined).total_seconds()) + " seconds"
            standard_logger.info(log)
            for client in lobby:
                try:
                    await client.ctx.send(gather_msg, ephemeral=True)
                except AttributeError:
                    pass
        log = "Group gathered in " + str((datetime.datetime.now() - start_gather).total_seconds()) + " seconds"
        standard_logger.info(log)


class Client:
    """ Client object to store user information """
    def __init__(self, user: discord.User, ctx: Context, guild: QbGuild, **kwargs):
        """ Initialize the client object """
        self.user: discord.User = user
        self.qb_guild: QbGuild = guild
        self.ctx = ctx
        self.time_joined = datetime.datetime.now()
        try:
            if kwargs['queue'] is not None:
                self.active_queue: Queue = kwargs['queue']
        except KeyError:
            pass


class Party(Client):
    """ Party object to store party information """
    def __init__(self, secret, user, qb_guild, ctx):
        """ Initialize the party object """
        super().__init__(user, ctx, qb_guild)
        self.size = 1
        self.members = []
        self.party_name = secret
        self.active_queue: Queue = None
        self.time_joined = datetime.datetime.now()

    async def add_member(self, member: Client):
        """ Add a member to the party """
        standard_logger.info("Adding %s to party %s", member.user, self.party_name)
        self.size += 1
        await self.ctx.send(f"New member joined your party! <@{member.user.id}>", ephemeral=True)
        for pMember in self.members:
            await pMember.ctx.send(f"New member joined your party! <@{pMember.user.id}>", ephemeral=True)
        self.members.append(member)

    async def remove_member(self, user: Client):
        """ Remove a member from the party """
        client_to_remove = None
        for member in self.members:
            if member.user.id == user.user.id:
                client_to_remove = member
                break
        standard_logger.info("Removing %s from party %s", user.user.name, self.party_name)
        self.size -= 1
        self.members.remove(client_to_remove)
        await self.ctx.send(f"<@{user.user.id}> has left the party.", ephemeral=True)
        for member in self.members:
            await member.ctx.send(f"<@{user.user.id}> has left the party.", ephemeral=True)

    async def disband(self):
        """ Disband the party """
        standard_logger.info("Disbanding party %s", self.party_name)
        for member in self.members:
            await member.ctx.send(f"Your party has been disbanded! @{member.user.name}", ephemeral=True)
            standard_logger.info("Notified %s about disbanding %s", member.user.name, self.party_name)
        self.qb_guild.guild_parties.pop(self.party_name)
        standard_logger.info("Party %s removed from guild parties", self.party_name)
