import asyncio
import logging
import sqlite3
from typing import Tuple

from telethon import TelegramClient, events, Button
import yaml
from telethon.tl.types import User

HELP1 = 'Commands:\n' \
        '/subscribe <game>: Get notified about newly created lobbies\n' \
        '/enroll: reply to existing lobby to subscribe game\n' \
        '/join: reply to a existing lobby to join it\n' \
        '/ping: Type it in inline mode to get list of your games and to create a lobby\n' \
        '/announce <game>: Manually create a lobby'


def get_sender_name(sender: User) -> str:  # fuck davson
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


def is_empty(lobby: str) -> bool:
	return len(lobby.split(':', 1)[1]) == 0


async def main(config):
	logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=config['log_level'])
	# logger = logging.getLogger(__name__)
	con = sqlite3.connect('users.db')
	cur = con.cursor()
	# cur.execute('''DROP TABLE users''')
	cur.execute(
		"""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, userid INTEGER, username TEXT, chatid INTEGER, chatname TEXT, game TEXT, UNIQUE(userid, username, chatid, chatname, game))""")
	client = TelegramClient(**config['telethon_settings'])
	print("Starting")
	client.start(bot_token=config['bot_token'])
	print("Started")

	@client.on(events.NewMessage(pattern='/subscribe'))
	async def subscribe(event):
		if not event.is_reply:
			game = event.text.split(" ", 1)[1]
			cur.execute("INSERT INTO users(userid, username, chatid, chatname, game) VALUES (?, ?, ?, ?, ?)", (
				event.message.from_id.user_id, get_sender_name(event.message.sender), event.chat.id, event.chat.title,
				game))
			con.commit()

			await event.reply(
				f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just subscribed to '{game}'!")
		else:
			replied_to = await event.get_reply_message()
			if 'Game:' in replied_to.text:
				game = replied_to.text.split('\n')[1]  # get "Game" line, then extract only game name.
				game = game.split(':', 1)[1].strip(' ')
				cur.execute("INSERT INTO users(userid, username, chatid, chatname, game) VALUES (?, ?, ?, ?, ?)", (
					event.message.from_id.user_id, get_sender_name(event.message.sender), event.chat.id,
					event.chat.title, game))
				con.commit()
				await event.reply(f"You've just subscribed to '{game}'!")
			else:
				await event.reply("It's not a valid lobby, please use /subscribe <game>")

	# @client.on(events.NewMessage(pattern='/games'))
	# async def games(event):
	#	 await event.reply('\n'.join([x[0] for x in cur.execute("SELECT game FROM users").fetchall()]))

	@client.on(events.InlineQuery(pattern=''))
	async def ping_inline(event):
		print(event)
		user_games = cur.execute("SELECT DISTINCT game FROM users WHERE userid == ?", (event.sender.id,))
		msg = await event.answer(
			[event.builder.article(f'{g[0]}', text=f'/announce {g[0]}') for g in user_games.fetchall()])
		print(msg)

	@client.on(events.NewMessage(pattern='/announce'))
	async def ping_guys(event):
		game = event.text.split(' ', 1)[1]
		chat_id = event.chat.id
		users = cur.execute("SELECT username, userid FROM users WHERE chatid == ? AND game == ?",
		                    (chat_id, game,)).fetchall()

		msg = await event.reply(f'Lobby: [{get_sender_name(event.sender)}](tg://user?id={event.sender.id})\n'
		                        f'Game: {game}\n', buttons=[Button.inline('Join'), Button.inline('Subscribe'),
		                                                    Button.inline('Unsubscribe'), Button.inline('Leave')])
		if len(users) > 1:
			await msg.reply(
				f'{", ".join(f"[{x[0]}](tg://user?id={x[1]})" for x in users if x[1] != event.message.sender.id)}')

	@client.on(events.NewMessage(pattern='/join'))
	async def join(event):
		print(event)
		if event.is_reply:
			replied_to = await event.get_reply_message()
			t = replied_to.text
			if 'Lobby' in t and 'Game' in t:
				if str(event.sender.id) not in t:
					t = t.split('\n')
					await replied_to.edit(
						f'{t[0]}, [{get_sender_name(event.sender)}](tg://user?id={event.sender.id})\n{t[1]}')
				else:
					await event.reply("You're in the lobby already")
			else:
				await event.reply(HELP1)
		else:
			await event.reply(HELP1)

	@client.on(events.CallbackQuery(pattern=b'Subscribe'))
	async def subscribe_button(event):
		replied_to = await event.get_message()
		print(replied_to)
		if 'Game:' in replied_to.text:
			game = replied_to.text.split('\n')[1]  # get "Game" line, then extract only game name.
			game = game.split(':', 1)[1].strip(' ')
			if game not in [x[0] for x in cur.execute("SELECT DISTINCT game FROM users WHERE userid == ?",
			                                          (event.sender_id,)).fetchall()]:
				cur.execute("INSERT INTO users(userid, username, chatid, chatname, game) VALUES (?, ?, ?, ?, ?)", (
					event.sender_id, get_sender_name(event.sender), event.chat.id, event.chat.title, game))
				con.commit()
				await event.respond(
					f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just subscribed to '{game}'!")
			else:
				await event.answer(f"It's already in your library", alert=True)

	@client.on(events.CallbackQuery(pattern=b'Unsubscribe'))
	async def unsubscribe_button(event):
		replied_to = await event.get_message()
		print(replied_to)
		if 'Game:' in replied_to.text:
			game = replied_to.text.split('\n')[1]  # get "Game" line, then extract only game name.
			game = game.split(':', 1)[1].strip(' ')
			if game in [x[0] for x in cur.execute("SELECT DISTINCT game FROM users WHERE userid == ?",
			                                      (event.sender_id,)).fetchall()]:
				cur.execute("DELETE FROM users WHERE (userid, username, chatid, chatname, game) == (?, ?, ?, ?, ?)", (
					event.sender_id, get_sender_name(event.sender), event.chat.id, event.chat.title, game))
				con.commit()
				await event.respond(
					f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just unsubscribed '{game}'!")
			else:
				await event.answer(f"{game} was not in your library", alert=True)

	@client.on(events.CallbackQuery(pattern=b'Join'))
	async def join_button(event):
		replied_to = await event.get_message()
		t = replied_to.text
		if 'Lobby' in t and 'Game' in t:
			if str(event.sender.id) not in t:
				t = t.split('\n')
				await replied_to.edit(
					f'{t[0]} [{get_sender_name(event.sender)}](tg://user?id={event.sender.id})\n{t[1]}')
				await replied_to.reply(
					f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just joined this lobby!")
			else:
				await event.answer("You're already in the lobby")
		else:
			await event.answer(HELP1, alert=True)

	@client.on(events.CallbackQuery(pattern=b'Leave'))
	async def leave_button(event):
		replied_to = await event.get_message()
		t = replied_to.text
		if 'Lobby' in t and 'Game' in t:
			if str(event.sender.id) in t:
				t = t.split('\n')
				stripped = t[0].replace(f'[{get_sender_name(event.sender)}](tg://user?id={event.sender_id})', '')

				if is_empty(stripped.strip()):
					await replied_to.delete()
				else:
					await replied_to.edit(f'{stripped}\n{t[1]}')
					await replied_to.reply(
						f"[{get_sender_name(event.sender)}](tg://user?id={event.sender_id}) just left this lobby!")
			else:
				await event.answer("You were not in the lobby")
		else:
			await event.answer(HELP1, alert=True)

	async with client:
		print("Good morning!")
		await client.run_until_disconnected()


if __name__ == '__main__':
	with open("config.yml", 'r') as f:
		config = yaml.safe_load(f)
		asyncio.get_event_loop().run_until_complete(main(config))
