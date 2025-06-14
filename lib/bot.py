import logging
import time
import discord
from discord.ext import commands, tasks
import aiohttp
import ijson
import re
import json
import io
from difflib import unified_diff
import gc


class Bot(commands.Bot):
    def __init__(self, prefix, database):
        super().__init__(prefix, intents=discord.Intents.all())
        self.database = database
        self.channel_main = 1069667390402592788
        self.channel_secondary = 1070755471679570021
        self.server = 481447341849706496
        self.files = []

        @self.event
        async def on_ready():
            logging.error(f"### Bot running ###")
            self.files = self.database.fetchall("SELECT * FROM files")
            self.files = [list(file) for file in self.files]
            self.main_loop.start()

        @self.command(name="versions")
        async def get_versions(ctx):
            if ctx.channel.id == self.channel_main or ctx.guild.id != self.server:
                lines = []
                self.files = self.database.fetchall("SELECT * FROM files")
                self.files = [list(file) for file in self.files]
                for file in self.files:
                    version = await get_file_version(file[0])
                    lines.append(f"Version actuelle {file[3]} : [{version}](<{file[2].format(version=version)}>)")
                await ctx.send("\n".join(lines))

    def set_database(self, database):
        self.database = database

    @tasks.loop(seconds=300)
    async def main_loop(self):
        if not self.send_versions_notifications.is_running():
            self.send_versions_notifications.start()


    @tasks.loop(seconds=60)
    async def send_versions_notifications(self):
        now = int(time.time())
        for file in self.files:
            old_version = file[1]
            new_version = await get_file_version(file[0])
            if new_version != old_version:
                if file[0].startswith("text"):
                    old_file = await get_json_file(file[2].format(version=old_version))
                    old_lines = json.dumps(old_file, indent=4, ensure_ascii=False).split('\n')
                    new_file = await get_json_file(file[2].format(version=new_version))
                    new_lines = json.dumps(new_file, indent=4, ensure_ascii=False).split('\n')
                    lines_diff = '\n'.join([*unified_diff(old_lines, new_lines, n=0)])
                elif file[0].startswith("dll"):
                    old_file = await get_text_file(file[2].format(version=old_version))
                    old_lines = old_file.split("ItemVersions.prototype.fill=function(){", 1)[1].split("}", 1)[0].replace(';', ',').split(',')
                    new_file = await get_text_file(file[2].format(version=new_version))
                    new_lines = new_file.split("ItemVersions.prototype.fill=function(){", 1)[1].split("}", 1)[0].replace(';', ',').split(',')
                    lines_diff = '\n'.join([*unified_diff(old_lines, new_lines, n=0)])
                    server = 'default' if file[0] == 'dll' else 'openBeta'
                    lines_diff = re.sub(r"this\.assets\.([^=]*)=\"(.*)\"", lambda x: f"    {x.group(1)} = https://empire-html5.goodgamestudios.com/{server}/assets/{x.group(2)}.webp", lines_diff)
                    for line in lines_diff.split('\n'):
                        if line.startswith('+    ') or line.startswith('-    '):
                            action = "ajoutée" if line.startswith("+") else "supprimée"
                            name = line.split("    ", 1)[1].split(" = ", 1)[0]
                            url = line.split(" = ", 1)[1]
                            message = f"Image {action} à <t:{now}:T> le <t:{now}:D> dans la version {new_version} {file[3]} :\n[{name}](<{url}>)"
                            image = await get_raw_file(url)
                            await self.get_channel(self.channel_secondary).send(message, file=discord.File(io.BytesIO(image), filename=url.split("/")[-1]))
                elif file[0].startswith("item"):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(file[2].format(version=old_version)) as old_file, session.get(file[2].format(version=new_version)) as new_file:
                            old_items = ijson.kvitems(old_file.content, '')
                            new_items = ijson.kvitems(new_file.content, '')
                            old_key, old_value = await anext(old_items, [None, None])
                            new_key, new_value = await anext(new_items, [None, None])
                            lines_diff = []
                            while new_key is not None:
                                if old_key == new_key:
                                    old_lines = json.dumps(old_value, indent=4, ensure_ascii=False).split('\n')
                                    old_key, old_value = await anext(old_items, [None, None])
                                else:
                                    old_lines = ""
                                new_lines = json.dumps(new_value, indent=4, ensure_ascii=False).split('\n')
                                keylines_diff = '\n'.join([*unified_diff(old_lines, new_lines, n=0)])
                                if keylines_diff != "":
                                    lines_diff.append(f"-------------------- {new_key} --------------------\n{keylines_diff}")
                                new_key, new_value = await anext(new_items, [None, None])
                    lines_diff = '\n\n\n'.join(lines_diff)
                else:
                    logging.error(f"Unknown file type {file[0]}")
                    continue

                await self.get_channel(self.channel_main).send(
                    f"La version {file[3]} a changé à <t:{now}:T> le <t:{now}:D> !\n"
                    f"L'ancienne version était : [{old_version}](<{file[2].format(version=old_version)}>)\n"
                    f"La nouvelle version est : [{new_version}](<{file[2].format(version=new_version)}>)",
                    file=discord.File(io.BytesIO(bytes(lines_diff, 'utf-8')), filename="changes.txt"))
                self.database.execute(f"UPDATE files SET version = '{new_version}' WHERE id = '{file[0]}'")
                file[1] = new_version
                gc.collect()


async def get_file_version(file):
    async with aiohttp.ClientSession() as session:
        if file == "item":
            async with session.get("https://empire-html5.goodgamestudios.com/default/items/ItemsVersion.properties") as response:
                return (await response.text()).split("=")[1]
        elif file == "item_test":
            async with session.get("https://empire-html5.goodgamestudios.com/openBeta/items/ItemsVersion.properties") as response:
                return (await response.text()).split("=")[1]
        elif file == "text":
            async with session.get("https://langserv.public.ggs-ep.com/12/fr/@metadata") as response:
                return str((await response.json())["@metadata"]["versionNo"])
        elif file == "text_dev":
            async with session.get("https://langserv-dev.public.ggs-ep.com/12/fr/@metadata") as response:
                return str((await response.json())["@metadata"]["versionNo"])
        elif file == "text_api":
            async with session.get("https://translations-api-live.public.ggs-ep.com/12/fr/versionNo") as response:
                return str((await response.json())["versionNo"])
        elif file == "text_api_test":
            async with session.get("https://translations-api-test.public.ggs-ep.com/12/fr/versionNo") as response:
                return str((await response.json())["versionNo"])
        elif file == "dll":
            async with session.get("https://empire-html5.goodgamestudios.com/default/index.html") as response:
                return re.findall("(?<=dll/ggs[.]dll[.]).*?(?=[.]js)", await response.text())[0]
        elif file == "dll_test":
            async with session.get("https://empire-html5.goodgamestudios.com/openBeta/index.html") as response:
                return re.findall("(?<=dll/ggs[.]dll[.]).*?(?=[.]js)", await response.text())[0]

async def get_json_file(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

async def get_text_file(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

async def get_raw_file(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.read()