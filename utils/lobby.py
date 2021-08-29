import sqlite3
from sqlite3 import Connection, Cursor
from typing import List, Dict, Tuple

# from telethon.tl.types import
from telethon.events import CallbackQuery
from telethon.client import TelegramClient
from utils.chat_aux import get_sender_name, get_chat_users
from utils.database import user_subscribes


def add_lobby_to_db(con: Connection, cur: Cursor, lobby_id: int, owner_id: int, chat_id: int, game: str,
                    participant: int, ping_id: int, in_lobby: bool) -> None:
    """Adds every pinged user for lobby to database"""
    cur.execute("INSERT INTO lobbies(lobbyid, ownerid, chatid, game, participant, ping, in_lobby) "
                "VALUES (?,?,?,?,?,?,?)", (lobby_id, owner_id, chat_id, game, participant, ping_id, in_lobby))
    con.commit()


def remove_lobby_from_db(con: Connection, cur: Cursor, lobby_id: int, chat_id: int):
    """Removes lobby from database and connected entries"""
    cur.execute("""DELETE FROM lobbies WHERE lobbyid == ? AND chatid == ?""", (lobby_id, chat_id,))
    con.commit()


def lobby_exists(cur: Cursor, lobby_id: int, chat_id: int) -> bool:
    """Checks if lobby exist in database"""
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


async def get_lobby_owner(cur: Cursor, event: CallbackQuery) -> int:
    """Returns lobby owner"""
    lobby_msg = await event.get_message()
    if lobby_exists(cur=cur, lobby_id=lobby_msg.id, chat_id=event.chat.id):
        return cur.execute("SELECT ownerid FROM lobbies WHERE lobbyid == ? AND chatid == ? AND ownerid == participant",
                           (lobby_msg.id, event.chat.id,)).fetchone()[0]
    else:
        raise Exception('Lobby does not exist!')


async def is_in_lobby(cur: sqlite3.Cursor, event: CallbackQuery, inside=True) -> bool:
    """Checks if user is in lobby"""
    lobby = await get_lobby(cur=cur, event=event)
    if inside:
        return event.sender.id in [user['participant'] for user in lobby if user['in_lobby']]
    else:
        return event.sender.id in [user['participant'] for user in lobby]


async def change_lobby_participants(con: Connection, cur: Cursor, event: CallbackQuery, joined: bool) -> bool:
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
    return True


def is_lobby_empty(lobby: List) -> bool:
    """Checks if lobby is empty"""
    return not any((user['in_lobby'] for user in lobby))


async def parse_lobby(client: TelegramClient, cur: Cursor, event: CallbackQuery) -> str:
    """Parses lobby to its final form"""
    game = await get_lobby_game(cur=cur, event=event)
    chat_users = dict(await get_chat_users(client=client, event=event, details='uid', with_sender=True))
    in_lobby = await get_lobby_participants(cur=cur, event=event, in_lobby=True)
    in_lobby = [user for user in in_lobby if user['participant'] in chat_users]
    owner = await get_lobby_owner(cur=cur, event=event)
    l_msg = ", ".join(f"[{chat_users[user['participant']]}](tg://user?id={user['participant']})" for user in in_lobby)

    return f'Owner: [{chat_users[owner]}](tg://user?id={owner})\n' \
           f'Game: {game}\n'\
           f'Lobby: {l_msg}'

