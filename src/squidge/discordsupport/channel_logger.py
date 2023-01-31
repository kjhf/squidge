import asyncio
import logging
from logging import StreamHandler
from typing import Optional

from discord.abc import Messageable

MESSAGE_TEXT_LIMIT = 2000


class ChannelLogHandler(StreamHandler):
    def __init__(self, channel: Messageable, logger: Optional[logging.Logger]):
        StreamHandler.__init__(self)
        if channel:
            self.log_channel = channel
            logger = logger or logging.getLogger()
            logger.setLevel(logging.INFO)
            self.setLevel(logging.INFO)
            formatter = logging.Formatter('[%(levelname)s]: %(message)s')
            self.setFormatter(formatter)
            logger.addHandler(self)

    def emit(self, record):
        msg = self.format(record)
        while len(msg) > MESSAGE_TEXT_LIMIT:
            truncated_send = msg[:MESSAGE_TEXT_LIMIT]
            asyncio.create_task(self.log_channel.send(truncated_send))
            msg = msg[MESSAGE_TEXT_LIMIT:]
        asyncio.create_task(self.log_channel.send(msg))
