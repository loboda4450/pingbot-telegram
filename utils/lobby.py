import asyncio
from datetime import datetime, timedelta
from typing import List

from telethon.events import CallbackQuery
from telethon.tl.custom import Message
from telethon.client import TelegramClient
from pony.orm import *
from utils.logme import logme

db = Database("sqlite", "users-orm.sqlite", create_db=True)


class Lobby(db.Entity):
    id = PrimaryKey(int, auto=True)
    lobbyid = Required(int)
    ownerid = Required(int, size=64)
    chatid = Required(int)
    game = Required(str)
    participant = Required(int, size=64)
    ping = Optional(int)
    in_lobby = Required(bool)
    created = Required(datetime)


db.generate_mapping(create_tables=True)


@db_session
@logme
def is_lobby_alive():
    return Lobby.exists()


@db_session
@logme
def add_lobby(event: CallbackQuery, lobby: Message, participant: int,
              ping: Message, game: str, in_lobby: bool) -> bool:
    if not Lobby.exists(lobbyid=lobby.id, ownerid=event.sender.id, chatid=event.chat.id,
                        game=game, participant=event.sender.id, ping=ping.id, in_lobby=in_lobby):
        Lobby(lobbyid=lobby.id,
              ownerid=event.sender.id,
              chatid=event.chat.id,
              game=game,
              participant=participant,
              ping=ping.id,
              in_lobby=in_lobby,
              created=datetime.now())
        return True
    else:
        return False


@db_session
@logme
def remove_lobby(lobby: Message) -> None:
    select(l for l in Lobby if l.lobbyid == lobby.id and l.chatid == lobby.chat.id).delete()


@db_session
@logme
def modify_participant(lobby: Message, participant: int, in_lobby: bool) -> bool:
    db_participant = Lobby.get(lobbyid=lobby.id, chatid=lobby.chat.id, participant=participant)
    if db_participant:
        if db_participant.in_lobby != in_lobby:
            db_participant.in_lobby = in_lobby
            db_participant.created = datetime.now()
            commit()
            return True
        else:
            return False
    else:
        owner = get_lobby_owner(lobby=lobby)
        Lobby(lobbyid=owner.lobbyid,
              ownerid=owner.ownerid,
              chatid=owner.chatid,
              game=owner.game,
              participant=participant,
              ping=None,
              in_lobby=in_lobby,
              created=datetime.now())

        return True


@db_session
@logme
def is_lobby_empty(lobby: Message) -> bool:
    return not bool(count(l for l in Lobby if l.lobbyid == lobby.id and l.chatid == lobby.chat.id and l.in_lobby))


@db_session
@logme
def get_lobby_game(lobby: Message) -> list:
    return select(l.game for l in Lobby if l.lobbyid == lobby.id and
                  l.chatid == lobby.chat.id and
                  l.ownerid == l.participant).limit(1)[0]


@db_session
@logme
def get_lobby_participants(lobby: Message, in_lobby: bool):
    return list(Lobby.select(lobbyid=lobby.id, chatid=lobby.chat.id, in_lobby=in_lobby))


@db_session
@logme
def get_lobby_owner(lobby: Message) -> Lobby:
    return Lobby.get(lambda x: x.ownerid == x.participant and x.lobbyid == lobby.id)


@db_session
@logme
def lobby_exists(lobby: Message) -> bool:
    return Lobby.exists(lobbyid=lobby.id, chatid=lobby.chat.id)


@db_session
@logme
def get_lobby_msg_ids(lobby: Message) -> List[int]:
    return [msg.ping for msg in Lobby.select(lobbyid=lobby.id, chatid=lobby.chat.id).distinct()]


@db_session
@logme
async def penis(client: TelegramClient, query: CallbackQuery = None, hours=6):
    to_delete = []
    x = select(l for l in Lobby if l.created < (datetime.now() - timedelta(hours=hours)) and
               l.ownerid == l.participant and
               l.chatid == query.chat.id)
    for l in x:
        y = select(a for a in Lobby if a.lobbyid == l.lobbyid).distinct()
        for a in y:
            to_delete.append(a.ping)

        y.delete()

    await client.delete_messages(query.chat.id, to_delete)
    commit()


@db_session
@logme
async def cleanup_outdated_lobbies(client: TelegramClient, query: CallbackQuery = None, hours=6):
    while True:
        await asyncio.sleep(hours * 60 * 60)
        await penis(client=client, query=query, hours=hours)


@db_session
@logme
def update_pings(lobby: Message, repings: List, newping: Message):
    ids = (reping.split('=')[1].replace(')', '') for reping in repings)  # extract id from list again... cancer, ik
    for id_ in ids:
        Lobby.get(lobbyid=lobby.id, chatid=lobby.chat.id, participant=id_).ping = newping.id

    commit()


@db_session
@logme
def get_ping_ids(lobby: Message):
    return [x.ping for x in select(
        l for l in Lobby if l.lobbyid != l.ping and l.chatid == lobby.chat.id and l.lobbyid == lobby.id).distinct()]
