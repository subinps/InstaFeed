# InstaFeed [WIP]

Get your instagram feeds and storied inside telegram

### Config Variables

- `BOT_TOKEN` Bot token from [@BotFather](https://telegram.dog/BotFather)
- `API_ID` Telegram API Key.
- `API_HASH` Telegram API Hash.
- `USERNAME` Your Instagram username.
- `FEED_CHAT_ID` Chat ID where you want to recive your instagram feeds.
- `STORY_CHAT_ID` Chat ID where you want to recive your instagram stories.

### SetUp

- Clone the repo to your local machine.
- Add your config vars to `.env` in root directory
- get your instagram session file using
- Install requirements from requirements file
- run `instaloader -l <yourInstagramUsername>` to create an instagram session.
- finally run the bot by `python3 main.py`

##TODO

- []. Add support for Non-persistent servers.
- []. Better login option.

## ⚠️ WARNING

- You cant use this on heroku! or any non-persistent server.
