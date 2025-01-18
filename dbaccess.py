import os
import mysql.connector
from dotenv import load_dotenv
import settings

standard_logger = settings.logging.getLogger("discord")
error_logger = settings.logging.getLogger("bot")

loaded_guilds = {}
loaded_users = {}

def get_conn():
    """Get a connection to the database."""
    load_dotenv()
    if os.getenv('DB_USER'):
        user = os.getenv('DB_USER')
        password = os.getenv('DB_PASS')
        host = os.getenv('DB_HOST')
        port = os.getenv('DB_PORT')
        schema = os.getenv('DB_SCHEMA')
        try:
            conn = mysql.connector.connect(
                user=user,
                password=password,
                host=host,
                port=port,
                database=schema
            )
            standard_logger.info("Connection successful!")
            return conn
        except mysql.connector.Error as e:
            error_logger.error("Error connecting to the database: %s", e)
    else:
        error_logger.error("DATABASE_URL is not set in the environment.")
    return None

def delete_queue(guild_id, queue_id):
    """Delete a queue from the database."""
    if not guild_id:
        error_logger.error("Invalid input: guild_id or queue_id is missing.")
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cursor:
                delete_query = "DELETE FROM queues WHERE GuildId=%s AND QueueId=%s"
                cursor.execute(delete_query, (guild_id, queue_id))
                conn.commit()
                if cursor.rowcount == 0:
                    error_logger.warning("No rows deleted. GuildId: %s, QueueId: %s", guild_id, queue_id)
                else:
                    standard_logger.info("Queue deleted successfully.")
    except mysql.connector.Error as e:
        error_logger.error("Database error: %s", e)
        raise
    except Exception as e:
        error_logger.error("Unexpected error: %s", e)
        raise

def save_program(guild_dict):
    """Save program data to the database."""
    conn = get_conn()
    try:
        if conn:
            standard_logger.info("Saving data to the database...")
            cursor = conn.cursor()

            for guild_id, guild in guild_dict.items():
                guild_insert_or_update_query = """
                INSERT INTO Guild (GuildId, OwnerId)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE
                    OwnerId = VALUES(OwnerId)
                """
                error_logger.info("Inserting/updating guild: %s, %s", guild_id, guild.disc_guild.owner.id)
                guild_values = (guild_id, guild.disc_guild.owner.id)
                cursor.execute(guild_insert_or_update_query, guild_values)

                if len(guild.guild_queues) > 0:
                    for queue in guild.guild_queues:
                        queue_insert_or_update_query = """
                        INSERT INTO queues (GuildId, QueueName, QueueId, QueueType, QueueMin, QueueMax, IsGlobal, GlobalID)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            QueueName = VALUES(QueueName),
                            QueueType = VALUES(QueueType),
                            QueueMin = VALUES(QueueMin),
                            QueueMax = VALUES(QueueMax),
                            IsGlobal = VALUES(IsGlobal),
                            GlobalID = VALUES(GlobalID)
                        """
                        error_logger.info(
                            "Inserting/updating queue: GuildId=%s, QueueName=%s, QueueId=%s, QueueType=%s, QueueMax=%s, QueueMin=%s, IsGlobal=%s, GlobalID=%s",
                            guild.disc_guild.id, queue.queue_name, queue.queue_index, queue.queue_type, queue.max_size, queue.min_size, queue.is_global, queue.global_id
                        )
                        queue_values = (
                            guild.disc_guild.id, queue.queue_name, queue.queue_index, queue.queue_type, queue.min_size, queue.max_size, queue.is_global, queue.global_id
                        )
                        cursor.execute(queue_insert_or_update_query, queue_values)

            conn.commit()
            error_logger.info("Transaction committed successfully.")
        else:
            error_logger.error("No connection to the database.")
    except mysql.connector.Error as e:
        error_logger.error("Error executing query: %s", e)
        if conn:
            conn.rollback()
            error_logger.error("Transaction rolled back.")
    finally:
        if conn:
            conn.close()
            error_logger.warning("Database connection closed.")

def end_program(guild_dict):
    """End the program and save data to the database."""
    save_program(guild_dict)

async def get_list():
    """Get a list of guilds and their queues from the database."""
    conn = get_conn()

    if conn:
        cursor = conn.cursor(dictionary=True)
        guild_dict = {}

        try:
            guild_statement = "SELECT GuildId, OwnerId FROM Guild"
            cursor.execute(guild_statement)
            guilds = cursor.fetchall()

            queue_statement = "SELECT GuildId, QueueId, QueueName, QueueType, QueueMin, QueueMax, IsGlobal, GlobalID FROM queues"
            cursor.execute(queue_statement)
            queues = cursor.fetchall()

            queue_map = {}
            for queue in queues:
                guild_id = queue['GuildId']
                if guild_id not in queue_map:
                    queue_map[guild_id] = []
                queue_map[guild_id].append(queue)

            for guild_data in guilds:
                guild_id = guild_data['GuildId']
                guild_data['queues'] = queue_map.get(guild_id, [])
                guild_dict[guild_id] = guild_data

        except mysql.connector.Error as e:
            error_logger.error("Error retrieving entry from database: %s", e)
        finally:
            cursor.close()
            conn.close()

        return guild_dict
