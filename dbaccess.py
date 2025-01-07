import os
from urllib.parse import urlparse
import mariadb
from dotenv import load_dotenv
from cogs.guild import QbGuild
import settings

standard_logger = settings.logging.getLogger("discord")
error_logger = settings.logging.getLogger("bot")

loadedGuilds = {}
loadedUsers = {}

def getConn():
    # Load environment variable
    load_dotenv()
    database_url = os.getenv('DATABASE_URL')

    # Parse the DATABASE_URL
    if database_url:
        parsed_url = urlparse(database_url)

        USER = parsed_url.username
        PASSWORD = parsed_url.password
        HOST = parsed_url.hostname
        PORT = int(parsed_url.port)  
        SCHEMA = parsed_url.path.lstrip("/")  

        
        try:
            conn = mariadb.connect(
                user=USER,
                password=PASSWORD,
                host=HOST,
                port=PORT,
                database=SCHEMA
            )
            standard_logger.info("Connection successful!")
            return conn
        
        except mariadb.Error as e:
            error_logger.error(f"Error connecting to the database: {e}")

    else:
        error_logger.error("DATABASE_URL is not set in the environment.")  

def saveProgram(guildDict):
    conn = getConn()
    try:
        if conn:
            standard_logger.info("Saving data to the database...")
            cursor = conn.cursor()

            for guildId, guild in guildDict.items():
                # Query to insert or update the guild
                guildInsertOrUpdateQuery = """
                INSERT INTO Guild (GuildId, OwnerId)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE
                    GuildId = VALUES(GuildId),
                    OwnerId = VALUES(OwnerId)
                """
                # Log guild data for debugging
                error_logger.info(f"Inserting/updating guild: {guildId}, {guild.discGuild.owner.id}")
                
                # Values to be inserted or updated
                guildValues = (guildId, guild.discGuild.owner.id)
                
                # Execute the guild query
                cursor.execute(guildInsertOrUpdateQuery, guildValues)

                # Insert or update each queue for this guild
                if len(guild.GuildQueues) > 0:
                    for queue in guild.GuildQueues:  # Assuming `queues` is a list of queue objects in the guild
                        queueInsertOrUpdateQuery = """
                        INSERT INTO queues (GuildId, QueueName, QueueId, QueueType, QueueMin, QueueMax, IsGlobal, GlobalID)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            GuildId = VALUES(GuildId),
                            QueueName = VALUES(QueueName),
                            QueueType = VALUES(QueueType),
                            QueueId = VALUES(QueueId),
                            QueueMin = VALUES(QueueMin),
                            QueueMax = VALUES(QueueMax),
                            IsGlobal = VALUES(IsGlobal),
                            GlobalID = VALUES(GlobalID)
                        """
                        # Log queue data for debugging
                        error_logger.info(f"Inserting/updating queue: GuildId={guild.discGuild.id}, QueueName={queue.QueueName}, QueueId={queue.QueueIndex}, QueueType={queue.QueueType}, QueueMax={queue.MaxSize}, QueueMin={queue.MinSize}, IsGlobal={queue.IsGlobal}, GlobalID={queue.GlobalId}")
                        
                        # Values to be inserted or updated
                        queueValues = (guild.discGuild.id, queue.QueueName, queue.QueueIndex, queue.QueueType, queue.MinSize, queue.MaxSize, queue.IsGlobal, queue.GlobalId)
                        
                        # Execute the queue query
                        cursor.execute(queueInsertOrUpdateQuery, queueValues)

            # Commit the transaction
            conn.commit()
            error_logger.info("Transaction committed successfully.")
        else:
            error_logger.error("No connection to the database.")
    except mariadb.Error as e:
        error_logger.error(f"Error executing query: {e}")
        if conn:
            conn.rollback()  # Rollback the transaction on error
            error_logger.error("Transaction rolled back.")
    finally:
        if conn:
            conn.close()
            error_logger.warning("Database connection closed.")

