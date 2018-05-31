import yaml
import player
import engine
import logging
import random
import textwrap

from irc.bot import ServerSpec, SingleServerIRCBot
from threading import Thread

loader = engine.XMLGameLoader()
world = loader.load_world("mushworld.xml")
commands = {}
players = {}
turnorder = []
turn = 0
last_chan = {}


def command(name):
    def __decorator__(func):
        commands[name] = func
        return func

    return __decorator__
    
def next_turn():
    global turn
    turn += 1

    if turn >= len(turnorder):
        turn = 0
        world.tick()
    
    world.broadcast(3, "It's now ", turnorder[turn], "'s turn!")
    
log_file = open('event.log', 'w')
    
def log_channel(m, place):
    log_file.write(m)
    
world.add_broadcast_channel(-1, log_channel)
    
@command('help')
def help(interface, connection, event, args):
    interface.send_message(event.target, "Available commands: {}".format(', '.join(commands.keys())))
    
@command('join')
def player_join(interface, connection, event, args):
    if event.source.nick in players:
        interface.send_message(event.target, '{}: You are already playing!'.format(event.source.nick))
        return
        
    types = {}
    
    for et in world.etypes.values():
        for k, v in et.variants.items():
            if v['attr']['isPlayer'] or 'isPlayer' in v['flags']:
                if et.id in types:
                    types[et.id].append(k)
                    
                else:
                    types[et.id] = [k]
    
    type = random.choice(tuple(types.keys()))
    variant = random.choice(types[type])
        
    p = player.PlayerInterface.join([], world, event.source.nick, world.beginning, type, variant)
    players[event.source.nick] = p
        
    def _channel(m, place):
        if place == world.from_id(p.entity.id).place:
            interface.send_message(last_chan[event.source.nick], m)
            
    p.channels.append(_channel)
    world.add_broadcast_channel(1, _channel)
        
    turnorder.append(event.source.nick)
    world.broadcast(3, "A new player joined: ", p.entity, "!")
    
