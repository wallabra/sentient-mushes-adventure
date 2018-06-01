import yaml
import namegen
import player
import time
import engine
import traceback
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
last_interface = {}

def next_turn():
    global turn
    turn += 1

    if turn >= len(turnorder) or len(turnorder) == 0:
        turn = 0
        world.tick()
    
    world.broadcast(3, "It's now ", turnorder[turn], "'s turn!")
    
log_file = open('event.log', 'w')

def command(name):
    def __decorator__(func):
        commands[name] = func
        return func

    return __decorator__
    
def log_channel(m, place, level):
    log_file.write(m)
    
world.add_broadcast_channel(-1, log_channel)
    
@command('help')
def help(interface, connection, event, args):
    interface.send_message(event.target, "Available commands: {}".format(', '.join(commands.keys())))
    
@command('turn')
def help(interface, connection, event, args):
    interface.send_message(event.target, "It's now {}'s turn!".format(turnorder[turn]))
    
@command('join')
def player_join(interface, connection, event, args):
    while True:
        if event.source.nick in players:
            if players[event.source.nick].entity['dead']:
                if len(turnorder) > 0:
                    interface.send_message(event.target, '{}: You can only rejoin after a game tick, once your body has fully rot.'.format(event.source.nick))
                    
                else:
                    world.entities.pop(players[event.source.nick].entity.index)
                    break
        
            else:
                interface.send_message(event.target, '{}: You are already playing!'.format(event.source.nick))
               
            return
        
        break
        
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
        
    p = player.PlayerInterface.join([], world, event.source.nick, random.choice(world.beginning.split(';')), type, variant)
        
    def _channel(m, place, level):
        if place == world.from_id(p.entity.id).place and level < 3:
            interface.send_message(last_chan[event.source.nick], m)
            
    p.channels.append(_channel)
    players[event.source.nick] = p
    world.add_broadcast_channel(1, _channel)
    
    def __handle_dead_player(e):
        global turn
    
        players.pop(e.name)
        turnorder.remove(e.name)
        turn -= 1
        next_turn()
    
    turnorder.append(event.source.nick)
    setattr(p.entity, '__handle_dead_player', __handle_dead_player)
        
    world.broadcast(4, "A new player joined: ", p.entity, "!")
    p.print_out("Welcome, {}. You have now joined the Mush, an infectious alien fungus race that controls brains. Your goal is to infect or kill enemies, make new friends, craft new items, discover new paths, solve puzzles... and in the end, save the world from yet another alien race...I shouldn't spoil this to you, so you'll discover it all yourself. Best of luck in your journey!".format(p.entity.name))
    
