import asyncio
import logging
import sqlite3
import yaml

from telethon import TelegramClient, Button
from telethon.events import InlineQuery, NewMessage, CallbackQuery
from telethon.errors import MessageNotModifiedError

from utils.lobby import add_lobby_to_db, get_lobby, is_in_lobby, change_lobby_participants, is_lobby_empty, \
    remove_lobby_from_db, get_lobby_ids, get_lobby_ping_ids, get_lobby_participants
from utils.database import add_game_subscriber, get_user_games, get_game_users, remove_game_subscriber
from utils.chat_aux import get_sender_name, get_chat_users, get_subscribe_game, parse_lobby


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

    @client.on(InlineQuery(pattern=''))
    async def get_games(event):
        await event.answer(
            [event.builder.article(f'{game}', text=f'/announce {game}') for game in get_user_games(cur, event)])

    @client.on(NewMessage(pattern='/announce'))
    async def announce(event):
        game = event.text.split(' ', 1)[1]

        if chat_users := dict(await get_chat_users(client=client, event=event, details='uid', with_sender=False)):
            game_users = [user for user in get_game_users(cur, event) if user in chat_users]
            # TODO: Rethink aux. function for lobby creation (..chat_aux.parse_lobby), could use that l8er
            lobby = await event.reply(
                f'Lobby: [{get_sender_name(event.sender)}](tg://user?id={event.sender.id})\n'
                f'Game: {game}\n',
                # buttons=[[Button.inline('Ping')], [Button.inline('Join'), Button.inline('Leave')],
                #          [Button.inline('Subscribe'), Button.inline('Unsubscribe')]])
                buttons=[[Button.inline('Join'), Button.inline('Leave')],
                         [Button.inline('Subscribe'), Button.inline('Unsubscribe')]])

            # TODO: Refactor code from 195, i think i can do better
            add_lobby_to_db(con=con,
                            cur=cur,
                            event=event,
                            lobby=lobby,
                            ping=lobby,
                            game=game,
                            in_lobby=True)

            for chunk in [game_users[x: x + 5] for x in range(0, len(game_users), 5)]:
                if lobby_chunk := ", ".join(f"[{chat_users[id_]}](tg://user?id={id_})" for id_ in chunk):
                    ping = await lobby.reply(lobby_chunk)
                    for user in chunk:
                        if user in chat_users:
                            add_lobby_to_db(con=con,
                                            cur=cur,
                                            event=event,
                                            lobby=lobby,
                                            ping=ping,
                                            game=game,
                                            in_lobby=user == event.sender.id)

    @client.on(NewMessage(pattern='/games'))
    async def games(event):
        await event.reply('\n'.join(get_user_games(cur, event)))

    @client.on(NewMessage(pattern='/subscribe'))
    async def subscribe(event):
        try:
            game = await get_subscribe_game(cur=cur, event=event)
            if game not in get_user_games(cur, event):
                add_game_subscriber(con=con, cur=cur, event=event, game=game)
                await event.reply(
                    f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just subscribed to '{game}'!")
            else:
                await event.reply(f"It is already in "
                                  f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id})'s library!")
        except Exception as e:
            await event.reply(f"{e}")

    @client.on(CallbackQuery(pattern=b'Subscribe'))
    async def subscribe_button(event):
        try:
            game = await get_subscribe_game(cur=cur, event=event)
            if game not in get_user_games(cur, event):
                add_game_subscriber(con=con, cur=cur, event=event, game=game)
                await event.respond(
                    f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just subscribed to '{game}'!")
            else:
                await event.answer(f"It's already in your library", alert=True)

        except Exception as e:
            await event.answer(str(e), alert=True)

    @client.on(CallbackQuery(pattern=b'Unsubscribe'))
    async def unsubscribe_button(event):
        try:
            game = await get_subscribe_game(cur=cur, event=event)
            if game in get_user_games(cur, event):
                remove_game_subscriber(con=con, cur=cur, event=event, game=game)
                await event.respond(
                    f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just unsubscribed '{game}'!")
            else:
                await event.answer(f"{game} was not in your library", alert=True)

        except Exception as e:
            await event.answer(str(e), alert=True)

    @client.on(CallbackQuery(pattern=b'Join'))
    async def join_button(event):
        # TODO: Remove user from his/her ping message
        if not await is_in_lobby(cur=cur, event=event):
            try:
                await change_lobby_participants(con=con, cur=cur, event=event, joined=True)
                lobby_msg = await event.get_message()
                l = await parse_lobby(client=client, cur=cur, event=event)
                await lobby_msg.edit(text=l)
                await event.answer('Joined')

            except MessageNotModifiedError as e:
                print(e)
        else:
            await event.answer("You're already in the lobby")

    @client.on(CallbackQuery(pattern=b'Leave'))
    async def leave_button(event):
        if await is_in_lobby(cur=cur, event=event):
            await change_lobby_participants(con=con, cur=cur, event=event, joined=False)
            lobby = await get_lobby(cur=cur, event=event)
            await event.answer('Left')
            if is_lobby_empty(lobby=lobby):
                await client.delete_messages(event.chat.id, await get_lobby_ids(cur=cur, event=event))
                await remove_lobby_from_db(con=con, cur=cur, event=event)
            else:
                try:
                    await change_lobby_participants(con=con, cur=cur, event=event, joined=False)
                    lobby_msg = await event.get_message()
                    l = await parse_lobby(client=client, cur=cur, event=event)
                    await lobby_msg.edit(text=l)
                    await event.answer('Left')
                except MessageNotModifiedError as e:
                    print(e)

        else:
            await event.answer("You were not in the lobby")

    # @client.on(CallbackQuery(pattern=b'Ping'))
    # async def ping_button(event):
    #     # TODO: Finish implementing (delete previous pings, generate, update records in db and send new ones),
    #     #  now its good for debugging process
    #     lobby = await event.get_message()
    #     chat_users = dict(await get_chat_users(client=client, event=event, details='uid', with_sender=True))
    #     game_users = [user for user in get_game_users(cur, event)
    #                   if user in chat_users and not is_in_lobby(cur=cur, event=user, inside=True)]
    #
    #     l = await get_lobby_participants(cur=cur, event=event, in_lobby=True)
    #     print(l)
    #     p = await get_lobby_ping_ids(cur=cur, event=event)
    #     print(p)
    #
    #     # for chunk in [game_users[x: x + 5] for x in range(0, len(game_users), 5)]:
    #     #     if lobby_chunk := ", ".join(f"[{chat_users[id_]}](tg://user?id={id_})" for id_ in chunk):
    #     #         ping = await lobby.reply(lobby_chunk)
    #     #         for user in chunk:
    #     #             if user in chat_users:
    #     #                 add_lobby_to_db(con=con,
    #     #                                 cur=cur,
    #     #                                 event=event,
    #     #                                 lobby=lobby,
    #     #                                 ping=ping,
    #     #                                 game=game,
    #     #                                 in_lobby=user == event.sender.id)

    async with client:
        print("Good morning!")
        await client.run_until_disconnected()


if __name__ == '__main__':
    with open("config.yml", 'r') as f:
        config = yaml.safe_load(f)
        asyncio.get_event_loop().run_until_complete(main(config=config))
