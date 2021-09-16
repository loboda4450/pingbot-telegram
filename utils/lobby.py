from datetime import datetime
from typing import List

from telethon.events import CallbackQuery
from telethon.tl.custom import Message
from pony.orm import *
from utils.logme import logme

db = Database("sqlite", "users-orm.sqlite", create_db=True)


class Lobby(db.Entity):
    id = PrimaryKey(int, auto=True)
    lobbyid = Required(int)
    ownerid = Required(int)
    chatid = Required(int)
    game = Required(str)
    participant = Required(int)
    ping = Optional(int)
    in_lobby = Required(bool)
    created = Required(datetime)


db.generate_mapping(create_tables=True)


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
