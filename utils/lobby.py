from sqlite3 import Connection, Cursor
from typing import List, Dict, Tuple

from telethon.tl.types import *
from telethon.events import CallbackQuery

from utils.chat_aux import get_sender_name


def add_lobby_to_db(con: Connection, cur: Cursor, lobby_id: int, owner_id: int, chat_id: int, game: str,
                    participant: int, ping_id: int, in_lobby: bool) -> None:
    """Adds every pinged user for lobby to database"""
    cur.execute("INSERT INTO lobbies(lobbyid, ownerid, chatid, game, participant, ping, in_lobby) "
                "VALUES (?,?,?,?,?,?,?)", (lobby_id, owner_id, chat_id, game, participant, ping_id, in_lobby))
    con.commit()


def remove_lobby_from_db(con: Connection, cur: Cursor, lobby_id: int, chat_id: int):
    cur.execute("""DELETE FROM lobbies WHERE lobbyid == ? AND chatid == ?""", (lobby_id, chat_id,))
    con.commit()


def lobby_exists(cur: Cursor, lobby_id: int, chat_id: int) -> bool:
    return cur.execute("""SELECT COUNT(*) FROM lobbies 
                          WHERE lobbyid == ? AND chatid == ?""",
                       (lobby_id, chat_id,)).fetchone()[0] > 0


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
    """Gets only in lobby participants from database and format it friendly way"""
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


def get_lobby_game(cur: Cursor, event: CallbackQuery) -> str:
    # TODO: Code it
    ...


async def get_lobby_ids(cur: Cursor, event: CallbackQuery) -> List[int]:
    lobby_msg = await event.get_message()

    return [id[0] for id in cur.execute("SELECT DISTINCT ping FROM lobbies WHERE lobbyid == ? AND chatid == ?",
                                        (lobby_msg.id, event.chat.id,)).fetchall()]


async def get_lobby_owner(cur: Cursor, event: CallbackQuery) -> int:
    lobby_msg = await event.get_message()
    if lobby_exists(cur=cur, lobby_id=lobby_msg.id, chat_id=event.chat.id):
        return cur.execute("SELECT ownerid FROM lobbies WHERE lobbyid == ? AND chatid == ? AND ownerid == participant",
                           (lobby_msg.id, event.chat.id,)).fetchone()[0]
    else:
        raise Exception('Lobby does not exist!')


def is_in_lobby(userid: int, lobby: List) -> bool:
    """Checks if user is in lobby"""
    return userid in [user['participant'] for user in lobby if user['in_lobby']]


def change_lobby_participants(con: Connection, cur: Cursor, userid: int, lobbyid: int, joined: bool):
    """Changes in_lobby parameter to True/False for a specified userid and lobbyid, depends on join/leave"""
    cur.execute("""UPDATE lobbies SET in_lobby = ? WHERE participant == ? AND lobbyid == ?""",
                (joined, userid, lobbyid))
    con.commit()


def is_lobby_empty(lobby: List) -> bool:
    """Checks if lobby is empty"""
    return not any((user['in_lobby'] for user in lobby))


async def parse_lobby(cur: Cursor, event: CallbackQuery) -> str:
    lobby_msg = await event.get_message()
    lobby_id = lobby_msg.id
    lobby = await get_lobby(cur=cur, event=event)

    ...
    return str()