@command('special')
def special(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message(event.target, '{}: Join first!'.format(event.source.nick))
        return
        
    p = players[event.source.nick]
    e = p.entity

    if e['dead']:
        interface.send_message(event.target, "{}: You're dead! Join back after a tick, ie, after the AI creatures' turn.".format(event.source.nick))
        return
        
    if e.call('player_special', p, args):
        interface.send_message(event.target, "Special performed.")
        next_turn()
    
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
    
greek_items = ['Icarus wing', 'ambrosia', "Zeus staff", 'Achilles boots', "Pythagoras' Number Arché Orb", "Democrat's Atomic Arché Orb"]

@command('ping')
def ping(interface, connection, event, args):
    interface.send_message(event.target, "{}: Pong! I got another score! You're too slow at this arcade game! I mean, have you ever truly played a Pong arcade? It's awesome.".format(event.source.nick))
    
@command('pickup')
def pick_up(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message('{}: Join first!'.format(event.source.nick))
        return
        
    try:
        int(args[0])
        
    except ValueError:
        interface.send_message(event.target, '{}: Syntax: pickup [amount default=1] [item (defaults to random)]'.format(event.source.nick))
        return
        
    item = (args[1] if len(args) > 1 else None)   
    amount = min(int(args[0] if len(args) > 0 else 1), 20 - players[event.source.nick].entity['pickups'])
    
    if item and not world.find_item(item):
        if amount > 1 and item.endswith('s'):
            item = item.rstrip
        
            if not world.find_item(item):
                interface.send_message(event.target, "{}: No such item '{}'! Is that from some Greek myth? Like, {} doesn't really exist either.".format(event.source.nick, item, random.choice(greek_items)))
                return
        
        else:    
            interface.send_message(event.target, "{}: No such item '{}'! Is that from some Greek myth? Like, {} doesn't really exist either.".format(event.source.nick, item, random.choice(greek_items)))
            return
        
    if players[event.source.nick].pick_up(amount, item):
        if players[event.source.nick].entity['pickups'] >= 20:
            next_turn()
            
@command('wield')
def wield(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message('{}: Join first!'.format(event.source.nick))
        return
        
    if len(args) < 1:
        players[event.source.nick].wield() # exactly, nothing!
        
    if players[event.source.nick].wield(args[0]):
        pass # for now, I guess?
    
@command('craft')
def craft(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message('{}: Join first!'.format(event.source.nick))
        return
        
    try:
        int(args[0])
        
    except ValueError:
        interface.send_message(event.target, '{}: Syntax: craft <amount> <item name>'.format(event.source.nick))
        return        
        
    if len(args) < 1:
        interface.send_message(event.target, '{}: Syntax: craft <amount> <item name>'.format(event.source.nick))
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
  
def plural(name, amount=2):
    if amount == 1:
        return name
    
    elif name.endswith('us') or name.endswith('is'):
        return name[:-2] + 'i'

    elif name[-1] == 's':
        return name + 'es'
        
    else:
        return name + 's'
   
@command('msg')
def send_msg(interface, connection, event, args):
    if len(args) <= 1:
        interface.send_message(event.target, "{}: Syntax: msg <recipient name, e.g. '{}' (random example)> <message>".format(event.source.nick, random.choice(tuple(last_chan.keys())) if len(last_chan) > 0 else 'Somebody'))
        return
        
    if args[0] == event.source.nick:
        interface.send_message(event.target, "{}: Nice syntax.... but I'm not a mirror!".format(event.source.nick))
        return

    recipient = args[0].rstrip(':') # QUESTIONABLE: is it possible for an IRC nick to have ':' ?
    message = ' '.join(args[1:])
        
    if recipient not in last_chan:
        interface.send_message(event.target, '{}: Recipient is unknown!'.format(event.source.nick))
        return
        
    last_interface[recipient].send_message(last_chan[recipient], '[{} @ {}] <{}> {}: {}'.format(event.target, last_interface[recipient].name, event.source.nick, recipient, message))
    interface.send_message(event.target, 'Message sent to {} @ {} ({}) succesfully!'.format(recipient, last_chan[recipient], last_interface[recipient].name))
   
@command('inventory')
def inventory(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message(event.target, '{}: Join first!'.format(event.source.nick))
        return
        
    interface.send_message(event.target, "{}: You have {}.".format(event.source.nick, ', '.join("{} {}".format(v, plural(k, v)) for k, v in players[event.source.nick].entity['inventory'].items())))
   
@command('listitems')
def listitems(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message(event.target, '{}: Join first!'.format(event.source.nick))
        return
        
    interface.send_message(event.target, "{}: Here you can see {}.".format(event.source.nick, ', '.join("{} {}".format(v, plural(k, v)) for k, v in world.find_place(players[event.source.nick].entity.place)['items'].items())))
    
@command('listobjects')
def listobjects(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message('{}: Join first!'.format(event.source.nick))
        return
        
    interface.send_message(event.target, "{}: Here you can see {}.".format(event.source.nick, ', '.join("{} the {}".format(world.from_id(e).name, world.from_id(e).variant['name']) for e in world.entities if world.from_id(e).place == players[event.source.nick].entity.place)))
    
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
          
@command('paths')
def paths(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message(event.target, '{}: Join first!'.format(event.source.nick))
        return
        
    pl = set()
    
    for p in world.paths:
        if players[event.source.nick].entity.place in p:
            pl |= p
            
    pl -= {players[event.source.nick].entity.place}
    
    interface.send_message(event.target, "{}: From here you can go to {}".format(event.source.nick, ', '.join(tuple(pl))))
          
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
        
    if world.find_place(' '.join(args)) is None:
        interface.send_message(event.target, '{}: No such place!'.format(event.source.nick))
        return
        
    e = players[event.source.nick].entity
    res = players[event.source.nick].move(' '.join(args))
    rnames = ['WARNING', 'FAILED', 'SUCCESS']
    
    # if res == 2:
    #    interface.send_message(event.target, "{} has moved with success to {}{}!".format(event.source.nick, e.place, (', heading toward {}'.format(' '.join(args)) if ''.join(args) != e.place else '')))
    
    if res:
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
    def __init__(self, name, nick, realname, server, port, channels, account):
        super().__init__([ServerSpec(server, port)], nick, realname)
        self.name = name
        self.joinchans = channels
        self.account = account
        
        def _channel(chan):
            def __wrapper__(m, place, level):
                if place is None or level >= 3:
                    self.send_message(chan, m)
                
            return __wrapper__
                
        for j in self.joinchans:
            world.add_broadcast_channel(2, _channel(j))
    
        
    def send_message(self, channel, msg):
        for line in textwrap.wrap(msg, 350):
            self.connection.privmsg(channel, line)
        
    def on_pubmsg(self, connection, event):
        last_chan[event.source.nick] = event.target
        last_interface[event.source.nick] = self
    
        if event.arguments[0].startswith('}}'):
            cmd_full = event.arguments[0][2:]
            cmd_name = cmd_full.split(' ')[0]
            cmd_args = cmd_full.split(' ')[1:]
            
            if cmd_name in commands:
                try:
                    print("Executing command: " + cmd_name)
                    commands[cmd_name](self, connection, event, cmd_args)
                    
                except Exception as e:
                    self.send_message(event.target, "[{}: {} processing the '{}' command! ({})]".format(event.source.nick, type(e).__name__, cmd_name, str(e)))
                    traceback.print_exc()
        
    def on_endofmotd(self, connection, event):
        logging.debug("Joining channel")
       
        if self.account:
            self.connection.privmsg('NickServ', 'IDENTIFY {} {}'.format(self.account['username'], self.account['password']))
        
        def _joinchan_postwait():
            time.sleep(2.5)
        
            for c in self.joinchans:
                self.connection.join(c)

        Thread(target=_joinchan_postwait).start()

if __name__ == "__main__":
    logging.basicConfig(filename="bot.log", level=logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    console.setFormatter(formatter)

    logging.getLogger('').addHandler(console)
    
    conns = {}
    threads = []
          
    for s in yaml.load(open("config/irc.yml").read()):
        conns[s['name']] = IRCInterface(s['name'],s['nickname'], s['realname'], s['server'], s['port'], s.get('channels', ()), s.get('account', None))
        t = Thread(target=conns[s['name']].start, name="Bot: {}".format(s['name']))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()