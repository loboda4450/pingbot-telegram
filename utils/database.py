from sqlite3 import Connection, Cursor

import pony.orm
from telethon.events import CallbackQuery, NewMessage, InlineQuery
from typing import List, Union
from pony.orm import *

# import pony.orm as pony
db = Database("sqlite", "users-orm.sqlite", create_db=True)


class User(db.Entity):
    userid = Required(int)
    chatid = Required(int)
    game = Required(str)
    PrimaryKey(userid, chatid, game)


db.generate_mapping(create_tables=True)


@db_session
def add_subscriber(event: Union[NewMessage, CallbackQuery], game: str) -> bool:
    print("Woke up add_subscriber: {}, {}, {}".format(event.sender_id, event.chat.id, game))
    if not User.exists(userid=event.sender_id, chatid=event.chat.id, game=game):
        User(userid=event.sender_id, chatid=event.chat.id, game=game)
        return True
    else:
        return False


@db_session
def remove_subscriber(event: Union[NewMessage, CallbackQuery], game: str) -> bool:
    print("Woke up remove_subscriber: {}, {}, {}".format(event.sender_id, event.chat.id, game))
    if User.exists(userid=event.sender_id, chatid=event.chat.id, game=game):
        User.get(userid=event.sender.id, chatid=event.chat.id, game=game).delete()
        return True
    else:
        return False


# @db_session
# def get_game_subscribers(event: Union[NewMessage, CallbackQuery]):
#     return db.select(user for user in User if user.chatid == event.chat.id and
#                      user.userid != event.sender.id and
#                      user.game == event.text.split(' ', 1)[1])


@db_session
def get_user_games(event: Union[NewMessage, CallbackQuery]) -> List:
    return [user.game for user in User.select(userid=event.sender.id)]
