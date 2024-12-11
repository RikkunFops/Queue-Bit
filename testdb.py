import mariadb
import discord
import os
from discord import *
from discord.ext import commands
from dbaccess import getConn
from cogs.guild import Guild
from dotenv import load_dotenv


token = 'MTMxNTA0MDU2MDMxNDA2MDgzMg.GRkhiK.CUQoUSh4ZGjyUVujAFANOFDQNl3tbKEPkpEqX0'
intents = Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)


conn = getConn()

if conn:
    cursor = conn.cursor()
    
    guildList = []
    '''try:'''
    statement = "SELECT id, owner, isSetup FROM testdb.Guild"
    cursor.execute(statement)
    for id in cursor:
            print(type(id[0]))
            print(f"Successfully retrieved {id[0]}")
            gid = Guild(bot.get_guild(id[0]))
            print (gid.guild.id)
            '''guildList.append(gid)'''
    '''except Exception as e:
        print(f"Error retrieving entry from database: {e}")'''