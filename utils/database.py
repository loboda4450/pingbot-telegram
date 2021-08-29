import sqlite3
from typing import List


def add_game_subscriber(_con: sqlite3.Connection, _cur: sqlite3.Cursor, _userid: int, _chatid: int, _game: str) -> None:
    """Adds a game subscriber to database"""
    _cur.execute("INSERT INTO users(userid, chatid, game) VALUES (?, ?, ?)", (
        _userid, _chatid, _game,))
    _con.commit()


def get_user_games(cur: sqlite3.Cursor, event) -> List:
    """Gets user games from database and format it friendly way"""
    return [x[0] for x in
            cur.execute("SELECT DISTINCT game FROM users WHERE userid == ?", (event.sender_id,)).fetchall()]


def get_chat_games(cur: sqlite3.Cursor, event) -> List:
    """Gets chat games from database and format it friendly way"""
    return [x[0] for x in cur.execute("SELECT DISTINCT game FROM users WHERE chatid == ?", (event.chat.id,)).fetchall()]


def get_game_users(cur: sqlite3.Cursor, event) -> List:
    """Gets game users other than event requester from database and format it friendly way"""
    return [x[0] for x in cur.execute("SELECT userid FROM users WHERE chatid == ? AND game == ? AND userid != ?",
                                      (event.chat.id, event.text.split(' ', 1)[1], event.sender.id)).fetchall()]
