from typing import Union, Tuple

from telethon.tl.types import User
from telethon.events import NewMessage

from utils.lobby import *


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


async def get_chat_users(client: TelegramClient, event: CallbackQuery, details='all', with_sender=False) -> Union[
    List, List[Tuple]]:
    """Returns chat users other than sender and bots"""
    participants = (user for user in await client.get_participants(event.chat.id) if not user.is_self and not user.bot)

    if not with_sender:
        participants = (user for user in participants if user.id != event.sender.id
                        and not user.is_self and not user.bot)

    if details == 'id':
        return [user.id for user in participants]
    elif details == 'username':
        return [get_sender_name(user) for user in participants]
    elif details == 'uid':
        return [(user.id, get_sender_name(user)) for user in participants]
    else:
        return [user for user in participants]


async def get_game(event: Union[NewMessage, CallbackQuery]) -> str:
    """Returns game from a lobby in database"""
    if isinstance(event, CallbackQuery.Event):
        if lobby_exists(lobby=await event.get_message()):
            game = get_lobby_game(lobby=await event.get_message())
        else:
            t = await event.get_message()
            t = t.raw_text
            game = t.split(" just unsubscribed '", 1)[1].rsplit("'!", 1)[0] if 'unsubscribed' in t \
                else t.split(" just subscribed to '", 1)[1].rsplit("'!", 1)[0]

    elif isinstance(event, NewMessage.Event):
        if not event.is_reply:
            game = event.text.split(" ", 1)[1]
        else:
            lobby_msg = await event.get_reply_message()
            if 'Game:' in lobby_msg.text:
                game = lobby_msg.text.split('\n')[1]
                game = game.split(':', 1)[1].strip(' ')
            else:
                raise Exception('Message does not contain game!')

    else:
        raise Exception('Wrong event type!')

    return game


async def parse_lobby(client: 'TelegramClient', event: CallbackQuery, lobby: Message) -> str:
    """Parses lobby to its final form"""
    game = get_lobby_game(lobby=lobby)
    chat_users = dict(await get_chat_users(client=client, event=event, details='uid', with_sender=True))
    in_lobby = [user for user in get_lobby_participants(lobby=lobby, in_lobby=True) if user.participant in chat_users]
    owner = get_lobby_owner(lobby=lobby).ownerid
    l_msg = ", ".join(f"[{chat_users[user.participant]}](tg://user?id={user.participant})" for user in in_lobby)
    return f'Owner: [{chat_users[owner]}](tg://user?id={owner})\n' \
           f'Game: {game}\n' \
           f'Lobby: {l_msg}'


async def parse_repings(client: 'TelegramClient', event: CallbackQuery, lobby: Message) -> List[List[str]]:
    if chat_users := dict(await get_chat_users(client=client, event=event, details='uid', with_sender=False)):
        participants = [user.participant for user in get_lobby_participants(lobby=lobby, in_lobby=False)
                        if user.participant in chat_users]

        return [[f"[{chat_users[id_]}](tg://user?id={id_})" for id_ in chunk] for chunk in
                [participants[x: x + 5] for x in range(0, len(participants), 5)]]

    else:
        raise Exception('No chat users to load!')


async def delete_previous_pings(client: 'TelegramClient', event: CallbackQuery, lobby: Message) -> None:
    await client.delete_messages(event.chat.id, get_ping_ids(lobby=lobby))
