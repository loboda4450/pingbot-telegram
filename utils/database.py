from sqlite3 import Connection, Cursor
from telethon.events import CallbackQuery, NewMessage
from typing import List, Union


def add_game_subscriber(con: Connection, cur: Cursor, event: Union[NewMessage.Event, CallbackQuery.Event], game: str) -> None:#Union[None, Exception]:
    # TODO: Idk if exceptions should be re-raised, or returned..
    """Adds a game subscriber to database"""
    try:
        cur.execute("INSERT INTO users(userid, chatid, game) VALUES (?, ?, ?)", (event.sender_id, event.chat.id, game))
        con.commit()
    except Exception as e:
        return e


def remove_game_subscriber(con: Connection, cur: Cursor, event: Union[NewMessage.Event, CallbackQuery.Event], game: str) -> None:
    cur.execute("DELETE FROM users WHERE userid == ? AND chatid == ? AND game == ?",
                (event.sender.id, event.chat.id, game,))
    con.commit()


def get_user_games(cur: Cursor, event: Union[NewMessage.Event, CallbackQuery.Event]) -> List:
    """Gets user games from database and format it friendly way"""
    return [x[0] for x in
            cur.execute("SELECT DISTINCT game FROM users WHERE userid == ?", (event.sender_id,)).fetchall()]


def get_chat_games(cur: Cursor, event: Union[NewMessage.Event, CallbackQuery.Event]) -> List:
    """Gets chat games from database and format it friendly way"""
    return [x[0] for x in cur.execute("SELECT DISTINCT game FROM users WHERE chatid == ?", (event.chat.id,)).fetchall()]


def get_game_users(cur: Cursor, event: Union[NewMessage.Event, CallbackQuery.Event]) -> List:
    """Gets game users other than event requester from database and format it friendly way"""
    return [x[0] for x in cur.execute("SELECT userid FROM users WHERE chatid == ? AND game == ? AND userid != ?",
                                      (event.chat.id, event.text.split(' ', 1)[1], event.sender.id)).fetchall()]


def user_subscribes(cur: Cursor, event: Union[NewMessage.Event, CallbackQuery.Event], game: str) -> bool:
    return cur.execute("""SELECT COUNT(*) FROM users WHERE userid == ? AND chatid == ? AND game == ?""",
                       (event.sender.id, event.chat.id, game,)).fetchone()[0] > 0
