import asyncio
import json
from io import BytesIO
from os import getenv

import instaloader
import requests as r
import tzlocal
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client, errors, idle, raw, types, utils

from logger import getLogger
from utils import send_media_group
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

log = getLogger(__name__)


feedChatID = int(getenv("FEED_CHAT_ID", 0))  # chat ID to send Instagram feeds
storyChatID = int(getenv("STORY_CHAT_ID", 0))  # chat ID to send Instagram stories
username = getenv("USERNAME")  # your Instagram username
session_file_id = getenv("INSTA_SESSIONFILE_ID") # get session file


RUNNING = {}

bot = Client(
    "instaFeeds", getenv("API_ID", 0), getenv("API_HASH", ""), bot_token=getenv("BOT_TOKEN", "")
)

L = instaloader.Instaloader()
await bot.download_media(session_file_id, file_name=f"./{username}")
L.load_session_from_file(username, filename=f"./{username}")

scheduler = AsyncIOScheduler(timezone=str(tzlocal.get_localzone()))


def getLastPost(file):
    with open(f"cache/{file}") as out:
        return json.load(out)


def saveLast(data, file):
    with open(f"cache/{file}", "w+") as out:
        json.dump(data, out)


lastStory = getLastPost("stories.json")
lastFeed = getLastPost("post.json")
timeStamp = getLastPost("ts.json")


def get_post(post):
    images = []
    videos = []
    if post.typename == "GraphSidecar":
        for k in post.get_sidecar_nodes():
            if k.is_video:
                videos.append({"main": k.video_url, "thumb": k.display_url})
            else:
                images.append(k.display_url)
    elif post.typename in ["GraphImage", "GraphStoryImage"]:
        images.append(post.url)

    elif post.typename in ["GraphVideo", "GraphStoryVideo"]:
        videos.append({"main": post.video_url, "thumb": post.url})
    return images, videos


async def getAlbumURL(post, caption=None):
    ALBUM = []
    if caption is None:
        caption = (
            f"[@{post.owner_username}](https://instagram.com/{post.owner_username}) | [🌐 Instagram](https://www.instagram.com/p/"
            + post.shortcode
            + ")\n\n"
            + (post.caption or "")
        )
    if caption and len(caption) > 1024:
        caption = caption[:1024] + "..."
    image, video = get_post(post)
    for i in image:
        ALBUM.append(types.InputMediaPhoto(i, caption=caption))
        caption = None  # using caption only for the first image of the group.
    for i in video:
        thumb = BytesIO()
        resp = r.get(i["thumb"])
        thumb.write(resp.content)
        thumb.name = "thu.jpg"
        ALBUM.append(types.InputMediaVideo(i["main"], caption=caption, thumb=thumb))
        caption = None
    return ALBUM


async def getAlbumBytes(post, caption=None):
    ALBUM = []
    if caption is None:
        caption = (
            f"[@{post.owner_username}](https://instagram.com/{post.owner_username}) | [🌐Instagram](https://www.instagram.com/p/"
            + post.shortcode
            + ")\n\n"
            + (post.caption or "")
        )
    if caption and len(caption) > 1024:
        caption = caption[:1024] + "..."
    image, video = get_post(post)
    for i in image:
        file = BytesIO()
        resp = r.get(i)
        file.write(resp.content)
        file.name = "img.jpg"
        ALBUM.append(types.InputMediaPhoto(file, caption=caption))
        caption = None
    for i in video:
        file = BytesIO()
        resp = r.get(i["main"])
        file.write(resp.content)
        file.name = "vid.mp4"
        thumb = BytesIO()
        resp = r.get(i["thumb"])
        thumb.write(resp.content)
        thumb.name = "thu.jpg"
        ALBUM.append(types.InputMediaVideo(file, caption=caption, thumb=thumb))
        caption = None
    return ALBUM


async def sendMedia(media, post=None, story=None, breaker=None, ownerID=None):
    # uploading media to telegram servers, without sending it anywhere
    try:
        return await send_media_group(bot, feedChatID, media=media)
    except (errors.WebpageMediaEmpty, errors.WebpageCurlFailed):
        if story:
            media = await getStoryAlbumBytes(story, breaker, ownerID)
        else:
            media = await getAlbumBytes(post)
        return await sendMedia(media, post, story, breaker, ownerID)
    except errors.FloodWait as e:
        await asyncio.sleep(e.value)
        return await sendMedia(media, post, story, breaker, ownerID)
    except Exception as e:
        log.exception(e)


