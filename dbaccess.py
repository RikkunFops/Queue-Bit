import os
from urllib.parse import urlparse
import mariadb
from dotenv import load_dotenv
from cogs.guild import Guild

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
            cursor = conn.cursor()

            for guild in guildList:
                # Query to insert or update
                guildInsertOrUpdateQuery = """
                INSERT INTO Guild (GuildId, OwnerId, IsSetup)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    OwnerId = VALUES(OwnerId),
                    IsSetup = VALUES(IsSetup)
                """
                # Logging for debugging
                print(f"{guild.guild.id}, {guild.guild.owner.id}, {guild.isSetup}")
                
                # Values to be inserted or updated
                guildValues = (guild.guild.id, guild.guild.owner.id, guild.isSetup)
                
                # Execute the query
                cursor.execute(guildInsertOrUpdateQuery, guildValues)

            # Commit the transaction
            conn.commit()
        else:
            print("No connection to the database.")
    except mariadb.Error as e:
        print(f"Error executing query: {e}")
    finally:
        if conn:
            conn.close()
    

async def getList():
    conn = getConn()

    if conn:
        cursor = conn.cursor(dictionary=True)  # Use dictionary cursor for easier row access
        guildList = []

        try:
            # Retrieve guild information
            statement = "SELECT GuildId, OwnerId, IsSetup FROM Guild"
            cursor.execute(statement)
            guilds = cursor.fetchall()

            for guild_data in guilds:
                # Reconstruct the base Guild object
                guildList.append(guild_data)

        except Exception as e:
            print(f"Error retrieving entry from database: {e}")
        finally:
            cursor.close()
            conn.close()

        return guildList