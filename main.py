import os
import time

from lib.database import Database
from lib.bot import Bot


POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

DISCORD_PREFIX = "%"

DB_POOL_MINCONN = 1
DB_POOL_MAXCONN = 5

if __name__ == "__main__":
    bot = Bot(DISCORD_PREFIX, None)

    time.sleep(2)

    database = Database(DB_POOL_MINCONN, DB_POOL_MAXCONN, host=POSTGRES_HOST, database=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD, port=POSTGRES_PORT)
    bot.set_database(database)

    database.execute("CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY, version TEXT, link TEXT, name TEXT)")

    time.sleep(2)

    bot.run(DISCORD_TOKEN)
