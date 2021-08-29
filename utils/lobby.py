import sqlite3
from typing import List, Dict


def add_lobby_to_db(con: sqlite3.Connection, cur: sqlite3.Cursor, lobby_id: int, owner_id: int, chat_id: int, game: str,
                    participant: int, ping_id: int, in_lobby: bool) -> None:
    """Adds every pinged user for lobby to database"""
    cur.execute(
        "INSERT INTO lobbies(lobbyid, ownerid, chatid, game, participant, ping, in_lobby) VALUES (?,?,?,?,?,?,?)",
        (lobby_id, owner_id, chat_id, game, participant, ping_id, in_lobby))
    con.commit()


async def get_lobby(cur: sqlite3.Cursor, event) -> List[Dict]:
    """Gets lobby from database and format it friendly way"""
    try:
        lobby_msg = await event.get_message()
        lobby = cur.execute(
            "SELECT lobbyid, ownerid, chatid, game, participant, ping, in_lobby FROM lobbies WHERE lobbyid == ? AND chatid == ?",
            (lobby_msg.id, event.chat.id,)).fetchall()
        keys = [x[0] for x in cur.description]

        return [{keys[0]: user[0],
                 keys[1]: user[1],
                 keys[2]: user[2],
                 keys[3]: user[3],
                 keys[4]: user[4],
                 keys[5]: user[5],
                 keys[6]: user[6]} for user in lobby] if lobby else [{'error': 'lobby does not exist in database'}]

    except TypeError:
        raise Exception('Wrong lobby id!')


def is_in_lobby(userid: int, lobby: List) -> bool:
    """Checks if user is in lobby"""
    return userid in [user['participant'] for user in lobby if user['in_lobby']]


def leave_lobby(con: sqlite3.Connection, cur: sqlite3.Cursor, userid: int, lobbyid: int):
    """Changes in_lobby parameter to True for a specified userid and lobbyid"""
    cur.execute("""UPDATE lobbies SET in_lobby = ? WHERE participant == ? AND lobbyid == ?""", (False, userid, lobbyid))
    con.commit()


def join_lobby(con: sqlite3.Connection, cur: sqlite3.Cursor, userid: int, lobbyid: int):
    """Changes in_lobby parameter to False for a specified userid and lobbyid"""
    cur.execute("""UPDATE lobbies SET in_lobby = ? WHERE participant == ? AND lobbyid == ?""", (True, userid, lobbyid))
    con.commit()


def change_lobby_participants(con: sqlite3.Connection, cur: sqlite3.Cursor, userid: int, lobbyid: int, joined: bool):
    """Changes in_lobby parameter to False for a specified userid and lobbyid"""
    cur.execute("""UPDATE lobbies SET in_lobby = ? WHERE participant == ? AND lobbyid == ?""", (joined, userid, lobbyid))
    con.commit()

def is_lobby_empty(lobby: str) -> bool:
    """Checks if lobby is empty
    TODO: Rework with database, will work after future code edits but also will make no sense
    """
    return len(lobby.split(':', 1)[1]) == 0


def parse_lobby(event) -> List:
    ...
