"""
Copyright 2020-2025 AstreaTSS.
This file is part of the Realms Playerlist Bot.

The Realms Playerlist Bot is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

The Realms Playerlist Bot is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with the Realms
Playerlist Bot. If not, see <https://www.gnu.org/licenses/>.
"""

import os
import tomllib
from pathlib import Path

import orjson
from dotenv import load_dotenv

IS_LOADED = False


def is_loaded() -> bool:
    return IS_LOADED


def set_loaded() -> None:
    global IS_LOADED
    IS_LOADED = True


def load() -> None:
    if is_loaded():
        return

    load_dotenv()

    # load the config file into environment variables
    # this allows an easy way to access these variables from any file
    # we allow the user to set a configuration location via an already-set
    # env var if they wish, but it'll default to config.toml in the running
    # directory
    CONFIG_LOCATION = os.environ.get("CONFIG_LOCATION", "config.toml")
    with open(CONFIG_LOCATION, "rb") as f:
        toml_dict = tomllib.load(f)
        for key, value in toml_dict.items():
            if key == "DEBUG":
                os.environ[key] = orjson.dumps(value).decode()
            else:
                os.environ[key] = str(value)

    if os.environ.get("DOCKER_MODE", "False") == "True":
        os.environ["DB_URL"] = (
            f"postgres://postgres:{os.environ['POSTGRES_PASSWORD']}@db:5432/postgres"
        )
        os.environ["VALKEY_URL"] = "redis://redis:6379?protocol=3"

    if not os.environ.get("VALKEY_URL") and os.environ.get("REDIS_URL"):
        os.environ["VALKEY_URL"] = os.environ["REDIS_URL"]

    file_location = Path(__file__).parent.absolute().as_posix()
    os.environ["DIRECTORY_OF_BOT"] = file_location
    os.environ["LOG_FILE_PATH"] = f"{file_location}/discord.log"
    os.environ["XAPI_TOKENS_LOCATION"] = f"{file_location}/tokens.json"

    set_loaded()
