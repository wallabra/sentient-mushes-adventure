import yaml
import sys
import os
import logging
import triarc.backends.irc
import triarc.backends.discord
import trio
import trio_asyncio

from . import interface



def main():
    stdout_level = logging.INFO

    if os.environ.get('BOT_DEBUG', False):
        stdout_level = logging.DEBUG
    
    logging.basicConfig(stream=sys.stdout, format='%(name)-12s: %(levelname)-8s %(message)s', level=stdout_level)
    logger = logging.getLogger()
    logger.addHandler(logging.FileHandler('bot.log'))
    logger.addHandler(logging.FileHandler('last.log', 'w'))

    main_cfg = yaml.safe_load(open("config/main.yml"))
    bot, world = interface.make_game(main_cfg['gamefile'], main_cfg['prefix'])

    for s in yaml.safe_load(open("config/irc.yml")):
        print('Opening IRC connection: ', s['name'])
        
        account = s.get('account', None)

        if account:
            account = (account.get('username', None), account.get('password', None))
            print('Using account: {} [{}]'.format(account[0], '*' * len(account[1])))

        bot.register_backend(triarc.backends.irc.IRCConnection(
            nickname = s.get('nickname', 'SMAdventure'),
            realname = s.get('realname', 'The official Sentient Mushes: Adventure bot!'),

            host     = s['server'],
            port     = s.get('port', 6667),
            channels = s.get('channels', ()),

            nickserv_user = account and account[0],
            nickserv_pass = account and account[1]
        ))

        #conns[s['name']] = IRCInterface(s['name'],s['nickname'], s['realname'], s['server'], s['port'], s.get('channels', ()), s.get('account', None), s.get('prefix', '=='))
        #t = Thread(target=conns[s['name']].start, name="Bot: {}".format(s['name']))
        #threads.append(t)
        #t.start()

    for s in yaml.safe_load(open("config/discord.yml").read()):
        print('Opening Discord client: ', s['name'])
    
        bot.register_backend(triarc.backends.discord.DiscordClient(s['token']))

    async def smadv_main():
        async with trio.open_nursery() as nursery:
            nursery.start_soon(world._broadcast_loop)
            nursery.start_soon(bot.start)

    trio_asyncio.run(smadv_main)
