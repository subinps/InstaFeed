from logging.handlers import RotatingFileHandler
import logging
import os

if not os.path.exists("logs"):
    os.mkdir("logs")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("logs/botlogs.log", maxBytes=500000, backupCount=10),
        logging.StreamHandler(),
    ],
)


logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.INFO)


def getLogger(name: str) -> logging.Logger:
    return logging.getLogger(name)