def endProgram(guildDict):
    conn = getConn()
    try:
        if conn:
            standard_logger.info("Trying to get cursor")
            cursor = conn.cursor()

            for guildId, guild in guildDict.items():
                # Query to insert or update the guild
                guildInsertOrUpdateQuery = """
                INSERT INTO Guild (GuildId, OwnerId)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE
                    GuildId = VALUES(GuildId),
                    OwnerId = VALUES(OwnerId)
                """
                # Log guild data for debugging
                standard_logger.info(f"Inserting/updating guild: {guildId}, {guild.discGuild.owner.id}")
                
                # Values to be inserted or updated
                guildValues = (guildId, guild.discGuild.owner.id)
                
                # Execute the guild query
                cursor.execute(guildInsertOrUpdateQuery, guildValues)

                # Insert or update each queue for this guild
                if len(guild.GuildQueues) > 0:
                    for queue in guild.GuildQueues:  # Assuming `queues` is a list of queue objects in the guild
                        queueInsertOrUpdateQuery = """
                        INSERT INTO queues (GuildId, QueueName, QueueId, QueueType, QueueMin, QueueMax, IsGlobal, GlobalID)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            GuildId = VALUES(GuildId),
                            QueueName = VALUES(QueueName),
                            QueueType = VALUES(QueueType),
                            QueueId = VALUES(QueueId),
                            QueueMin = VALUES(QueueMin),
                            QueueMax = VALUES(QueueMax),
                            IsGlobal = VALUES(IsGlobal),
                            GlobalID = VALUES(GlobalID)

                        """
                        # Log queue data for debugging
                        standard_logger.info(f"Inserting/updating queue: GuildId={guild.discGuild.id}, QueueName={queue.QueueName}, QueueId={queue.QueueIndex}, QueueType={queue.QueueType}, QueueMax={queue.MaxSize}, QueueMin={queue.MinSize}, IsGlobal={queue.IsGlobal}, GlobalID={queue.GlobalId}")
                        
                        # Values to be inserted or updated
                        queueValues = (guild.discGuild.id, queue.QueueName, queue.QueueIndex, queue.QueueType, queue.MinSize, queue.MaxSize, queue.IsGlobal, queue.GlobalId)
                        
                        # Execute the queue query
                        cursor.execute(queueInsertOrUpdateQuery, queueValues)

            # Commit the transaction
            conn.commit()
            standard_logger.info("Transaction committed successfully.")
        else:
            standard_logger.error("No connection to the database.")
    except mariadb.Error as e:
        standard_logger.error(f"Error executing query: {e}")
        if conn:
            conn.rollback()  # Rollback the transaction on error
            standard_logger.error("Transaction rolled back.")
    finally:
        if conn:
            conn.close()
            standard_logger.warning("Database connection closed.")

async def getList():
    conn = getConn()

    if conn:
        cursor = conn.cursor(dictionary=True)  # Use dictionary cursor for easier row access
        guildDict = {}

        try:
            # Retrieve guild information
            guildStatement = "SELECT GuildId, OwnerId FROM Guild"
            cursor.execute(guildStatement)
            guilds = cursor.fetchall()

            # Retrieve queues and group them by GuildId
            queueStatement = "SELECT GuildId, QueueId, QueueName, QueueType, QueueMin, QueueMax, IsGlobal, GlobalID FROM queues"
            cursor.execute(queueStatement)
            queues = cursor.fetchall()

            # Create a mapping of GuildId to its queues
            queueMap = {}
            for queue in queues:
                guild_id = queue['GuildId']
                if guild_id not in queueMap:
                    queueMap[guild_id] = []
                queueMap[guild_id].append(queue)

            # Combine guild information with their queues
            for guild_data in guilds:
                guild_id = guild_data['GuildId']
                guild_data['queues'] = queueMap.get(guild_id, [])  # Add queues to the guild
                guildDict[guild_id] = guild_data

        except Exception as e:
            error_logger.error(f"Error retrieving entry from database: {e}")
        finally:
            cursor.close()
            conn.close()

        return guildDict
