import os
from urllib.parse import urlparse
import mariadb
from dotenv import load_dotenv
from cogs.guild import QbGuild

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
            print("Connection successful!")
            return conn
        
        except mariadb.Error as e:
            print(f"Error connecting to the database: {e}")

    else:
        print("DATABASE_URL is not set in the environment.")

    

def endProgram(guildList):
    conn = getConn()
    try:
        if conn:
            print("Trying to get cursor")
            cursor = conn.cursor()

            for guild in guildList:
                # Query to insert or update the guild
                guildInsertOrUpdateQuery = """
                INSERT INTO Guild (GuildId, OwnerId, IsSetup)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    OwnerId = VALUES(OwnerId),
                    IsSetup = VALUES(IsSetup)
                """
                # Log guild data for debugging
                print(f"Inserting/updating guild: {guild.discGuild.id}, {guild.discGuild.owner.id}, {guild.isSetup}")
                
                # Values to be inserted or updated
                guildValues = (guild.discGuild.id, guild.discGuild.owner.id, guild.isSetup)
                
                # Execute the guild query
                cursor.execute(guildInsertOrUpdateQuery, guildValues)

                # Insert or update each queue for this guild
                if len(guild.GuildQueues) > 0:
                    for queue in guild.GuildQueues:  # Assuming `queues` is a list of queue objects in the guild
                        queueInsertOrUpdateQuery = """
                        INSERT INTO queues (GuildId, QueueName, QueueId, QueueType)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            QueueName = VALUES(QueueName),
                            QueueType = VALUES(QueueType)
                        """
                        # Log queue data for debugging
                        print(f"Inserting/updating queue: GuildId={guild.discGuild.id}, QueueName={queue.QueueName}, QueueId={queue.QueueID}, QueueType={queue.QueueType}")
                        
                        # Values to be inserted or updated
                        queueValues = (guild.discGuild.id, queue.QueueName, queue.QueueID, queue.QueueType)
                        
                        # Execute the queue query
                        cursor.execute(queueInsertOrUpdateQuery, queueValues)

            # Commit the transaction
            conn.commit()
            print("Transaction committed successfully.")
        else:
            print("No connection to the database.")
    except mariadb.Error as e:
        print(f"Error executing query: {e}")
        if conn:
            conn.rollback()  # Rollback the transaction on error
            print("Transaction rolled back.")
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")
    

async def getList():
    conn = getConn()

    if conn:
        cursor = conn.cursor(dictionary=True)  # Use dictionary cursor for easier row access
        guildList = []

        try:
            # Retrieve guild information
            guildStatement = "SELECT GuildId, OwnerId, IsSetup FROM Guild"
            cursor.execute(guildStatement)
            guilds = cursor.fetchall()

            # Retrieve queues and group them by GuildId
            queueStatement = "SELECT GuildId, QueueId, QueueName, QueueType FROM queues"
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
                guildList.append(guild_data)

        except Exception as e:
            print(f"Error retrieving entry from database: {e}")
        finally:
            cursor.close()
            conn.close()

        return guildList