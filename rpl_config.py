import os
import tomllib

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

    set_loaded()