@command('leave')
def player_leave(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message(event.target, '{}: Join first!'.format(event.source.nick))
        return
     
    p = players[event.source.nick]
    e = p.entity
    world.broadcast(3, '{} left the game!'.format(e))
    e['leaving'] = True
    e.call('take_damage', e['health'])
   
def player_death_system(event, entity):
    if event == 'death' and entity.name in turnorder and entity['isPlayer']:
        entity['interface'].turnorder.remove(entity.name)
        players.pop(entity.name)
        
        if entity['leaving']:
            world.broadcast(3, "It's now ", turnorder[turn], "'s turn!")
            
world.global_systems.append(player_death_system)
    
@command('pickup')
def pick_up(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message('{}: Join first!'.format(event.source.nick))
        return
        
    players[event.source.nick].pick_up(int(args[0] if len(args) > 0 else 1), (args[1] if len(args) > 1 else None))
       
@command('craft')
def craft(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message('{}: Join first!'.format(event.source.nick))
        return
        
    if len(args) < 1:
        interface.send_message(event.target, '{}: Syntax: craft <item name> [amount]'.format(event.source.nick))
        return        
        
    players[event.source.nick].craft(' '.join(args[1:]), int(args[0]))
   
   
@command('gethealth')
def gethealth(interface, connection, event, args):
    if len(args) < 1:
        interface.send_message(event.target, '{}: Syntax: gethealth <entity name (e.g. Axamur)>'.format(event.source.nick))
        return
        
    if not world.from_name(args[0]):
        interface.send_message(event.target, "{}: {} doesn't exist, I guess!".format(event.source.nick, args[0]))
        return
   
    elif world.from_name(args[0])['health'] is None:
        interface.send_message(event.target, "{}: {} isn't a living being!".format(event.source.nick, args[0]))
        return
   
    interface.send_message(event.target, "{}: {} has {} health!".format(event.source.nick, args[0], world.from_name(args[0])['health']))
   
@command('listitems')
def listitems(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message('{}: Join first!'.format(event.source.nick))
        return
        
    interface.send_message(event.target, "{}: Here you can see: {}".format(event.source.nick, ', '.join("{} x{}".format(k, v) for k, v in world.find_place(players[event.source.nick].entity.place)['items'].items())))
    
@command('listobjects')
def listobjects(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message('{}: Join first!'.format(event.source.nick))
        return
        
    interface.send_message(event.target, "{}: Here you can see: {}".format(event.source.nick, ', '.join("{} the {}".format(world.from_id(e).name, world.from_id(e).variant['name']) for e in world.entities if world.from_id(e).place == players[event.source.nick].entity.place)))
    
@command('infect')
def infect(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message(event.target, '{}: Join first!'.format(event.source.nick))
        return
        
    if event.source.nick != turnorder[turn]:
        interface.send_message(event.target, "{}: It isn't your turn yet; it's {}'s turn right now!".format(event.source.nick, turnorder[turn]))
        return
        
    if len(args) < 1:
        interface.send_message(event.target, '{}: Syntax: infect <infectee name (e.g. Azoleo)>'.format(event.source.nick))
        return
        
    if players[event.source.nick].infect(world.from_name(args[0])):
        next_turn()
          
@command('move')
def move(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message(event.target, '{}: Join first!'.format(event.source.nick))
        return
        
    if event.source.nick != turnorder[turn]:
        interface.send_message(event.target, "{}: It isn't your turn yet; it's {}'s turn right now!".format(event.source.nick, turnorder[turn]))
        return
        
    if len(args) < 1:
        interface.send_message(event.target, '{}: Syntax: move <place name>'.format(event.source.nick))
        return
        
    if players[event.source.nick].move(args[0]):
        next_turn()
         
@command('pass')
def pass_turn(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message(event.target, '{}: Join first!'.format(event.source.nick))
        return
        
    if event.source.nick != turnorder[turn]:
        interface.send_message(event.target, "{}: It isn't your turn yet; it's {}'s turn right now!".format(event.source.nick, turnorder[turn]))
        return
        
    world.broadcast(3, '{} passed the turn!'.format(event.source.nick))
    next_turn()
        
@command('attack')
def attack(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message(event.target, '{}: Join first!'.format(event.source.nick))
        return
        
    if event.source.nick != turnorder[turn]:
        interface.send_message(event.target, "{}: It isn't your turn yet; it's {}'s turn right now!".format(event.source.nick, turnorder[turn]))
        return
        
    if len(args) < 1:
        interface.send_message(event.target, '{}: Syntax: attack <enemy name (e.g. Axamur)>'.format(event.source.nick))
        return
        
    if players[event.source.nick].attack_name(args[0]):
        next_turn()
   
class IRCInterface(SingleServerIRCBot):
    def __init__(self, nick, realname, server, port, channels):
        super().__init__([ServerSpec(server, port)], nick, realname)
        self.joinchans = channels
        
        def _channel(chan):
            def __wrapper__(m, place):
                if place is None:
                    self.send_message(chan, m)
                
            return __wrapper__
                
        for j in self.joinchans:
            world.add_broadcast_channel(2, _channel(j))
    
        
    def send_message(self, channel, msg):
        for line in textwrap.wrap(msg, 350):
            self.connection.privmsg(channel, line)
        
    def on_pubmsg(self, connection, event):
        if event.arguments[0].startswith('}}'):
            last_chan[event.source.nick] = event.target
        
            cmd_full = event.arguments[0][2:]
            cmd_name = cmd_full.split(' ')[0]
            cmd_args = cmd_full.split(' ')[1:]
            
            if cmd_name in commands:
                commands[cmd_name](self, connection, event, cmd_args)
        
    def on_endofmotd(self, connection, event):
        logging.debug("Joining channel")
        
        for c in self.joinchans:
            self.connection.join(c)


if __name__ == "__main__":
    logging.basicConfig(filename="bot.log", level=logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    console.setFormatter(formatter)

    logging.getLogger('').addHandler(console)
    
    conns = {}
                
    for s in yaml.load(open("config/irc.yml").read()):
        conns[s['name']] = IRCInterface(s['nickname'], s['realname'], s['server'], s['port'], s['channels'])
        Thread(target=conns[s['name']].start, name="Bot: {}".format(s['name'])).start()
        
    # print(conns)