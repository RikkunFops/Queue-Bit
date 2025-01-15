import os
import threading
import discord
from discord import app_commands
from discord.ext import commands
from classes import QbGuild, Queue, Client, Party
import time
import settings
import atexit
from dbaccess import end_program, save_program, delete_queue

standard_logger = settings.logging.getLogger("discord")
error_logger = settings.logging.getLogger("bot")

global GuildList
GuildList : QbGuild = {}
GlobalQueues : Queue = {}

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
        """ Load the guilds from the database """
        for guild_id, guild_data in load_dict.items():
            discord_guild: QbGuild = self.bot.get_guild(guild_id)

            if discord_guild:
                # Create a Guild instance
                guild_instance = QbGuild(discord_guild, self.bot)
                standard_logger.info(f"Loading {guild_instance.disc_guild.name}")

                # Add queues to the Guild instance if available
                if 'queues' in guild_data:
                    standard_logger.info(f"Listing queues in {guild_instance.disc_guild.id}")
                    standard_logger.info(" Queue name | Queue type | Queue ID")
                    for queue_data in guild_data['queues']:
                        queue_id = queue_data['QueueId']
                        queue_name = queue_data['QueueName']
                        queue_type = queue_data['QueueType']
                        queue_max = queue_data['QueueMax']
                        queue_min = queue_data['QueueMin']
                        is_global = queue_data['IsGlobal']
                        bool_glob = bool(is_global)
                        global_id = queue_data['GlobalID']

                        if bool_glob:
                            new_queue = Queue(guild=discord_guild, name=queue_name, queue_type=queue_type, identifier=queue_id, min_size=queue_min, max_size=queue_max, global_queue=True)
                            standard_logger.info(f"{new_queue.queue_name:^12}|{new_queue.queue_type:^12}|{new_queue.queue_index:^12}")
                            guild_instance.guild_queues.append(new_queue)
                        else:
                            new_queue = Queue(guild=discord_guild, name=queue_name, queue_type=queue_type, identifier=queue_id, min_size=queue_min, max_size=queue_max, global_queue=False)
                            standard_logger.info(f"{new_queue.queue_name:^12}|{new_queue.queue_type:^12}|{new_queue.queue_index:^12}")
                            guild_instance.guild_queues.append(new_queue)

                # Add the guild instance to the GuildList
                GuildList[guild_id] = guild_instance

        self.save_thread = threading.Thread(target=save_guilds, daemon=True)
        self.save_thread.start()

    def new_guild(self, new_guild):
        """ Add a new guild to the GuildList """
        for check_guild in list(GuildList.values()):
            if new_guild.id == check_guild.disc_guild.id:
                return
        new_guild = QbGuild(new_guild, self.bot)
        GuildList[new_guild.disc_guild.id] = new_guild
        standard_logger.info(f"Added new guild: {GuildList[new_guild.disc_guild.id]}")

    def check_user_queues(self, client: Client):
        """ Check if a user is in a queue """
        guild_to_search = client.qb_guild
        for queues in guild_to_search.guild_queues:
            for user in queues.people_in_queue:
                if user.user == client.user:
                    return True
        return False

    def check_user_parties(self, client: Client):
        """ Check if a user is in a party """
        guild_to_search = client.qb_guild
        for party in list(guild_to_search.guild_parties.values()):
            if client.user == party.user:
                return True, True, party
            for user in party.members:
                if user.user == client.user:
                    return True, False, party
        return False

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
    @commands.has_permissions(administrator=True)
    async def add_queue(self, ctx: commands.Context, *, name: str = commands.parameter(description="Name of your queue."),
                        activity: str = commands.parameter(description="What are we queueing for?"),
                        lobbysize: int = commands.parameter(description="Minimum lobby size")):
        """ Add a queue to the server """
        successful = None
        queuebit_guild = GuildList[ctx.guild.id]
        try:
            new_identifier = len(queuebit_guild.guild_queues)
            new_queue = Queue(guild=queuebit_guild, name=name, queue_type=activity, identifier=new_identifier, min_size=lobbysize, max_size=lobbysize, global_queue=False)
            queuebit_guild.guild_queues.append(new_queue)
            successful = True
        except Exception as e:
            successful = False
            error_logger.error(f"Error {e}")
        finally:
            if successful:
                await ctx.send(f"Successfully added list {queuebit_guild.guild_queues[-1].queue_name}", ephemeral=True)

    @commands.hybrid_command(
        name="joinqueue",
        description="Join a queue. If the queue you want to join isn't listed, ask an admin to add it for you.",
        brief="Join a queue"
    )
    async def join_queue(self, ctx: commands.Context, name: str = commands.parameter(description="Which queue?")):
        """ Join a queue """
        guild_to_list: QbGuild = GuildList[ctx.guild.id]
        queue_to_join: Queue = None
        test_client = Client(user=ctx.author, queue=queue_to_join, ctx=ctx, guild=guild_to_list)
        party_status = self.check_user_parties(test_client)
        new_client = None
        if not party_status:
            new_client = Client(user=ctx.author, queue=queue_to_join, ctx=ctx, guild=guild_to_list)
        elif party_status[0]:
            if not party_status[1]:
                await ctx.send("Only a party leader can join the queue!", ephemeral=True)
                return
            elif party_status[1]:
                new_client = party_status[2]
        for queue in guild_to_list.guild_queues:
            if queue.queue_name.lower() == name.lower():
                queue_to_join = queue
                break
        if not queue_to_join:
            await ctx.send("Couldn't join the queue! Are you sure this queue exists?", ephemeral=True)
            error_logger.error(f"Queue '{name}' does not exist in guild '{ctx.guild.name}'")
            return

        if self.check_user_queues(new_client):
            await ctx.send("You're already queuing! Leave the current queue before requeuing with /leavequeue.", ephemeral=True)
            error_logger.warning(f"User '{ctx.author}' is already in a queue in guild '{ctx.guild.name}'")
            return
        else:
            queue_to_join.people_in_queue.append(new_client)
            if isinstance(new_client, Party):
                new_client.active_queue = queue_to_join
                queue_to_join.no_people_in_queue += new_client.size
            elif isinstance(new_client, Client):
                queue_to_join.no_people_in_queue += 1

            if queue_to_join.no_people_in_queue != queue_to_join.max_size * 5:
                await ctx.send(f"You've joined {queue_to_join.queue_name}! \nThere aren't many people, though. \nThis may take a moment! {queue_to_join.no_people_in_queue}", ephemeral=True)
                standard_logger.info(f"User '{ctx.author}' joined queue '{queue_to_join.queue_name}' in guild '{ctx.guild.name}' with {queue_to_join.no_people_in_queue} people in queue")
            else:
                await ctx.send(f"You've joined {queue_to_join.queue_name}! Shouldn't take long. {queue_to_join.no_people_in_queue}", ephemeral=True)
                standard_logger.info(f"User '{ctx.author}' joined queue '{queue_to_join.queue_name}' in guild '{ctx.guild.name}' with {queue_to_join.no_people_in_queue} people in queue")
            await queue_to_join.try_queue()

    @join_queue.autocomplete('name')
    async def queuename_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """ Autocomplete the queue name """
        queue_names = []
        guild_to_list: QbGuild = GuildList[interaction.guild.id]
        for queue in guild_to_list.guild_queues:
            name = queue.queue_name
            queue_names.append(queue.queue_name)
        return [app_commands.Choice(name=name, value=name) for name in queue_names if current.lower() in name.lower()]
    @commands.hybrid_command(
            name="leavequeue",
            brief="Leave a queue",
            description="Leave the current queue you are waiting in."
    )
    async def leaveQueue(self, 
                         ctx : commands.Context):
        """ Leave a queue """
        guildToUse : QbGuild = GuildList[ctx.guild.id]
        ClientToCheck = Client(user=ctx.author, ctx=ctx, guild=guildToUse)
        results = self.check_user_parties(ClientToCheck)
        if not results:
            for queues in guildToUse.guild_queues:
                for users in queues.people_in_queue:
                    if ctx.author == users.user:
                        await queues.remove_from_list(users)
                        queues.no_people_in_queue -= 1
                        standard_logger.info(f"User '{ctx.author}' left queue '{queues.queue_name}' in guild '{ctx.guild.name}'")
                        await ctx.send(f"You have left the queue: {queues.queue_name}.", ephemeral=True)
                        return
            
            await ctx.send(f"You aren't in a queue!", ephemeral=True)
            error_logger.warning(f"User '{ctx.author}' attempted to leave a queue in guild '{ctx.guild.name}' but is not in any queue")
        else:
            clientToLeave = results[2]
            if results[1]:
                queueToLeave = clientToLeave.active_queue
                if not queueToLeave:
                    await ctx.send("You're not in a queue!", ephemeral=True)
                    error_logger.warning(f"User '{ctx.author}' attempted to leave a queue in guild '{ctx.guild.name}' but is not in any queue")
                    return
                await queueToLeave.remove_from_list(clientToLeave)
                queueToLeave.no_people_in_queue -= (len(clientToLeave.members)+1)
                standard_logger.info(f"Party '{clientToLeave.party_name}' left queue '{queueToLeave.queue_name}' in guild '{ctx.guild.name}'")
                await ctx.send(f"Your party has left the queue: {queueToLeave.queue_name}.", ephemeral=True)
                return
            else:
                queueToLeave = clientToLeave.active_queue
                if queueToLeave:
                    await ctx.send("Only a party leader can leave the queue!", ephemeral=True)
                    error_logger.warning(f"User '{ctx.author}' attempted to leave queue '{queueToLeave.queue_name}' in guild '{ctx.guild.name}' but is not the party leader")
                else:
                    await ctx.send("You're not in a queue! Plus, only the party leader can leave queues!", ephemeral=True)
                    error_logger.warning(f"User '{ctx.author}' attempted to leave queue but party is not in a queue in guild '{ctx.guild.name}'")
         
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
        headers = ['Queue Name', 'Minimum size', 'Maximum size', 'No. people in Queue']
        col_widths = [15, 15, 15, 20]  # Adjust these widths based on expected data length

        # Create the header row
        header_row = ''.join(f"{header:<{col_width}}" for header, col_width in zip(headers, col_widths))
        list_guild_queues += header_row
        
        # Add a separator row for better readability
        list_guild_queues += '\n' + '-' * sum(col_widths)
        
        # Add each queue's data
        for queue in guild_to_list.guild_queues:
            row = ''.join([
                f"{queue.queue_name:<{col_widths[0]}}",
                f"{queue.min_size:<{col_widths[1]}}",
                f"{queue.max_size:<{col_widths[2]}}",
                f"{len(queue.people_in_queue):<{col_widths[3]}}"
            ])
            list_guild_queues += '\n' + row

        try:
            if list_guild_queues.strip():
                await ctx.send(f"```{list_guild_queues}```", ephemeral=True)
                standard_logger.info(f"Listed queues for guild '{ctx.guild.name}'")
            else:
                await ctx.send("There are no queues! Create one with /addqueue", ephemeral=True)
                standard_logger.info(f"No queues found for guild '{ctx.guild.name}'")
        except Exception as e:
            await ctx.send("Undefined error!")
            error_logger.error(f"Error listing queues for guild '{ctx.guild.name}': {e}")

    @commands.hybrid_command(
        name="removequeue",
        brief="Admin only -- Remove a queue",
        description="**Admin only** -- Remove a queue from the server.")
    @commands.has_permissions(administrator=True)
    async def remove_queue(self, ctx: commands.Context, name: str = commands.parameter(description="Name of the queue to remove.")):
        """ Remove a queue from the server """
        guild_to_remove: QbGuild = GuildList[ctx.guild.id]
        for queue in guild_to_remove.guild_queues:
            if queue.queue_name == name:
                guild_to_remove.guild_queues.remove(queue)
                
                standard_logger.info(f"Queue '{name}' removed by '{ctx.author}' in guild '{ctx.guild.name}'")
                print(queue.queue_index)
                delete_queue(ctx.guild.id, queue.queue_index)
                await ctx.send(f"Queue {name} removed!", ephemeral=True)
                return
        await ctx.send("Couldn't find queue!", ephemeral=True)
        error_logger.warning(f"Queue '{name}' not found in guild '{ctx.guild.name}'")
    @remove_queue.autocomplete('name')
    async def queuename_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """ Autocomplete the queue name """
        queue_names = []
        guild_to_list: QbGuild = GuildList[interaction.guild.id]
        if len(guild_to_list.guild_queues) == 0:
            return [app_commands.Choice(name="No queues found", value="No queues found")]
        for queue in guild_to_list.guild_queues:
            queue_names.append(queue.queue_name)
        return [app_commands.Choice(name=name, value=name) for name in queue_names if current.lower() in name.lower()]


    @commands.hybrid_command(
        name="changelobbysize",
        brief="Admin only -- Change the min/max size of a lobby",
        description="**Admin only** -- Change the minimum and maximum number of people that can be queued into a lobby."
    )
    @commands.has_permissions(administrator=True)
    async def changelobbysize(self, ctx: commands.Context, queuename: str = commands.param(description="Queue to Change"), size: int = commands.param(description="Minimum lobby size")):
        """ Change the lobby size """
        guild_to_check = GuildList[ctx.guild.id]

        for queue in guild_to_check.guild_queues:
            if queue.queue_name == queuename:
                queue.min_size = size
                await ctx.send("Successfully updated!", ephemeral=True)
                standard_logger.info(f"Queue '{queuename}' lobby size updated to {size} by '{ctx.author}' in guild '{ctx.guild.name}'")
                return

        await ctx.send("Couldn't update minmax! Please contact support for help.", ephemeral=True)
        error_logger.error(f"Failed to update lobby size for queue '{queuename}' in guild '{ctx.guild.name}'")

    @changelobbysize.autocomplete('queuename')
    async def queuename_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """ Autocomplete the queue name """
        queue_names = []
        guild_to_list: QbGuild = GuildList[interaction.guild.id]
        if len(guild_to_list.guild_queues) == 0:
            return [app_commands.Choice(name="No queues found", value="No queues found")]
        for queue in guild_to_list.guild_queues:
            queue_names.append(queue.queue_name)
        return [app_commands.Choice(name=name, value=name) for name in queue_names if current.lower() in name.lower()]

    @commands.hybrid_command(
        name="createparty",
        brief="Create a party",
        description="Create a party to queue together"
    )
    async def createparty(self, ctx: commands.Context, partyname: str):
        """ Create a party """
        guild_to_use: QbGuild = GuildList[ctx.guild.id]
        client_check = Client(user=ctx.author, ctx=ctx, guild=guild_to_use)
        result = self.check_user_parties(client_check)
        if result:
            await ctx.send(f"You're already in a party! \nPeople can join by using: `/joinparty {result[2].party_name}` \nOr you can leave by using: `/leaveparty`", ephemeral=True)
            standard_logger.info(f"User '{ctx.author}' attempted to create a party but is already in party '{result[2].party_name}' in guild '{ctx.guild.name}'")
            return
        new_party = Party(secret=partyname, user=ctx.author, qb_guild=guild_to_use, ctx=ctx)
        if partyname in guild_to_use.guild_parties:
            await ctx.send("Party already exists!", ephemeral=True)
            error_logger.warning(f"User '{ctx.author}' attempted to create a party with an existing name '{partyname}' in guild '{ctx.guild.name}'")
            return

        guild_to_use.guild_parties[partyname] = new_party
        if guild_to_use.guild_parties[partyname]:
            await ctx.send(f"Party `{partyname}` created!", ephemeral=True)
            standard_logger.info(f"Party '{partyname}' created by user '{ctx.author}' in guild '{ctx.guild.name}'")
        else:
            await ctx.send("Couldn't create party!", ephemeral=True)
            error_logger.error(f"Failed to create party '{partyname}' by user '{ctx.author}' in guild '{ctx.guild.name}'")

    @commands.hybrid_command(
        name="joinparty",
        brief="Join a party",
        description="Join a party using the name"
    )
    async def joinparty(self, ctx: commands.Context, partyname: str):
        """ Join a party """
        guild_to_use: QbGuild = GuildList[ctx.guild.id]
        if partyname in guild_to_use.guild_parties:
            new_client = Client(user=ctx.author, ctx=ctx, guild=guild_to_use)
            if new_client.user == guild_to_use.guild_parties[partyname].user or any(new_client.user == member.user for member in guild_to_use.guild_parties[partyname].members):
                await ctx.send("You're already in the party!", ephemeral=True)
                standard_logger.info(f"User '{ctx.author}' attempted to join party '{partyname}' but is already a member in guild: '{ctx.guild.name}'")
                return

            await guild_to_use.guild_parties[partyname].add_member(new_client)
            await ctx.send(f"Joined party: {partyname}!", ephemeral=True)
            standard_logger.info(f"User '{ctx.author}' joined party '{partyname}' in guild: '{ctx.guild.name}'")
        else:
            await ctx.send("Couldn't join party! Does it exist?", ephemeral=True)
            error_logger.warning(f"User '{ctx.author}' attempted to join non-existent party '{partyname}' in guild: '{ctx.guild.name}'")

    @commands.hybrid_command(
        name="leaveparty",
        brief="Leave a party",
        description="Leave the party you are in."
    )
    async def leaveparty(self, ctx: commands.Context):
        """ Leave a party """
        party_to_leave = self.check_user_parties(Client(user=ctx.author, ctx=ctx, guild=GuildList[ctx.guild.id]))
        if not party_to_leave:
            await ctx.send("You're not in a party!", ephemeral=True)
            standard_logger.info(f"User '{ctx.author}' attempted to leave a party but is not in a party in guild '{ctx.guild.name}'")
            return
        if party_to_leave[1]:
            await party_to_leave[2].disband()
            await ctx.send("The party disbanded!", ephemeral=True)
            standard_logger.info(f"User '{ctx.author}' disbanded party '{party_to_leave[2].party_name}' in guild '{ctx.guild.name}'")
        else:
            new_client = Client(user=ctx.author, ctx=ctx, guild=GuildList[ctx.guild.id])
            await party_to_leave[2].remove_member(new_client)
            await ctx.send("You've left the party!", ephemeral=True)
            standard_logger.info(f"User '{ctx.author}' left party '{party_to_leave[2].party_name}' in guild '{ctx.guild.name}'")

    @commands.hybrid_command(
        name="partyinfo",
        brief="Get party information",
        description="Get information on a party"
    )
    async def partyinfo(self, ctx: commands.Context):
        """ Get party information """
        party_to_check = self.check_user_parties(Client(user=ctx.author, ctx=ctx, guild=GuildList[ctx.guild.id]))
        if not party_to_check:
            await ctx.send("You're not in a party!", ephemeral=True)
            standard_logger.info(f"User '{ctx.author}' attempted to get party info but is not in a party in guild '{ctx.guild.name}'")
            return
        party = party_to_check[2]
        party_members = '```'

        headers = ['', 'User']
        col_widths = [3, 15]

        header_row = ''.join(f"{header:^{col_width}}" for header, col_width in zip(headers, col_widths))
        party_members += header_row
        party_members += '\n' + '-' * sum(col_widths)

        f_row = ''.join([
            f"* ",
            f"|{party.user.name:^{col_widths[1]}}"
        ])
        party_members += '\n' + f_row

        for member in party.members:
            row = ''.join([
                f"  ",
                f"| {member.user.name:^{col_widths[1]}}"
            ])
            party_members += '\n' + row
        party_members += '```'

        await ctx.send(party_members, ephemeral=True)
        standard_logger.info(f"User '{ctx.author}' requested party info for party '{party.party_name}' in guild '{ctx.guild.name}'")

    @commands.hybrid_command(
        name="queueinfo",
        brief="Get queue information",
        description="Get information on a queue"
    )
    async def queueinfo(self, ctx: commands.Context, queuename: str):
        """ Get queue information """
        guild_to_use: QbGuild = GuildList[ctx.guild.id]
        for queue in guild_to_use.guild_queues:
            if queue.queue_name == queuename:
                await ctx.send(queue.info(), ephemeral=True)
                standard_logger.info(f"Queue info for '{queuename}' requested by '{ctx.author}' in guild '{ctx.guild.name}'")
                return
        await ctx.send("Couldn't find queue!", ephemeral=True)
        error_logger.warning(f"Queue '{queuename}' not found in guild '{ctx.guild.name}' requested by '{ctx.author}'")

    @queueinfo.autocomplete('queuename')
    async def queuename_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """ Autocomplete the queue name """
        queue_names = []
        guild_to_list: QbGuild = GuildList[interaction.guild.id]
        if len(guild_to_list.guild_queues) == 0:
            return [app_commands.Choice(name="No queues found", value="No queues found")]
        for queue in guild_to_list.guild_queues:
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
        for queue in guild_to_use.guild_queues:
            if queue.queue_name == queuename:
                queue.global_id = self.gen_global_id(queue)
                GlobalQueues[queue.global_id] = queue
                await ctx.send(f"Registered {queuename} as global queue!", ephemeral=True)
                standard_logger.info(f"Queue '{queuename}' registered as global queue by '{ctx.author}' in guild '{ctx.guild.name}'")
                return
        await ctx.send("Couldn't find queue!", ephemeral=True)
        error_logger.warning(f"Queue '{queuename}' not found in guild '{ctx.guild.name}' requested by '{ctx.author}'")

    @registerqueue.autocomplete('queuename')
    async def queuename_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """ Autocomplete the queue name """
        queue_names = []
        guild_to_list: QbGuild = GuildList[interaction.guild.id]
        if len(guild_to_list.guild_queues) == 0:
            return [app_commands.Choice(name="No queues found", value="No queues found")]
        for queue in guild_to_list.guild_queues:
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

        headers = ['Queue Name', 'Queue Subject', 'Lobby Size', 'No. people in Queue', 'Queue ID']
        col_widths = [15, 20, 15, 20, 25]

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
                f"{queue.global_id:^{col_widths[4]}}"
            ])
            global_queue_list += '\n' + row

        await ctx.send(f"```{global_queue_list}```", ephemeral=True)

    @add_queue.error
    async def add_queue_error(self, ctx: commands.Context, error: commands.CommandError):
        """ Error handling for add_queue """
        if isinstance(error, commands.CommandError):
            await ctx.send("Sorry. Only admins can add queues.", ephemeral=True)

async def setup(bot: commands.Bot):
    """ Add the GuildWrapper cog to the bot """
    await bot.add_cog(GuildWrapper(bot))

atexit.register(end_program, GuildList)
