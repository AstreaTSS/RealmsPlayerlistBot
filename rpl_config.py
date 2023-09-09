import os
import tomllib
from pathlib import Path

IS_LOADED = False


def is_loaded() -> bool:
    return IS_LOADED


def set_loaded() -> None:
    global IS_LOADED
    IS_LOADED = True


def load() -> None:
    if is_loaded():
        return

    # load the config file into environment variables
    # this allows an easy way to access these variables from any file
    # we allow the user to set a configuration location via an already-set
    # env var if they wish, but it'll default to config.toml in the running
    # directory
    CONFIG_LOCATION = os.environ.get("CONFIG_LOCATION", "config.toml")
    with open(CONFIG_LOCATION, "rb") as f:
        toml_dict = tomllib.load(f)
        for key, value in toml_dict.items():
            os.environ[key] = str(value)

    os.environ["DATABASE_URL"] = os.environ["DB_URL"]

    file_location = Path(__file__).parent.absolute().as_posix()
    os.environ["DIRECTORY_OF_BOT"] = file_location
    os.environ["LOG_FILE_PATH"] = f"{file_location}/discord.log"
    os.environ["XAPI_TOKENS_LOCATION"] = f"{file_location}/tokens.json"

    set_loaded()
