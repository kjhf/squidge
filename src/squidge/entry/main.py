import os
import sys

import dotenv
import logging


def main():
    dotenv_path = dotenv.find_dotenv()
    if not dotenv_path:
        assert False, ".env file not found. Please check the .env file is present in the root folder."
    sys.path.insert(0, os.path.dirname(dotenv_path))

    dotenv.load_dotenv(dotenv_path)
    if not os.getenv("DISCORD_BOT_TOKEN", None):
        assert False, "DISCORD_BOT_TOKEN is not defined, please check the .env file is present and correct."

    # Import must be after the env loading
    print(sys.path)
    from src.squidge.entry.SquidgeBot import SquidgeBot

    logging.basicConfig(level=logging.INFO)
    squidge = SquidgeBot()
    squidge.do_the_thing()
    logging.info("Main exited!")


if __name__ == '__main__':
    main()
