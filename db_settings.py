import os

import rpl_config

rpl_config.load()

TORTOISE_ORM = {
    "connections": {"default": os.environ["DB_URL"]},
    "apps": {
        "models": {
            "models": ["common.models", "aerich.models"],
        }
    },
}
