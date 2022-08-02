import os
import dotenv
import logging


def main():
    dotenv.load_dotenv()
    if not os.getenv("DISCORD_BOT_TOKEN", None):
        assert False, "DISCORD_BOT_TOKEN is not defined, please check the .env file is present and correct."

    # Import must be after the env loading
    from src.squidge.entry.SquidgeBot import SquidgeBot

    logging.basicConfig(level=logging.INFO)
    squidge = SquidgeBot()
    squidge.do_the_thing()
    logging.info("Main exited!")


if __name__ == '__main__':
    main()
