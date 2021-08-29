from re import sub
from typing import List, Generator

from telethon.tl.types import User
from telethon.client import TelegramClient

HELP1 = 'Commands:\n' \
        '/subscribe <game>: Get notified about newly created lobbies\n' \
        '/enroll: reply to existing lobby to subscribe game\n' \
        '/join: reply to a existing lobby to join it\n' \
        '/ping: Type it in inline mode to get list of your games and to create a lobby\n' \
        '/announce <game>: Manually create a lobby'


def escape_markdown(text: str) -> str:
    """Escape markdown to prevent markdown injection XDD"""
    parse = sub(r"([_*\[\]()~`>\#\+\-=|\.!])", r"\\\1", text)
    reparse = sub(r"\\\\([_*\[\]()~`>\#\+\-=|\.!])", r"\1", parse)
    return reparse


def get_sender_name(sender: User) -> str:  # fuck @divadsn
    """Returns the sender's username or full name if there is no username"""
    if sender.username:
        return "" + sender.username
    elif sender.first_name and sender.last_name:
        return "{} {}".format(sender.first_name, sender.last_name)
    elif sender.first_name:
        return sender.first_name
    elif sender.last_name:
        return sender.last_name
    else:
        return "PersonWithNoName"


async def get_chat_users(client: TelegramClient, event, details='all', with_sender=False) -> Generator:
    """Returns chat users other than sender and bots"""
    participants = await client.get_participants(event.chat.id)

    if details == 'id':
        v = (user.id for user in participants if not user.is_self and not user.bot)
    elif details == 'username':
        v = (get_sender_name(user) for user in participants if
             not user.is_self and not user.bot)
    elif details == 'uid':
        v = ((user.id, get_sender_name(user)) for user in participants if
             not user.is_self and not user.bot)
    else:
        return (user for user in participants if not user.is_self and not user.bot)

    if not with_sender:
        return (user for user in v if user.id == event.sender.id)
    else:
        return v


def get_subscribe_message():
    # TODO: Code it.
    print('Calm down, will code it soon..')
    ...


def set_ping_messages():
    # TODO: Code it.
    print('Calm down, will code it soon..')
    ...
