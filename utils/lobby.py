import sqlite3
from sqlite3 import Connection, Cursor
from typing import List, Dict, Tuple, Union

from telethon.events import CallbackQuery
from telethon.tl.custom import Message
from utils.database import user_subscribes


def add_lobby_to_db(con: Connection, cur: Cursor, event: CallbackQuery, lobby: Message,
                    ping: Message, game: str, in_lobby: bool) -> None:
    """Adds every pinged user for lobby to database"""
    cur.execute("INSERT INTO lobbies(lobbyid, ownerid, chatid, game, participant, ping, in_lobby) "
                "VALUES (?,?,?,?,?,?,?)",
                (lobby.id, event.sender.id, event.chat.id, game, event.sender.id, ping.id, in_lobby))
    con.commit()


async def remove_lobby_from_db(con: Connection, cur: Cursor, event: CallbackQuery):
    """Removes lobby from database and connected entries"""
    lobby_msg = await event.get_message()
    cur.execute("""DELETE FROM lobbies WHERE lobbyid == ? AND chatid == ?""", (lobby_msg.id, lobby_msg.chat.id,))
    con.commit()


async def lobby_exists(cur: Cursor, event: CallbackQuery) -> bool:
    """Checks if lobby exist in database"""
    lobby_msg = await event.get_message()
    return cur.execute("""SELECT COUNT(*) FROM lobbies 
                          WHERE lobbyid == ? AND chatid == ?""",
                       (lobby_msg.id, event.chat.id,)).fetchone()[0] > 0


async def get_lobby(cur: Cursor, event: CallbackQuery) -> List[Dict]:
    """Gets all lobby from database and format it friendly way"""
    lobby_msg = await event.get_message()
    lobby = cur.execute("SELECT lobbyid, ownerid, chatid, game, participant, ping, in_lobby "
                        "FROM lobbies WHERE lobbyid == ? AND chatid == ?",
                        (lobby_msg.id, event.chat.id,)).fetchall()
    keys = [x[0] for x in cur.description]
    return [{keys[0]: user[0],
             keys[1]: user[1],
             keys[2]: user[2],
             keys[3]: user[3],
             keys[4]: user[4],
             keys[5]: user[5],
             keys[6]: user[6]} for user in lobby] if lobby else [{'error': 'lobby does not exist in database'}]


async def get_lobby_participants(cur: Cursor, event: CallbackQuery, in_lobby: bool) -> List[Dict]:
    """Gets lobby participants from database and format it friendly way"""
    lobby_msg = await event.get_message()
    lobby = cur.execute("SELECT lobbyid, ownerid, chatid, game, participant, ping, in_lobby "
                        "FROM lobbies WHERE lobbyid == ? AND chatid == ? AND in_lobby == ?",
                        (lobby_msg.id, event.chat.id, in_lobby,)).fetchall()
    keys = [x[0] for x in cur.description]
    return [{keys[0]: user[0],
             keys[1]: user[1],
             keys[2]: user[2],
             keys[3]: user[3],
             keys[4]: user[4]} for user in lobby] if lobby else [{'error': 'lobby does not exist in database'}]


async def get_lobby_game(cur: Cursor, event: CallbackQuery) -> str:
    """Returns lobby game"""
    lobby_msg = await event.get_message()
    lobby = cur.execute("SELECT game FROM lobbies WHERE lobbyid == ? AND chatid == ?",
                        (lobby_msg.id, event.chat.id,)).fetchone()

    return lobby[0]


async def get_lobby_ids(cur: Cursor, event: CallbackQuery) -> List[int]:
    """Returns lobby id"""
    lobby_msg = await event.get_message()

    return [id_[0] for id_ in cur.execute("SELECT DISTINCT ping FROM lobbies WHERE lobbyid == ? AND chatid == ?",
                                          (lobby_msg.id, event.chat.id,)).fetchall()]


async def get_lobby_ping_ids(cur: Cursor, event: CallbackQuery) -> List[int]:
    lobby_msg = await event.get_message()

    return [id_[0] for id_ in cur.execute("SELECT DISTINCT ping FROM lobbies "
                                          "WHERE lobbyid == ? AND chatid == ? AND ping != lobbyid",
                                          (lobby_msg.id, event.chat.id,)).fetchall()]


async def get_lobby_owner(cur: Cursor, event: CallbackQuery) -> int:
    """Returns lobby owner"""
    lobby_msg = await event.get_message()
    if await lobby_exists(cur=cur, event=event):
        return cur.execute("SELECT ownerid FROM lobbies WHERE lobbyid == ? AND chatid == ? AND ownerid == participant",
                           (lobby_msg.id, event.chat.id,)).fetchone()[0]
    else:
        raise Exception('Lobby does not exist!')


async def is_in_lobby(cur: sqlite3.Cursor, event: Union[CallbackQuery, int], inside=True) -> bool:
    """Checks if user is in lobby"""
    lobby = await get_lobby(cur=cur, event=event)
    id = event.sender.id if isinstance(event, CallbackQuery.Event) else event
    if inside:
        return id in [user['participant'] for user in lobby if user['in_lobby']]
    else:
        return id in [user['participant'] for user in lobby]


async def change_lobby_participants(con: Connection, cur: Cursor, event: CallbackQuery, joined: bool) -> None:
    """Changes in_lobby parameter to True/False for a specified userid and lobbyid, depends on join/leave"""
    lobby_msg = await event.get_message()
    if user_subscribes(cur=cur,
                       event=event,
                       game=await get_lobby_game(cur=cur, event=event)) or await is_in_lobby(cur=cur,
                                                                                             event=event,
                                                                                             inside=False):

        cur.execute("""UPDATE lobbies SET in_lobby = ? WHERE participant == ? AND lobbyid == ?""",
                    (joined, event.sender.id, lobby_msg.id))
    else:
        cur.execute("INSERT INTO lobbies(lobbyid, ownerid, chatid, game, participant, ping, in_lobby) "
                    "VALUES (?,?,?,?,?,?,?)", (lobby_msg.id, await get_lobby_owner(cur=cur, event=event),
                                               event.chat.id, await get_lobby_game(cur=cur, event=event),
                                               event.sender.id, 0, joined,)
                    )
    con.commit()


async def update_lobby_pings(con: Connection, cur: Cursor, event: CallbackQuery):
    ...


def is_lobby_empty(lobby: List) -> bool:
    """Checks if lobby is empty"""
    return not any((user['in_lobby'] for user in lobby))
