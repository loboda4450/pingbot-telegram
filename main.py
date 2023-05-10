import asyncio
import logging

import yaml

from telethon import Button
from telethon.errors import MessageNotModifiedError
from telethon.events import InlineQuery

from utils.database import *
from utils.chat_aux import *
from utils.lobby import *


async def main(config):
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=config['log_level'])
    logger = logging.getLogger(__name__)
    client = TelegramClient(**config['telethon_settings'])
    print("Starting")
    await client.start(bot_token=config['bot_token'])
    print("Started")

    @client.on(NewMessage(pattern='/status'))
    async def status(event):
        if is_user_alive and is_lobby_alive:
            await event.reply("I'm alive!")
        elif is_user_alive and not is_lobby_alive:
            await event.reply("Lobby's dead")
        elif not is_user_alive and is_lobby_alive:
            await event.reply("User's dead")
        else:
            await event.reply("Database's dead")

    @client.on(InlineQuery())
    async def handle_iq(event):
        if event.text == '':
            await event.answer(
                [event.builder.article(f'{game}', text=f'/announce {game}') for game in get_user_games(event)])

        elif event.text == '.g' or event.text == '.games':
            await event.answer(
                [event.builder.article(f'{game}', text=f'/subscribe {game}') for game in get_chat_games()])

    @client.on(NewMessage(pattern='/announce'))
    async def announce(event):
        if game := ' '.join(event.text.split(' ', 1)[1].split()):
            if chat_users := dict(await get_chat_users(client=client, event=event, details='uid', with_sender=False)):
                game_users = [user for user in get_game_subscribers(event) if user in chat_users]
                lobby = await event.reply(
                    f'Owner: [{get_sender_name(event.sender)}](tg://user?id={event.sender.id})\n'
                    f'Game: {game}\n'
                    f'Lobby: [{get_sender_name(event.sender)}](tg://user?id={event.sender.id})',
                    buttons=[[Button.inline('Ping subs'), Button.inline('Ping lobby')],
                             [Button.inline('Join'), Button.inline('Leave')],
                             [Button.inline('Subscribe'), Button.inline('Unsubscribe')]])

                if add_lobby(event=event, lobby=lobby, participant=event.sender.id, ping=lobby, game=game,
                             in_lobby=True):
                    for chunk in [game_users[x: x + 5] for x in range(0, len(game_users), 5)]:
                        if lobby_chunk := ", ".join(f"[{chat_users[id_]}](tg://user?id={id_})" for id_ in chunk):
                            ping = await lobby.reply(lobby_chunk)
                            for user in chunk:
                                add_lobby(event=event,
                                          lobby=lobby,
                                          participant=user,
                                          ping=ping,
                                          game=game,
                                          in_lobby=user == event.sender.id)

    @client.on(NewMessage(pattern='/subscribe'))
    async def subscribe(event):
        if add_subscriber(event=event, game=await get_game(event=event)):
            await event.respond(
                f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just subscribed to "
                f"'{await get_game(event=event)}'!", buttons=[Button.inline('Subscribe'), Button.inline('Unsubscribe')])
        else:
            await event.reply(f"It is already in your library!")

    @client.on(CallbackQuery(pattern=b'Subscribe'))
    async def subscribe_button(event):
        game = await get_game(event=event)
        if add_subscriber(event=event, game=game):
            await event.respond(
                f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just subscribed to '{game}'!",
                buttons=[Button.inline('Subscribe'), Button.inline('Unsubscribe')])
        else:
            await event.answer(f"It is already in your library!", alert=True)

    @client.on(CallbackQuery(pattern=b'Unsubscribe'))
    async def unsubscribe_button(event):
        game = await get_game(event=event)
        if remove_subscriber(event=event, game=game):
            await event.respond(
                f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just unsubscribed '{game}'!",
                buttons=[Button.inline('Subscribe'), Button.inline('Unsubscribe')])
        else:
            await event.answer(f"It was not in your library!", alert=True)

    @client.on(CallbackQuery(pattern=b'Join'))
    async def join_button(event):
        lobby = await event.get_message()
        if modify_participant(lobby=lobby, participant=event.sender.id, in_lobby=True):
            msg = await parse_lobby(client=client, event=event, lobby=lobby)
            try:
                await lobby.edit(text=msg)
                await event.answer(f'Joined')
                # you gotta send a message to bot first in order to receive notifications
                await client.send_message(get_lobby_owner(lobby=lobby).ownerid, f"[{get_sender_name(event.sender)}]"
                                                                                f"(tg://user?id={event.sender_id}) "
                                                                                f"just joined [your lobby!]"
                                                                                f"(https://t.me/c/{lobby.chat.id}/{lobby.id})")

            except MessageNotModifiedError as e:
                logger.debug(e)
        else:
            await event.answer('You are already in this lobby', alert=True)

    @client.on(CallbackQuery(pattern=b'Leave'))
    async def leave_button(event):
        lobby = await event.get_message()
        if modify_participant(lobby=lobby, participant=event.sender.id, in_lobby=False):
            msg = await parse_lobby(client=client, event=event, lobby=lobby)
            try:
                await lobby.edit(text=msg)
                await event.answer(f'Left')
            except MessageNotModifiedError as e:
                logger.debug(e)

            if is_lobby_empty(lobby=lobby):
                x = get_lobby_msg_ids(lobby=lobby)
                await client.delete_messages(event.chat.id, x)
                remove_lobby(lobby=lobby)
        else:
            await event.answer('You were not in this lobby!', alert=True)

    @client.on(CallbackQuery(pattern=b'Ping subs'))
    async def ping_subs_button(event):
        lobby = await event.get_message()

        if lobby_exists(lobby=lobby):
            await delete_previous_pings(client=client, event=event, lobby=lobby)
            for reping in await parse_repings(client=client, event=event, lobby=lobby):
                newping = await lobby.reply(', '.join(reping))
                update_pings(lobby=lobby, repings=reping, newping=newping)

            await event.answer('Repinged users that were not in lobby!', alert=False)
        else:
            await event.answer('Lobby does not exist!', alert=True)

    @client.on(CallbackQuery(pattern=b'Ping lobby'))
    async def ping_lobby_button(event):
        lobby = await event.get_message()

        if lobby_exists(lobby=lobby):
            await delete_previous_pings(client=client, event=event, lobby=lobby)
            for reping in await parse_repings(client=client, event=event, lobby=lobby, inside=True):
                newping = await lobby.reply(', '.join(reping))
                update_pings(lobby=lobby, repings=reping, newping=newping)

            await event.answer('Repinged users that are in lobby!', alert=False)
        else:
            await event.answer('Lobby does not exist!', alert=True)

    async with client:
        print("Good morning!")
        await client.run_until_disconnected()


if __name__ == '__main__':
    with open("config.yml", 'r') as f:
        config = yaml.safe_load(f)
        asyncio.get_event_loop().run_until_complete(main(config=config))
