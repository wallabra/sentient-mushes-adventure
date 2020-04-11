import yaml
import sys
import logging

from botclient.irc import IRCInterface
from irc.bot import ServerSpec, SingleServerIRCBot
from threading import Thread

def main():
    logging.basicConfig(filename="bot.log", level=logging.DEBUG)
    #logging.basicConfig(filename="last.log", filemode='w', level=logging.DEBUG)
    logging.basicConfig(stream=sys.stdout, format='%(name)-12s: %(levelname)-8s %(message)s', level=logging.DEBUG)

    conns = {}
    threads = []

    for s in yaml.load(open("config/irc.yml").read()):
        conns[s['name']] = IRCInterface(s['name'],s['nickname'], s['realname'], s['server'], s['port'], s.get('channels', ()), s.get('account', None), s.get('prefix', '=='))
        t = Thread(target=conns[s['name']].start, name="Bot: {}".format(s['name']))
        threads.append(t)
        t.start()

    for s in yaml.load(open("config/discord.yml").read()):
        conns[s['name']] = IRCInterface(s['name'],s['nickname'], s['realname'], s['server'], s['port'], s.get('channels', ()), s.get('account', None), s.get('prefix', '=='))
        t = Thread(target=conns[s['name']].start, name="Bot: {}".format(s['name']))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
