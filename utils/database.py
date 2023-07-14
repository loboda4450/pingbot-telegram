from typing import List, Union
from pony.orm import *
from telethon.events import CallbackQuery, NewMessage

from utils.lobby import logme

db = Database("sqlite", "users-orm.sqlite", create_db=True)


class User(db.Entity):
    id = PrimaryKey(int, auto=True)
    userid = Required(int, size=64)
    chatid = Required(int)
    game = Required(str)
    composite_key(userid, chatid, game)


db.generate_mapping(create_tables=True)


@db_session
@logme
def is_user_alive():
    return User.exists()


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
                       user.game == ' '.join(event.text.split(' ', 1)[1].split())))


@db_session
@logme
def get_user_games(event: Union[NewMessage, CallbackQuery]) -> List:
    return list(select(user.game for user in User if user.userid == event.sender.id).distinct())


@db_session
@logme
def get_games() -> List:
    return list(select(user.game for user in User).distinct())


# @db_session
# @logme
# def get_chat_games(event: Union[
#     NewMessage, CallbackQuery, None]) -> List:  # if event passed nothing happens, cuz we cant get chatid from callbackquery :<
#     return list(select(user.game for user in User).distinct())
