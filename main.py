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
    remove_lobby_from_db, parse_lobby, get_lobby_participants, get_lobby_owner
from utils.database import add_game_subscriber, get_user_games, get_chat_games, get_game_users
from utils.chat_aux import HELP1, escape_markdown, get_sender_name, get_chat_users


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
        # TODO: Create handler for subscribing, might use that also in button
        if not event.is_reply:
            game = event.text.split(" ", 1)[1]
            add_game_subscriber(con, cur, event.message.from_id.user_id, event.chat.id, game)

            await event.reply(
                f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just subscribed to '{game}'!")
        else:
            replied_to = await event.get_reply_message()
            if 'Game:' in replied_to.text:
                game = replied_to.text.split('\n')[1]  # get "Game" line, then extract only game name.
                game = game.split(':', 1)[1].strip(' ')
                add_game_subscriber(con, cur, event.message.from_id.user_id, event.chat.id, game)

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
        # TODO: Rethink aux. function for lobby creation, could use that l8er
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
        # TODO: Rethink that database access there, use aux. functions.
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
        # TODO: Rethink that database access there, use aux. functions.
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
        lobby_msg = await event.get_message()
        lobby = await get_lobby(cur=cur, event=event)
        if not is_in_lobby(userid=event.sender.id, lobby=lobby):
            change_lobby_participants(con=con, cur=cur, userid=event.sender.id, lobbyid=lobby_msg.id, joined=True)
            x = await parse_lobby(cur=cur, event=event)
            # TODO: Add the newly joined user to lobby message
            ...
        else:
            await event.answer("You're already in the lobby")

        # 	else:
        # 		await event.answer("You're already in the lobby")
        # else:
        # 	await event.answer(HELP1, alert=True)
        # await event.answer('To be reimplemented', alert=True)

    @client.on(events.CallbackQuery(pattern=b'Leave'))
    async def leave_button(event):
        lobby_msg = await event.get_message()
        lobby = await get_lobby(cur=cur, event=event)
        if is_in_lobby(userid=event.sender.id, lobby=lobby):
            change_lobby_participants(con=con, cur=cur, userid=event.sender.id, lobbyid=lobby_msg.id, joined=False)
            lobby = await get_lobby(cur=cur, event=event)
            if is_lobby_empty(lobby=lobby):
                remove_lobby_from_db(con=con, cur=cur, lobby_id=lobby_msg.id, chat_id=lobby_msg.chat.id)
                # TODO: Remove lobby and ping messages (dunno if shoulda do it here or make aux. function).
            else:
                # TODO: Remove the outgoing user from lobby message
                ...

        else:
            await event.answer("You were not in the lobby")

    @client.on(events.CallbackQuery(pattern=b'Ping'))
    async def ping_button(event):
        # TODO: Finish implementing, now its good for debugging process
        # users = game_users(cur, event)
        chat_users = dict(await get_chat_users(client, event, details='uid', with_sender=True))
        try:
            lobby = await get_lobby(cur, event)
            lobby2 = await get_lobby_participants(cur, event, True)
            lobby3 = await get_lobby_participants(cur, event, False)
            owner  = await get_lobby_owner(cur=cur, event=event)
            print(lobby)
            await event.reply(f'Lobby owner: [{chat_users[owner]}](tg://user?id={owner})')
            # await event.reply(f'```{dumps(lobby)}```')
            # await event.reply(f'```{dumps(lobby2)}```')
            # await event.reply(f'```{dumps(lobby3)}```')

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
