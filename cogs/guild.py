import threading
import time
import atexit

import discord
from discord import app_commands
from discord.ext import commands

import settings
from classes import QbGuild, Queue, Client, Party
from dbaccess import end_program, save_program, delete_queue
from checks import *
from encoding import encode_base62, decode_base62

standard_logger = settings.logging.getLogger("discord")
error_logger = settings.logging.getLogger("bot")


GuildList : QbGuild = {}
GlobalQueues : Queue = {}
# pylint: disable=too-many-public-methods
def save_guilds():
    """ Save the guilds to the database """
    while True:
        time.sleep(600)
        save_program(GuildList)


class GuildWrapper(commands.Cog):
    """ Guild commands for QuBit """
    __cog_name__ = 'Guild Commands'

    def __init__(self, bot: commands.Bot):
        """ Initialize the GuildWrapper """
        self.bot = bot
        self.save_thread = None

    def load_guilds(self, load_dict):
    # pylint: disable=too-many-locals
        """Load the guilds from the database."""

        global_queues = []
        for guild_id, guild_data in load_dict.items():
            discord_guild: QbGuild = self.bot.get_guild(int(guild_id))  # Ensure guild_id is an integer.

            if discord_guild:
                # Create a Guild instance
                guild_instance = QbGuild(discord_guild, self.bot)
                standard_logger.info("Loading %s", guild_instance.disc_guild.name)

                # Add queues to the Guild instance if available
                if 'queues' in guild_data:
                    standard_logger.info("Listing queues in %s", guild_instance.disc_guild.id)
                    standard_logger.info("      Queue name | Queue type | Queue ID")
                    for queue_data in guild_data['queues']:
                        queue_id = queue_data['QueueId']
                        root = queue_data['RootGuild']
                        queue_name = queue_data['QueueName']
                        queue_type = queue_data['QueueType']
                        queue_max = queue_data['QueueMax']
                        queue_min = queue_data['QueueMin']
                        is_global = queue_data['IsGlobal']
                        global_id = queue_data['GlobalID']

                        # Create a new Queue instance based on the queue data
                        new_queue = Queue(
                            guild=discord_guild,
                            name=queue_name,
                            owner = self.bot.get_guild(int(root)) if root is not None else discord_guild,
                            queue_type=queue_type,
                            identifier=queue_id,
                            min_size=queue_min,
                            max_size=queue_max,
                            global_queue=bool(is_global),
                            global_id=global_id
                        )

                        standard_logger.info("      %-10s | %-10s | %-10s", new_queue.queue_name.center(10), new_queue.queue_type.center(10), str(new_queue.queue_index).center(10))
                        guild_instance.guild_queues[queue_name] = new_queue
                        if new_queue.is_global and new_queue.guild.id == new_queue.root_guild.id:
                            global_queues.append(new_queue)

                # Add the guild instance to the GuildList
                GuildList[guild_id] = guild_instance
        self.say_global_queues(global_queues)
        self.save_thread = threading.Thread(target=save_guilds, daemon=True)
        self.save_thread.start()

    def say_global_queues(self, queues):
        """ Add global queues to dict, log """
        list_global_queues = ''
        # Define column headers and widths
        headers = ['Queue Name', 'Lobby size', 'Owning Guild', 'Queue ID']
        col_widths = [15, 15, 15, 25]  # Adjust these widths based on expected data length
        standard_logger.info("Listing Global Queues")
        # Create the header row
        header_row = ''.join(f"{header:^{col_width}}" for header, col_width in zip(headers, col_widths))
        standard_logger.info(header_row)
        # Add a separator row for better readability
        standard_logger.info('-' * sum(col_widths))
        # Add each queue's data
        for queue in queues:
            row = ''.join([
                f"{queue.queue_name:^{col_widths[0]}}",
                f"{queue.min_size:^{col_widths[1]}}",
                f"{queue.guild.name:^{col_widths[2]}}",
                f"{queue.global_id:^{col_widths[3]}}"
            ])
            list_global_queues += '\n' + row
            standard_logger.info(row)
            GlobalQueues[queue.global_id] = queue

    def new_guild(self, new_guild):
        """ Add a new guild to the GuildList """
        for check_guild in list(GuildList.values()):
            if new_guild.id == check_guild.disc_guild.id:
                return
        new_guild = QbGuild(new_guild, self.bot)
        GuildList[new_guild.disc_guild.id] = new_guild
        standard_logger.info("Added new guild: %s", GuildList[new_guild.disc_guild.id])

    def check_user_queues(self, client: Client):
        """ Check if a user is in a queue """
        if client.user.id in list(client.qb_guild.active_members.keys()):
            return client.qb_guild.active_members[client.user.id]
        return False

    async def check_user_parties(self, guild_to_list, ctx : commands.Context):
        """ Check if a user is in a party """
        if ctx.author.id in list(guild_to_list.active_members.keys()):
            return guild_to_list.active_members[ctx.author.id]
        return Client(ctx.author, ctx, guild_to_list)

    def gen_global_id(self, queue, queue_bits=8):
        """ Generate a global ID for a queue """
        guild = queue.guild
        queue_id = queue.queue_index

        if queue_id >= (1 << queue_bits):
            raise ValueError("Queue ID exceeds the maximum value for the given number of bits")

        return (guild.id << queue_bits) | queue_id

    def decode_global_id(self, bitwise_id, queue_bits=8):
        """ Decode a global ID into guild and queue IDs """
        guild_id = bitwise_id >> queue_bits
        queue_id = bitwise_id & ((1 << queue_bits) - 1)

        return guild_id, queue_id

    @commands.hybrid_command(
        name="addqueue",
        description="Admins can add a queue to the server.",
        brief="Admin only -- Create a new queue"
    )
    @commands.check(owner_or_permissions(administrator=True))
    async def add_queue(self, ctx: commands.Context, *, name: str = commands.parameter(description="Name of your queue."),
                        activity: str = commands.parameter(description="What are we queueing for?"),
                        lobbysize: int = commands.parameter(description="Minimum lobby size")):
        """ Add a queue to the server """
        queuebit_guild = GuildList[ctx.guild.id]
        successful = False
        if name in queuebit_guild.guild_queues.keys():
            await ctx.send(f"The queue {name} already exists!", ephemeral=True)
            return
        try:
            new_identifier = len(queuebit_guild.guild_queues)
            standard_logger.info(new_identifier)
            new_queue = Queue(guild=queuebit_guild, owner=ctx.guild, name=name, queue_type=activity, identifier=new_identifier, min_size=lobbysize, max_size=lobbysize, global_queue=False, global_id=None)
            queuebit_guild.guild_queues[name] = new_queue
            successful = True
        except ValueError as ve:
            successful = False
            standard_logger.info("ValueError: %s", ve)
        except TypeError as te:
            successful = False
            standard_logger.info("TypeError: %s", te)
        except KeyError as ke:
            successful = False
            standard_logger.info("KeyError: %s", ke)
        except Exception as e:
            standard_logger.info("Exception: %s", e)
        finally:
            if successful:
                await ctx.send(f"Successfully added queue {queuebit_guild.guild_queues[name].queue_name}", ephemeral=True)
                standard_logger.info("Queue '%s' added by '%s' in guild '%s'", name, ctx.author, ctx.guild.name)

    @commands.hybrid_command(
        name="joinqueue",
        description="Join a queue. If the queue you want to join isn't listed, ask an admin to add it for you.",
        brief="Join a queue"
    )
    async def join_queue(self, ctx: commands.Context, name: str = commands.parameter(description="Which queue?")):
        # pylint: disable=too-many-branches
        """ Join a queue """
        guild_to_list: QbGuild = GuildList[ctx.guild.id]
        queue_to_join: Queue = None
        client_to_use : Client = await self.check_user_parties(guild_to_list=guild_to_list, ctx=ctx)
        # Check if the user is already in a queue
        if hasattr(client_to_use, "active_queue") and client_to_use.active_queue is not None:
            await ctx.send(f"You're already queueing for `{client_to_use.active_queue.queue_name}`! Leave the current queue before requeuing with /leavequeue.", ephemeral=True)
            return
        if client_to_use.user.id != ctx.author.id:
            await ctx.send("Only the party leader can join queues!", ephemeral=True)
            return
        # Check if the queue exists in the guild
        if name in guild_to_list.guild_queues.keys():
            queue_to_join = guild_to_list.guild_queues[name]
        else:
            await ctx.send("Couldn't find queue! Are you sure it exists?", ephemeral=True)
            return
        if queue_to_join.global_id in GlobalQueues.keys():
            print(queue_to_join.global_id)
            queue_to_join = GlobalQueues[queue_to_join.global_id]
        queue_to_join.people_in_queue[ctx.author.id] = client_to_use
        guild_to_list.active_members[ctx.author.id] = client_to_use
        if isinstance(client_to_use, Party):
            queue_to_join.no_people_in_queue += client_to_use.size
            print(client_to_use.size)
            client_to_use.active_queue = queue_to_join
            await ctx.send(f"You've joined queue {name}! There are {queue_to_join.no_people_in_queue} in queue right now.", ephemeral=True)
            for user in client_to_use.members:
                client_to_use.active_queue = queue_to_join
                guild_to_list.active_members[ctx.author.id] = client_to_use
                await user.ctx.send(f"Your party has joined queue {name}! There are {queue_to_join.no_people_in_queue} in queue right now.", ephemeral=True)
        elif isinstance(client_to_use, Client):
            client_to_use.active_queue = queue_to_join
            queue_to_join.no_people_in_queue += 1
            await ctx.send(f"You've joined queue {name}! There are {queue_to_join.no_people_in_queue} in queue right now.", ephemeral=True)
        await queue_to_join.try_queue()
        return

    @join_queue.autocomplete('name')
    async def joinqueue_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """ Autocomplete the queue name """
        queue_names = []
        guild_to_list: QbGuild = GuildList[interaction.guild.id]
        for queue in guild_to_list.guild_queues.values():
            queue_names.append(queue.queue_name)
        return [app_commands.Choice(name=name, value=name) for name in queue_names if current.lower() in name.lower()]

    @commands.hybrid_command(
            name="leavequeue",
            brief="Leave a queue",
            description="Leave the current queue you are waiting in."
    )
    async def leave_queue(self,
                         ctx : commands.Context):
        """ Leave a queue """
        guildToUse : QbGuild = GuildList[ctx.guild.id]
        client_to_use = await self.check_user_parties(guildToUse, ctx)
        # Check if user is in party, and is party leader
        if client_to_use.active_queue is None:
            await ctx.send("You can't leave a queue you aren't in!", ephemeral=True)
            return
        if isinstance(client_to_use, Party) and client_to_use.user.id==ctx.author.id:
            if client_to_use.user.id != ctx.author.id:
                await ctx.send("Only the party leader can leave the queue.", ephemeral=True)
                return
            await client_to_use.active_queue.drop_members(client_to_use)
            await ctx.send("Your party has left the queue!",ephemeral=True)
        elif isinstance(client_to_use, Client):
            await client_to_use.active_queue.drop_members(client_to_use)
            await ctx.send("You've left the queue!", ephemeral=True)
        else:
            await ctx.send("You are in a party, but are not the leader", ephemeral=True)
            return

    @commands.hybrid_command(
        name="listqueues",
        brief="List all queues",
        description="List all queues for this server."
    )
    async def list_queue(self, ctx: commands.Context):
        """ List all queues for the server """
        list_guild_queues = ''
        guild_to_list: QbGuild = GuildList[ctx.guild.id]

        # Define column headers and widths
        headers = ['Queue Name', 'Lobby size', 'No. people in Queue', 'Is Global?']
        col_widths = [15, 15, 20, 10]  # Adjust these widths based on expected data length
        # Create the header row
        header_row = ''.join(f"{header:<{col_width}}" for header, col_width in zip(headers, col_widths))
        list_guild_queues += header_row
        # Add a separator row for better readability
        list_guild_queues += '\n' + '-' * sum(col_widths)
        # Add each queue's data
        for queue in guild_to_list.guild_queues.values():
            if queue.global_id in GlobalQueues.keys():
                globqueue = GlobalQueues[queue.global_id]
                row = ''.join([
                    f"{queue.queue_name:<{col_widths[0]}}"
                    f"{globqueue.min_size:<{col_widths[1]}}",
                    f"{globqueue.no_people_in_queue:<{col_widths[2]}}",
                    f"{globqueue.is_global:<{col_widths[3]}}"
                ])
                list_guild_queues += '\n' + row
            else:
                row = ''.join([
                    f"{queue.queue_name:<{col_widths[0]}}"
                    f"{queue.min_size:<{col_widths[1]}}",
                    f"{queue.no_people_in_queue:<{col_widths[2]}}",
                    f"{queue.is_global:<{col_widths[3]}}"
                ])
                list_guild_queues += '\n' + row
        try:
            if list_guild_queues.strip():
                await ctx.send(f"```{list_guild_queues}```", ephemeral=True)
                standard_logger.info("Listed queues for guild '%s'", ctx.guild.name)
            else:
                await ctx.send("There are no queues! Create one with /addqueue", ephemeral=True)
                standard_logger.info("No queues found for guild '%s'", ctx.guild.name)
        except ValueError as e:
            await ctx.send("Undefined error!")
            error_logger.error("Error listing queues for guild '%s': %s", ctx.guild.name, e)

    @commands.hybrid_command(
        name="removequeue",
        brief="Admin only -- Remove a queue",
        description="**Admin only** -- Remove a queue from the server.")
    @commands.check(owner_or_permissions(administrator=True))
    async def remove_queue(self, ctx: commands.Context, name: str = commands.parameter(description="Name of the queue to remove.")):
        """ Remove a queue from the server """
        guild_to_remove: QbGuild = GuildList[ctx.guild.id]
        for queue in guild_to_remove.guild_queues:
            if queue.queue_name == name:
                guild_to_remove.guild_queues.remove(queue)
                standard_logger.info("Queue '%s' removed by '%s' in guild '%s'", name, ctx.author, ctx.guild.name)
                print(queue.queue_index)
                delete_queue(ctx.guild.id, queue.queue_index)
                await ctx.send(f"Queue {name} removed!", ephemeral=True)
                return
        await ctx.send("Couldn't find queue!", ephemeral=True)
        error_logger.warning("Queue '%s' not found in guild '%s'", name, ctx.guild.name)
    @remove_queue.autocomplete('name')
    async def remove_queue_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """ Autocomplete the queue name """
        queue_names = []
        guild_to_list: QbGuild = GuildList[interaction.guild.id]
        for queue in guild_to_list.guild_queues.values():
            queue_names.append(queue.queue_name)
        return [app_commands.Choice(name=name, value=name) for name in queue_names if current.lower() in name.lower()]

    @commands.hybrid_command(
        name="changelobbysize",
        brief="Admin only -- Change the min/max size of a lobby",
        description="**Admin only** -- Change the minimum and maximum number of people that can be queued into a lobby."
    )
    @commands.check(owner_or_permissions(administrator=True))
    async def changelobbysize(self, ctx: commands.Context, queuename: str = commands.param(description="Queue to Change"), size: int = commands.param(description="New lobby size")):
        """ Change the lobby size """
        guild_to_check = GuildList[ctx.guild.id]
        if not queuename in guild_to_check.guild_queues:
            await ctx.send("That queue doesn't exist!", ephemeral=True)
            error_logger.warning("User %s tried to change queue in %s but it doesn't exist", ctx.author.name, ctx.guild.name)
            return
        queue_to_change = guild_to_check.guild_queues[queuename]
        queue_to_change.min_size = size
        if queue_to_change.guild.id != queue_to_change.root_guild.id:
            await ctx.send("You can't make changes to global lists you don't own.", ephemeral=True)
            return
        if queue_to_change.min_size == size:
            await ctx.send("Updated successfully!", ephemeral=True)
            return
        await ctx.send("Something went wrong! Contact support for help.")
        error_logger.error("There was an error updating a queue size in %s", ctx.guild.id)

    @changelobbysize.autocomplete('queuename')
    async def changelobbysize_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """ Autocomplete the queue name """
        queue_names = []
        guild_to_list: QbGuild = GuildList[interaction.guild.id]
        for queue in guild_to_list.guild_queues.values():
            if not queue.is_global:
                queue_names.append(queue.queue_name)
        return [app_commands.Choice(name=name, value=name) for name in queue_names if current.lower() in name.lower()]

    @commands.hybrid_command(
        name="createparty",
        brief="Create a party",
        description="Create a party to queue together"
    )
    async def create_party(self, ctx: commands.Context, partyname: str):
        """ Create a party """
        guild_to_use: QbGuild = GuildList[ctx.guild.id]
        client_check = await self.check_user_parties(ctx=ctx, guild_to_list=guild_to_use)
        if isinstance(client_check, Party):
            await ctx.send(f"You're already in a party! \nPeople can join by using: `/joinparty {client_check.party_name}` \nOr you can leave by using: `/leaveparty`", ephemeral=True)
            standard_logger.info("User '%s' attempted to create a party but is already in party '%s' in guild '%s'", ctx.author, client_check.party_name, ctx.guild.name)
            return
        if client_check.active_queue:
            await ctx.send("You can't make a party while you're in a queue! \nLeave the queue to make a party.", ephemeral=True)
            return
        new_party = Party(secret=partyname, user=ctx.author, qb_guild=guild_to_use, ctx=ctx)
        if partyname in list(guild_to_use.guild_parties.keys()):
            await ctx.send("Party already exists!", ephemeral=True)
            error_logger.warning("User '%s' attempted to create a party with an existing name '%s' in guild '%s'", ctx.author, partyname, ctx.guild.name)
            return
        guild_to_use.guild_parties[partyname] = new_party
        guild_to_use.active_members[ctx.author.id] = new_party
        if guild_to_use.guild_parties[partyname]:
            await ctx.send(f"Party `{partyname}` created!", ephemeral=True)
            standard_logger.info("Party '%s' created by user '%s' in guild '%s'", partyname, ctx.author, ctx.guild.name)
        else:
            await ctx.send("Couldn't create party!", ephemeral=True)
            error_logger.error("Failed to create party '%s' by user '%s' in guild '%s'", partyname, ctx.author, ctx.guild.name)

    @commands.hybrid_command(
        name="joinparty",
        brief="Join a party",
        description="Join a party using the name"
    )
    async def join_party(self, ctx: commands.Context, partyname: str):
        """ Join a party """
        guild_to_use: QbGuild = GuildList[ctx.guild.id]
        if guild_to_use.guild_parties[partyname]:
            new_client = Client(user=ctx.author, ctx=ctx, guild=guild_to_use)
            if new_client.user == guild_to_use.guild_parties[partyname].user or any(new_client.user == member.user for member in guild_to_use.guild_parties[partyname].members):
                await ctx.send("You're already in the party!", ephemeral=True)
                standard_logger.info("User '%s' attempted to join party '%s' but is already a member in guild: '%s'", ctx.author, partyname, ctx.guild.name)
                return
            await guild_to_use.guild_parties[partyname].add_member(new_client)
            await ctx.send(f"Joined party: {partyname}!", ephemeral=True)
            standard_logger.info("User '%s' joined party '%s' in guild: '%s'", ctx.author, partyname, ctx.guild.name)
        else:
            await ctx.send("Couldn't join party! Does it exist?", ephemeral=True)
            error_logger.warning("User '%s' attempted to join non-existent party '%s' in guild: '%s'", ctx.author, partyname, ctx.guild.name)

    @commands.hybrid_command(
        name="leaveparty",
        brief="Leave a party",
        description="Leave the party you are in."
    )
    async def leave_party(self, ctx: commands.Context):
        """ Leave a party """
        guild_to_use = GuildList[ctx.guild.id]
        party_to_leave = await self.check_user_parties(ctx=ctx, guild_to_list=guild_to_use)
        if isinstance(party_to_leave, Client):
            await ctx.send("You're not in a party in this server")
            return
        if ctx.author.id == party_to_leave.user.id:
            await party_to_leave.disband()
            await ctx.send("Your party has been disbanded!")
            return
        client_to_remove = Client(ctx.author, ctx, guild_to_use)
        await party_to_leave.remove_member(client_to_remove)
        await ctx.send("You've left the party.")

    @commands.hybrid_command(
        name="partyinfo",
        brief="Get party information",
        description="Get information on a party"
    )
    async def party_info(self, ctx: commands.Context):
        """ Get party information """
        party_to_check = await self.check_user_parties(GuildList[ctx.guild.id], ctx)
        if isinstance(party_to_check, Client):
            await ctx.send("You're not in a party!", ephemeral=True)
            standard_logger.info("User '%s' attempted to get party info but is not in a party in guild '%s'", ctx.author, ctx.guild.name)
            return
        party_members = '```'
        headers = ['', 'User']
        col_widths = [3, 15]
        header_row = ''.join(f"{header:^{col_width}}" for header, col_width in zip(headers, col_widths))
        party_members += header_row
        party_members += '\n' + '-' * sum(col_widths)
        f_row = ''.join([
            "* ",
            f"|{party_to_check.user.name:^{col_widths[1]}}"
        ])
        party_members += '\n' + f_row
        for member in party_to_check.members:
            row = ''.join([
            "  ",
            f"| {member.user.name:^{col_widths[1]}}"
            ])
            party_members += '\n' + row
        party_members += '```'
        await ctx.send(party_members, ephemeral=True)
        standard_logger.info("User '%s' requested party info for party '%s' in guild '%s'", ctx.author, party_to_check.party_name, ctx.guild.name)

    @commands.hybrid_command(
        name="queueinfo",
        brief="Get queue information",
        description="Get information on a queue"
    )
    async def queue_info(self, ctx: commands.Context, queuename: str):
        """ Get queue information """
        guild_to_use: QbGuild = GuildList[ctx.guild.id]
        for queue in guild_to_use.guild_queues:
            if queue.queue_name == queuename:
                await ctx.send(queue.info(), ephemeral=True)
                standard_logger.info("Queue info for '%s' requested by '%s' in guild '%s'", queuename, ctx.author, ctx.guild.name)
                return
        await ctx.send("Couldn't find queue!", ephemeral=True)
        error_logger.warning("Queue '%s' not found in guild '%s' requested by '%s'", queuename, ctx.guild.name, ctx.author)

    @queue_info.autocomplete('queuename')
    async def queueinfo_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """ Autocomplete the queue name """
        queue_names = []
        guild_to_list: QbGuild = GuildList[interaction.guild.id]
        for queue in guild_to_list.guild_queues.values():
            queue_names.append(queue.queue_name)
        return [app_commands.Choice(name=name, value=name) for name in queue_names if current.lower() in name.lower()]

    @commands.hybrid_command(
        name="registerqueue",
        brief="Register a queue",
        description="Register a queue as global."
    )
    @commands.has_permissions(administrator=True)
    async def registerqueue(self, ctx: commands.Context, queuename: str):
        """ Register a queue as global """
        guild_to_use: QbGuild = GuildList[ctx.guild.id]
        queue = guild_to_use.guild_queues[queuename]

        if queue:
            queue.global_id = self.gen_global_id(queue)
            if queue.global_id in GlobalQueues:
                await ctx.send("There seems to be a queue with that ID already. \nThat shouldn't happen! Please contact support for help", ephemeral=True)
                error_logger.error("%s in guild `%s` tried to register a queue with global id `%s` but that already exists.", ctx.author.name, guild_to_use.disc_guild.name, queue.global_id)
                return
            queue.is_global = True
            GlobalQueues[queue.global_id] = queue
            await ctx.send(f"Registered {queuename} as global queue!", ephemeral=True)
            standard_logger.info("Queue '%s' registered as global queue by '%s' in guild '%s'", queuename, ctx.author, ctx.guild.name)
            return
        await ctx.send("Couldn't find queue!", ephemeral=True)
        error_logger.warning("Queue '%s' not found in guild '%s' requested by '%s'", queuename, ctx.guild.name, ctx.author)
    @registerqueue.autocomplete('queuename')
    async def registerqueue_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """ Autocomplete the queue name """
        queue_names = []
        guild_to_list: QbGuild = GuildList[interaction.guild.id]
        for queue in guild_to_list.guild_queues.values():
            if not queue.is_global:
                queue_names.append(queue.queue_name)
        return [app_commands.Choice(name=name, value=name) for name in queue_names if current.lower() in name.lower()]

    @commands.hybrid_command(
        name="listglobal",
        brief="List global queues",
        description="List all global queues."
    )
    async def listglobal(self, ctx: commands.Context):
        """ List all global queues """
        global_queue_list = ''
        headers = ['Queue Name', 'Queue Subject', 'Lobby Size', 'No. people in Queue', 'Queue Code']
        col_widths = [15, 20, 15, 20, 15]
        global_queue_list = ''.join([f"{header:^{col_widths[i]}}" for i, header in enumerate(headers)])
        if len(GlobalQueues) == 0:
            await ctx.send("No global queues found!", ephemeral=True)
            return
        for queue in GlobalQueues.values():
            row = ''.join([
                f"{queue.queue_name:^{col_widths[0]}}",
                f"{queue.queue_type:^{col_widths[1]}}",
                f"{queue.min_size:^{col_widths[2]}}",
                f"{len(queue.people_in_queue):^{col_widths[3]}}",
                f"{encode_base62(int(queue.global_id)):^{col_widths[4]}}"
            ])
            global_queue_list += '\n' + row
        await ctx.send(f"```{global_queue_list}```", ephemeral=True)

    @commands.hybrid_command(name="subqueue",
                             brief="Subscribe a global queue",
                             description="Subscribe the server to a global queue")
    async def subqueue(self, ctx: commands.Context, code : str = commands.param(description="Queue Code"), name : str = commands.param(description="Name to have in this server")):
        """Subscribe to a global queue to access it in any server."""
        code = code.strip()
        code = decode_base62(code)
        if not code in GlobalQueues.keys():
            await ctx.send("Sorry! There doesn't seem to be a queue with that code. Are you sure it's correct?", ephemeral=True)
            return
        if GlobalQueues[int(code)].guild.id == ctx.guild.id:
            await ctx.send("You can't subscribe to your own queue.")
            return
        guild_to_use :QbGuild = GuildList[ctx.guild.id]
        for queue in guild_to_use.guild_queues.values():
            if queue.is_global:
                if queue.global_id == int(code):
                    await ctx.send("You are already subscribed to this queue!")
                    return
        queue_to_add :Queue = GlobalQueues[code]
        new_queue : Queue = Queue(name=name,
                                guild=ctx.guild,
                                owner=queue_to_add.guild,
                                queue_type=queue_to_add.queue_type,
                                identifier=len(guild_to_use.guild_queues),
                                min_size=queue_to_add.min_size,
                                max_size=queue_to_add.max_size,
                                global_queue=True,
                                global_id = queue_to_add.global_id  )
        if new_queue.queue_name in guild_to_use.guild_queues.keys():
            await ctx.send(f"There's already a queue with the name {new_queue.queue_name} in this server. Please remove it to subscribe to this queue.")
            return
        guild_to_use.guild_queues[new_queue.queue_name] = new_queue
        await ctx.send(f"{guild_to_use.guild_queues[new_queue.queue_name].queue_name} has been registered! Members can now join with /joinqueue", ephemeral=True)

    @add_queue.error
    async def add_queue_error(self, ctx: commands.Context, error: commands.CommandError):
        """ Error handling for add_queue """
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Sorry. Only the server owner and admins can add queues.", ephemeral=True)
            print(error)

async def setup(bot: commands.Bot):
    """ Add the GuildWrapper cog to the bot """
    await bot.add_cog(GuildWrapper(bot))

atexit.register(end_program, GuildList)
