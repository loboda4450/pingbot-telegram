from sqlite3 import Connection, Cursor
from telethon.events import NewMessage
from typing import List


def add_game_subscriber(con: Connection, cur: Cursor, userid: int, chatid: int, game: str) -> None:
    """Adds a game subscriber to database"""
    cur.execute("INSERT INTO users(userid, chatid, game) VALUES (?, ?, ?)", (userid, chatid, game,))
    con.commit()


def remove_game_subscriber(con: Connection, cur: Cursor, userid: int, chatid: int, game: str) -> None:
    cur.execute("DELETE FROM users WHERE userid == ? AND chatid == ? AND game == ?", (userid, chatid, game,))
    con.commit()


def get_user_games(cur: Cursor, event: NewMessage) -> List:
    """Gets user games from database and format it friendly way"""
    return [x[0] for x in
            cur.execute("SELECT DISTINCT game FROM users WHERE userid == ?", (event.sender_id,)).fetchall()]


def get_chat_games(cur: Cursor, event: NewMessage) -> List:
    """Gets chat games from database and format it friendly way"""
    return [x[0] for x in cur.execute("SELECT DISTINCT game FROM users WHERE chatid == ?", (event.chat.id,)).fetchall()]


def get_game_users(cur: Cursor, event: NewMessage) -> List:
    """Gets game users other than event requester from database and format it friendly way"""
    return [x[0] for x in cur.execute("SELECT userid FROM users WHERE chatid == ? AND game == ? AND userid != ?",
                                      (event.chat.id, event.text.split(' ', 1)[1], event.sender.id)).fetchall()]
