import asyncio
import logging
import sqlite3
import re
from typing import List, Dict
from json import dumps

import telethon.client
from telethon import TelegramClient, events, Button
import yaml
from telethon.tl.types import User
from utils.lobby import add_lobby_to_db, get_lobby, is_in_lobby, change_lobby_participants, is_lobby_empty, \
    remove_lobby_from_db

HELP1 = 'Commands:\n' \
        '/subscribe <game>: Get notified about newly created lobbies\n' \
        '/enroll: reply to existing lobby to subscribe game\n' \
        '/join: reply to a existing lobby to join it\n' \
        '/ping: Type it in inline mode to get list of your games and to create a lobby\n' \
        '/announce <game>: Manually create a lobby'


def escape_markdown(text: str) -> str:
    """Escape markdown to prevent markdown injection XDD"""
    parse = re.sub(r"([_*\[\]()~`>\#\+\-=|\.!])", r"\\\1", text)
    reparse = re.sub(r"\\\\([_*\[\]()~`>\#\+\-=|\.!])", r"\1", parse)
    return reparse


def get_sender_name(sender: User) -> str:  # fuck @divadsn
    """Returns the sender's username or full name if there is no username"""
    if sender.username:
        return "" + sender.username
    elif sender.first_name and sender.last_name:
        return "{} {}".format(sender.first_name, sender.last_name)
    elif sender.first_name:
        return sender.first_name
    elif sender.last_name:
        return sender.last_name
    else:
        return "PersonWithNoName"


def subscribe_db(_con: sqlite3.Connection, _cur: sqlite3.Cursor, _userid: int, _chatid: int, _game: str) -> None:
    """Adds a game subscriber to database"""
    _cur.execute("INSERT INTO users(userid, chatid, game) VALUES (?, ?, ?)", (
        _userid, _chatid, _game,))
    _con.commit()


def get_user_games(cur: sqlite3.Cursor, event) -> List:
    """Gets user games from database and format it friendly way"""
    return [x[0] for x in
            cur.execute("SELECT DISTINCT game FROM users WHERE userid == ?", (event.sender_id,)).fetchall()]


def chat_games(cur: sqlite3.Cursor, event) -> List:
    """Gets chat games from database and format it friendly way"""
    return [x[0] for x in cur.execute("SELECT DISTINCT game FROM users WHERE chatid == ?", (event.chat.id,)).fetchall()]


def get_game_users(cur: sqlite3.Cursor, event) -> List:
    """Gets game users other than event requester from database and format it friendly way"""
    return [x[0] for x in cur.execute("SELECT userid FROM users WHERE chatid == ? AND game == ? AND userid != ?",
                                      (event.chat.id, event.text.split(' ', 1)[1], event.sender.id)).fetchall()]


async def get_chat_users(client: telethon.client.TelegramClient, event, details='all') -> List:
    """Returns chat users other than sender and bots"""
    participants = await client.get_participants(event.chat.id)
    if details == 'all':
        return [user for user in participants if not user.is_self and not user.bot and user.id != event.sender.id]
    elif details == 'id':
        return [user.id for user in participants if not user.is_self and not user.bot and user.id != event.sender.id]
    elif details == 'username':
        return [get_sender_name(user) for user in participants if
                not user.is_self and not user.bot and user.id != event.sender.id]
    elif details == 'uid':
        return [(user.id, get_sender_name(user)) for user in participants if
                not user.is_self and not user.bot and user.id != event.sender.id]


