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
        self.guild_queues = {}
        self.guild_parties = {}
        self.active_members = {
            # discord.User : classes.Client
        }


class Queue:
    """ Queue object to store queue information """
    def __init__(self, guild : QbGuild, owner, name : str, queue_type : str, identifier : int, min_size : int, max_size : int, global_queue : bool = False, global_id : int = 0):
        """ Initialize the queue object """
        self.guild: QbGuild = guild
        self.root_guild = owner
        self.queue_name = name
        self.queue_index = identifier
        self.global_id = global_id
        self.is_global = global_queue
        self.queue_type = queue_type
        self.max_size = max_size
        self.min_size = min_size
        self.queue_mods = []
        self.people_in_queue = {}
        self.is_active = False
        self.no_people_in_queue = 0

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
        self.people_in_queue.pop(client)

    async def try_queue(self):
        """ Attempt to form a lobby from the queue """
        standard_logger.info("Attempting to form a lobby for queue: %s", self.queue_name)
        current_lobby = []
        if len(self.people_in_queue) >= self.min_size:
            standard_logger.info("Enough people in queue to form a lobby for %s", self.queue_name)

            for user in self.people_in_queue.values():
                current_lobby.append(user)
                standard_logger.info("Added %s to the lobby for %s", user.user.name, self.queue_name)
                if len(current_lobby) == self.min_size:
                    break

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
            if isinstance(client, Party):
                gather_msg += f"\n<@{client.user.id}>"
                for member in client.members:
                    gather_msg += f"\n{member.user.id}>"
            else:
                gather_msg += f"\n<@{client.user.id}>"
        for client in lobby:
            if isinstance(client, Party):
                await client.ctx.send(f"{gather_msg}", ephemeral=True)
                await self.drop_members(client)
                for member in client.members:
                    await member.ctx.send(f"{gather_msg}", ephemeral=True)
            else:
                await client.ctx.send(f"{gather_msg}", ephemeral=True)
                await self.drop_members(client)

        log = "Group gathered in " + str((datetime.datetime.now() - start_gather).total_seconds()) + " seconds"
        standard_logger.info(log)

    async def drop_members(self, client):
        """Drop users from a queue"""
        self.people_in_queue.pop(client.user.id)
        if isinstance(client, Party):
            self.no_people_in_queue -= client.size
            client.active_queue = None
            for user in client.members:
                user.active_queue = None
        if isinstance(client, Client):
            self.no_people_in_queue -= 1
            client.active_queue = None

class Client:
    """ Client object to store user information """
    def __init__(self, user: discord.User, ctx: Context, guild: QbGuild):
        """ Initialize the client object """
        self.user: discord.User = user
        self.qb_guild: QbGuild = guild
        self.ctx = ctx
        self.time_joined = datetime.datetime.now()
        self.active_queue: Queue = None


class Party(Client):
    """ Party object to store party information """
    def __init__(self, secret, user, qb_guild, ctx):
        """ Initialize the party object """
        super().__init__(user, ctx, qb_guild)
        self.size = 1
        self.members = []
        self.party_name = secret
        self.time_joined = datetime.datetime.now()

    async def add_member(self, member: Client):
        """ Add a member to the party """
        standard_logger.info("Adding %s to party %s", member.user, self.party_name)
        self.size += 1
        self.qb_guild.active_members[member.user.id] = self
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
        self.qb_guild.active_members.pop(user.user.id)
        self.members.remove(client_to_remove)
        await self.ctx.send(f"<@{user.user.id}> has left the party.", ephemeral=True)
        for member in self.members:
            await member.ctx.send(f"<@{user.user.id}> has left the party.", ephemeral=True)

    async def disband(self):
        """ Disband the party """
        standard_logger.info("Disbanding party %s", self.party_name)
        if self.active_queue:
            self.active_queue.no_people_in_queue -= self.size
            self.active_queue.people_in_queue.pop(self.user.id)
        for member in self.members:
            await member.ctx.send(f"Your party has been disbanded! @{member.user.name}", ephemeral=True)
            standard_logger.info("Notified %s about disbanding %s", member.user.name, self.party_name)
        self.qb_guild.guild_parties.pop(self.party_name)
        standard_logger.info("Party %s removed from guild parties", self.party_name)