async def sendMessage(chat_id, multi_media):
    try:
        return await bot.invoke(
            raw.functions.messages.SendMultiMedia(
                peer=await bot.resolve_peer(chat_id),
                multi_media=multi_media,
                silent=None,
                reply_to_msg_id=None,
                schedule_date=utils.datetime_to_timestamp(None),
                noforwards=None,
            ),
            sleep_threshold=60,
        )
    except errors.MediaEmpty:
        message = multi_media[0].message
        entities = multi_media[0].entities
        for i in multi_media:
            try:
                media = i.media
                await bot.invoke(
                    raw.functions.messages.SendMedia(
                        peer=await bot.resolve_peer(chat_id),
                        media=media,
                        silent=None,
                        message=message,
                        reply_to_msg_id=None,
                        random_id=bot.rnd_id(),
                        entities=entities,
                    )
                )
            except Exception as e:
                log.exception(e)


async def sendToChat(chatID, media):
    try:
        await sendMessage(chatID, media)
    except errors.FloodWait as e:
        await asyncio.sleep(e.value)
        return await sendToChat(chatID, media)
    except Exception as e:
        log.exception(e)


async def getStoryAlbumURL(story, lastShort, ownerID=None):
    ALBUM = []
    medias = []
    first = None
    i = None
    for i in story.get_items():
        if i.shortcode == lastShort:
            break
        else:
            medias.append(i)
        if not first:
            first = i.shortcode
    if i:
        ownerID = ownerID or str(i.owner_id)
        lastStory[ownerID] = first or i.shortcode
        saveLast(lastStory, "stories.json")
    caption = None
    for i in medias:
        if caption is None:
            caption = f"[@{i.owner_username}](https://instagram.com/{i.owner_username}) | [🌐 Story](https://www.instagram.com/{i.owner_username}/{i.mediaid})"
        else:
            caption = ""
        album = await getAlbumURL(i, caption)
        ALBUM += album
    return ALBUM


async def getStoryAlbumBytes(story, lastShort, ownerID=None):
    ALBUM = []
    medias = []
    first = None
    i = None
    for i in story.get_items():
        if i.shortcode == lastShort:
            break
        else:
            medias.append(i)
        if not first:
            first = i.shortcode
    if i:
        ownerID = ownerID or str(i.owner_id)
        lastStory[ownerID] = first or i.shortcode
        saveLast(lastStory, "stories.json")
    caption = None
    for i in medias:
        if caption is None:
            caption = f"[@{i.owner_username}](https://instagram.com/{i.owner_username}) | [🌐 Story](https://www.instagram.com/{i.owner_username}/{i.mediaid})"
        else:
            caption = ""
        album = await getAlbumBytes(i, caption)
        ALBUM += album
    return ALBUM


def splitList(l, count=10):
    return [l[i : i + count] for i in range(0, len(l), count)]


async def getStory():
    for story in L.get_stories():
        ownerID = str(story.owner_id)
        lastPosted = lastStory.get(ownerID)
        lastTimeStamp = timeStamp.get(ownerID)
        _newTimeStamp = str(story.latest_media_utc)
        if lastTimeStamp == _newTimeStamp:
            log.info(f"no story update : {story.owner_username}")
            continue
        timeStamp[ownerID] = _newTimeStamp
        saveLast(timeStamp, "ts.json")
        lastShort = ""
        if lastPosted:
            lastShort = lastPosted
        medias = splitList((await getStoryAlbumURL(story, lastShort, ownerID)))
        for media in medias:
            res = await sendMedia(media, story=story, breaker=lastShort, ownerID=ownerID)
            if res:
                await sendToChat(storyChatID, res)
                saveLast(lastStory, "stories.json")
                await asyncio.sleep(1)


async def getFeeds():
    isFirst = None
    MEDIA = []
    breaker = lastFeed.get("last")
    try:
        for post in L.get_feed_posts():
            if not isFirst:
                isFirst = post.shortcode
            if post.shortcode == breaker:
                break
            media = await getAlbumURL(post)
            res = await sendMedia(media, post)
            if res:
                MEDIA.append(res)
    except Exception as e:
        log.exception(e)
    if isFirst:
        lastFeed["last"] = isFirst
        saveLast(lastFeed, "post.json")
    MEDIA.reverse()  # reversing the list to keep the order of instagram posts
    for i in MEDIA:
        await sendToChat(feedChatID, i)
        await asyncio.sleep(1)


@scheduler.scheduled_job(
    "cron", hour="1,3,5,7,9,11,13,15,17,19", minute=00
)  # running every 2 hours
async def runFeed():
    while RUNNING.get("status"):
        await asyncio.sleep(2)
        log.info("waiting for previous run to finish!")
        continue
    RUNNING["status"] = True
    try:
        await getFeeds()
    except Exception as e:
        log.exception(e)
    RUNNING["status"] = False


@scheduler.scheduled_job("cron", minute=00, hour="2,4,6,8,10,12,14,16,18")
async def runStory():
    while RUNNING.get("status"):
        await asyncio.sleep(2)
        log.info("waiting for previous run to finish!")
        continue
    RUNNING["status"] = True
    try:
        await getStory()
    except Exception as e:
        log.exception(e)
    RUNNING["status"] = False


async def main():
    await bot.start()
    scheduler.start()
    log.info(f"{bot.me.username} started!")
    await idle()


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