async def main(config):
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=config['log_level'])
    # logger = logging.getLogger(__name__)
    con = sqlite3.connect('users.db')
    cur = con.cursor()
    # cur.execute('''DROP TABLE users''')
    # cur.execute('''DROP TABLE lobbies''')
    print('Creating users database')
    cur.execute(
        """CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                                             userid INTEGER, 
                                             chatid INTEGER, 
                                             game TEXT, 
                                             UNIQUE(userid, chatid, game))""")
    print('Created users database')
    print('Creating lobbies database')
    cur.execute(
        """CREATE TABLE IF NOT EXISTS lobbies (id INTEGER UNIQUE PRIMARY KEY AUTOINCREMENT, 
                                               lobbyid INTEGER, 
                                               ownerid INTEGER, 
                                               chatid INTEGER, 
                                               game TEXT, 
                                               participant INTEGER, 
                                               ping INTEGER,
                                               in_lobby BOOLEAN)""")
    print('Created lobbies database')
    client = TelegramClient(**config['telethon_settings'])
    print("Starting")
    client.start(bot_token=config['bot_token'])
    print("Started")

    @client.on(events.NewMessage(pattern='/subscribe'))
    async def subscribe(event):
        if not event.is_reply:
            game = event.text.split(" ", 1)[1]
            subscribe_db(con, cur, event.message.from_id.user_id, event.chat.id, game)

            await event.reply(
                f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just subscribed to '{game}'!")
        else:
            replied_to = await event.get_reply_message()
            if 'Game:' in replied_to.text:
                game = replied_to.text.split('\n')[1]  # get "Game" line, then extract only game name.
                game = game.split(':', 1)[1].strip(' ')
                subscribe_db(con, cur, event.message.from_id.user_id, event.chat.id, game)

                await event.reply(f"You've just subscribed to '{game}'!")
            else:
                await event.reply("It's not a valid lobby, please use /subscribe <game>")

    # @client.on(events.NewMessage(pattern='/games'))
    # async def games_handler(event):
    # 	await event.reply('\n'.join(user_games(cur, event)), alert=True)

    @client.on(events.InlineQuery(pattern=''))
    async def ping_inline(event):
        games = get_user_games(cur, event)
        await event.answer(
            [event.builder.article(f'{g}', text=f'/announce {g}') for g in games])

    @client.on(events.NewMessage(pattern='/announce'))
    async def announce(event):
        game = event.text.split(' ', 1)[1]
        game_users = get_game_users(cur, event)
        chat_users = dict(await get_chat_users(client=client, event=event, details='uid'))

        if game_users and chat_users:
            lobby = await event.reply(
                f'Lobby: [{get_sender_name(event.sender)}](tg://user?id={event.sender.id})\n'
                f'Game: {game}\n',
                buttons=[[Button.inline('Ping')], [Button.inline('Join'), Button.inline('Leave')],
                         [Button.inline('Subscribe'), Button.inline('Unsubscribe')]])

            # TODO: Refactor code from 195, i think i can do better
            add_lobby_to_db(con=con,
                            cur=cur,
                            lobby_id=lobby.id,
                            owner_id=event.sender.id,
                            chat_id=event.chat.id,
                            game=game,
                            participant=event.sender.id,
                            ping_id=lobby.id,
                            in_lobby=True)

            for chunk in [game_users[x: x + 5] for x in range(0, len(game_users), 5)]:
                if lobby_chunk := ", ".join(
                        f"[{chat_users[id_]}](tg://user?id={id_})" for id_ in chunk if id_ in chat_users):
                    ping = await lobby.reply(lobby_chunk)
                    for user in chunk:
                        if user in chat_users:
                            add_lobby_to_db(con=con,
                                            cur=cur,
                                            lobby_id=lobby.id,
                                            owner_id=event.sender.id,
                                            chat_id=event.chat.id,
                                            game=game,
                                            participant=user,
                                            ping_id=ping.id,
                                            in_lobby=user == event.sender.id)

    # @client.on(events.NewMessage(pattern='/start'))
    # async def start(event):
    #     # # dialogs = await client.get_dialogs()
    #     # participants = await client.get_participants(event.input_chat.channel_id)
    #     # for u in participants:
    #     # 	if not u.is_self and not u.bot:
    #     # 		print(get_sender_name(u))
    #     users = await get_chat_users(client, event)
    #     await event.reply('Daaaavson?')

    @client.on(events.CallbackQuery(pattern=b'Subscribe'))
    async def subscribe_button(event):
        replied_to = await event.get_message()
        print(replied_to)
        if 'Game:' in replied_to.text:
            game = replied_to.text.split('\n')[1]  # get "Game" line, then extract only game name.
            game = game.split(':', 1)[1].strip(' ')
            if game not in get_user_games(cur, event):
                cur.execute("INSERT INTO users(userid, chatid, game) VALUES (?, ?, ?)",
                            (event.sender_id, event.chat.id, game))
                con.commit()
                await event.respond(
                    f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just subscribed to '{game}'!")
            else:
                await event.answer(f"It's already in your library", alert=True)
        # await event.answer('To be implemented', alert=True)

    @client.on(events.CallbackQuery(pattern=b'Unsubscribe'))
    async def unsubscribe_button(event):
        # TODO: Rethink that database access there
        replied_to = await event.get_message()
        print(replied_to)
        if 'Game:' in replied_to.text:
            game = replied_to.text.split('\n')[1]  # get "Game" line, then extract only game name.
            game = game.split(':', 1)[1].strip(' ')
            if game in [x[0] for x in cur.execute("SELECT DISTINCT game FROM users WHERE userid == ?",
                                                  (event.sender_id,)).fetchall()]:
                cur.execute("DELETE FROM users WHERE (userid, chatid, game) == (?, ?, ?)", (
                    event.sender_id, event.chat.id, game))
                con.commit()
                await event.respond(
                    f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just unsubscribed '{game}'!")
            else:
                await event.answer(f"{game} was not in your library", alert=True)
        # await event.answer('To be implemented', alert=True)

    @client.on(events.CallbackQuery(pattern=b'Join'))
    async def join_button(event):
        # TODO: Reimplement
        lobby_msg = await event.get_message()
        lobby = await get_lobby(cur=cur, event=event)
        if not is_in_lobby(userid=event.sender.id, lobby=lobby):
            change_lobby_participants(con=con, cur=cur, userid=event.sender.id, lobbyid=lobby_msg.id, joined=True)
            ...

        # replied_to = await event.get_message()
        # t = replied_to.text
        # if 'Lobby' in t and 'Game' in t:
        # 	if str(event.sender.id) not in t:
        # 		t = t.split('\n')
        # 		await replied_to.edit(
        # 			f'{t[0]} [{get_sender_name(event.sender)}](tg://user?id={event.sender.id})\n{t[1]}')
        # 		await replied_to.reply(
        # 			f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just joined this lobby!")
        # 	else:
        # 		await event.answer("You're already in the lobby")
        # else:
        # 	await event.answer(HELP1, alert=True)
        # await event.answer('To be reimplemented', alert=True)

    @client.on(events.CallbackQuery(pattern=b'Leave'))
    async def leave_button(event):
        # TODO: Reimplement
        lobby_msg = await event.get_message()
        lobby = await get_lobby(cur=cur, event=event)
        if is_in_lobby(userid=event.sender.id, lobby=lobby):
            change_lobby_participants(con=con, cur=cur, userid=event.sender.id, lobbyid=lobby_msg.id, joined=False)
            lobby = await get_lobby(cur=cur, event=event)
            if is_lobby_empty(lobby=lobby):
                remove_lobby_from_db(con=con, cur=cur, lobby_id=lobby_msg.id, chat_id=lobby_msg.chat.id)

        # if 'Lobby' in t and 'Game' in t:
        #     if str(event.sender.id) in t:
        #         t = t.split('\n')
        #         stripped = t[0].replace(f'[{get_sender_name(event.sender)}](tg://user?id={event.sender_id})', '')
        #
        #         if is_empty(stripped.strip()):
        #             await replied_to.delete()
        #         else:
        #             await replied_to.edit(f'{stripped}\n{t[1]}')
        #             await replied_to.reply(
        #                 f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just left this lobby!")
        #     else:
        #         await event.answer("You were not in the lobby")
        # else:
        #     await event.answer(HELP1, alert=True)
        # await event.answer('To be reimplemented', alert=True)

        # replied_to = await event.get_message()
        # t = replied_to.text
        # if 'Lobby' in t and 'Game' in t:
        #     if str(event.sender.id) in t:
        #         t = t.split('\n')
        #         stripped = t[0].replace(f'[{get_sender_name(event.sender)}](tg://user?id={event.sender_id})', '')
        #
        #         if is_empty(stripped.strip()):
        #             await replied_to.delete()
        #         else:
        #             await replied_to.edit(f'{stripped}\n{t[1]}')
        #             await replied_to.reply(
        #                 f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just left this lobby!")
        #     else:
        #         await event.answer("You were not in the lobby")
        # else:
        #     await event.answer(HELP1, alert=True)
        # await event.answer('To be reimplemented', alert=True)

    @client.on(events.CallbackQuery(pattern=b'Ping'))
    async def ping_button(event):
        # TODO: Finish implementing
        # users = game_users(cur, event)
        # chat_users = dict(await get_chat_users(client, event, details='uid'))
        try:
            lobby = await get_lobby(cur, event)
            print(lobby)
            await event.reply(f'```{dumps(lobby)}```')

            # for msg in lobby['pings'].split(','):
            #     if msg:
            #         await client.edit_message(entity=int(lobby['chatid']), message=int(msg), text='zmienione')

        except telethon.errors.MessageNotModifiedError as e:
            print(e)

    async with client:
        print("Good morning!")
        await client.run_until_disconnected()


if __name__ == '__main__':
    with open("config.yml", 'r') as f:
        config = yaml.safe_load(f)
        asyncio.get_event_loop().run_until_complete(main(config))
