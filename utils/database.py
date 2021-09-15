from telethon.events import CallbackQuery, NewMessage, InlineQuery
from typing import List, Union
from pony.orm import *
from utils.lobby import logme

# import pony.orm as pony
db = Database("sqlite", "users-orm.sqlite", create_db=True)


class User(db.Entity):
    id = PrimaryKey(int, auto=True)
    userid = Required(int)
    chatid = Required(int)
    game = Required(str)
    composite_key(userid, chatid, game)


db.generate_mapping(create_tables=True)


@db_session
@logme
def add_subscriber(event: Union[NewMessage, CallbackQuery], game: str) -> bool:
    if not User.exists(userid=event.sender_id, chatid=event.chat.id, game=game):
        User(userid=event.sender_id, chatid=event.chat.id, game=game)
        return True
    else:
        return False


@db_session
@logme
def remove_subscriber(event: Union[NewMessage, CallbackQuery], game: str) -> bool:
    if User.exists(userid=event.sender_id, chatid=event.chat.id, game=game):
        User.get(userid=event.sender.id, chatid=event.chat.id, game=game).delete()
        return True
    else:
        return False


@db_session
@logme
def get_game_subscribers(event: Union[NewMessage, CallbackQuery]) -> List:
    return list(select(user.userid for user in User if user.chatid == event.chat.id and
                       user.userid != event.sender.id and
                       user.game == event.text.split(' ', 1)[1]))


@db_session
@logme
def get_user_games(event: Union[NewMessage, CallbackQuery]) -> List:
    return [user.game for user in User.select(userid=event.sender.id)]
