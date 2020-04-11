import namegen
import player
import time
import engine
import traceback
import random
import textwrap



loader = engine.XMLGameLoader()
world = loader.load_world("mushworld.xml")
commands = {}
docs = {}
players = {}
turnorder = []
turn = 0
last_chan = {}
last_interface = {}
_chan_already = set()
ticks = 1

def next_turn():
    global turn, ticks

    def _tick():
        global commands
        _cmds = commands
        commands = {k: v for k, v in commands.items() if not getattr(v, '__important', False)}
        world.tick()
        commands = _cmds

    turn += 1

    if turn >= len(turnorder) or len(turnorder) == 0:
        turn = 0
        ticks += 1

    if len(turnorder) > 0:
        world.broadcast(3, "It's now ", turnorder[turn], "'s turn! {}".format("Wait for the tick to end processing first." if turn == 0 else ""))

        if turn == 0:
            Thread(name="Tick #%i" % ticks, target=_tick).start()

log_file = open('event.log', 'w')

def command(name, game_relevant=False, doc="There is no documentation for this command."):
    def __decorator__(func):
        setattr(func, '__important', game_relevant)
        commands[name] = func
        docs[name] = doc
        return func

    return __decorator__

def log_channel(m, place, level):
    log_file.write(m)

world.add_broadcast_channel(-1, log_channel)

@command('guide', doc="Use this command to get information about a command.")
def guide(interface, connection, event, args):
    if len(args) < 1:
        interface.send_message(event.target, "{}: Use the guide command to get information about a command, for example, those decribed in the quickstart command.".format(event.source.nick))
        return

    command = args[0]
    docstr = docs.get(command, "There is no such command found!")

    interface.send_message(event.target, "{}: {}".format(event.source.nick, docstr))

@command('quickstart', doc="Use this command to learn to play!")
def quickstart(interface, connection, event, args):
    interface.send_message(event.target, "{0}: First, use the {1}join command to make part of the game. Remember, every command must be prepended by '{1}' (without quotes)! Now, you must know your surroundings before performing any action. Do {1}stats to know more about you and the surrounding creatures, and, if you plan on attacking someone or something, do {1}listobjects to list every creature at your location, and {1}listitems to see what you can {1}pickup. Use {1}wield to wield weapon items, which may be found in some locations or crafted ({1}craft) from other materials. Now {1}attack an enemy, which, once weak, you may either finish off or {1}infect. You may also explore immediately reachable places using {1}paths, and reach them using {1}move. Finally, every player class has a distinct {1}special, for example, the Kangaroo's Kick, the Velociraptor's Run, or the Dragon's Firebreath. For more commands, do {1}list. Good luck".format(event.source.nick, interface.prefix))
    return

@command('players', doc="List the players currently in the game.")
def list_players(interface, connection, event, args):
    interface.send_message(event.target, "The following are playing: " + ', '.join(tuple(players.keys())))

@command('dumpplaces', doc="List every known location in the game world.")
def list_players(interface, connection, event, args):
    interface.send_message(event.target, "{} places: ".format(len(world.places)) + ', '.join(map(lambda p: p['name'], world.places)))

# @command('reset_world', True, doc="Reset the whole world! Can't be performed during tick for security reasons.")
# def reset_world(interface, connection, event, args):
    # global world, players, turnorder, turn

    # world = loader.load_world("mushworld.xml")
    # players = {}
    # turnorder = []
    # turn = 0

    # interface.send_message(event.target, "{}: World reloaded and player list reset.".format(event.source.nick))

@command('list', doc="List all the commands available.")
def help(interface, connection, event, args):
    interface.send_message(event.target, "Available commands: {}".format(', '.join(commands.keys())))

@command('turn', doc="Display the name of the current turn's player.")
def help(interface, connection, event, args):
    if len(turnorder) > 0:
        interface.send_message(event.target, "It's now {}'s turn!".format(turnorder[turn]))

    else:
        interface.send_message(event.target, "Nobody's playing! :<")

@command('join', doc="Join the game!")
def player_join(interface, connection, event, args):
    global _chan_already

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
    p.entity['fancy_name'] = "\x02" + event.source.nick + "\x0F"

    def _super_channel(m, place, level):
        interface.send_message(last_chan[event.source.nick], m)

    p.channels.append(_super_channel)
    players[event.source.nick] = p

    interface.chan_population[event.target] = interface.chan_population.get(event.target, set()) | {event.source.nick}

    def __handle_dead_player(e):
        global turn

        if e.name in players:
            players.pop(e.name)
            turnorder.remove(e.name)

        interface.chan_population[event.target] -= {event.source.nick}
        turn -= 1

        next_turn()

    if '__handle_dead_player' not in p.entity.type.variants[p.entity.variant['id']]:
        p.entity.type.variants[p.entity.variant['id']]['__handle_dead_player'] = { p.entity.name: __handle_dead_player }

    else:
        p.entity.type.variants[p.entity.variant['id']]['__handle_dead_player'][p.entity.name] = __handle_dead_player

    turnorder.append(event.source.nick)
    world.broadcast(4, "A new player joined: ", p.entity, "! Currently it is ", turnorder[turn], "'s turn.")

    # interface.send_message(event.target, "Welcome, {}. Thou hast just joined the Mush, a parasitic, mind-controlling alien fungus race. Thy goal resumes in subjugating enemies, making new friends, exploring areas, crafting... all in order to finally save the world from yet another alien race... you'll discover it all by yourself eventually. Best of luck in thy journey!".format(p.entity.name))

@command('special', True, doc="Perform your player class' special. For example, velociraptors can move multiple places in one turn, at the cost of health, and dragons can firebreath.")
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

@command('leave', doc="Kills you.")
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

@command('ping', doc="Life check. Not necessary if the guide command worked :)")
def ping(interface, connection, event, args):
    interface.send_message(event.target, "{}: Pong! I got another score! You're too slow at this arcade game! I mean, have you ever truly played a Pong arcade? It's awesome.".format(event.source.nick))

@command('pickup', True, doc="Picks up an item lying around at your current place. List these using 'listitems'.")
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
        if amount > 1 and item[-1] in 'si':
            item = item[:-1]

            if item[-2:] == 'es':
                item = item[:-1]

            if not world.find_item(item):
                interface.send_message(event.target, "{}: No such item '{}'! Is that from some Greek myth? Like, {} doesn't really exist either.".format(event.source.nick, item, random.choice(greek_items)))
                return

        else:
            interface.send_message(event.target, "{}: No such item '{}'! Is that from some Greek myth? Like, {} doesn't really exist either.".format(event.source.nick, item, random.choice(greek_items)))
            return

    if players[event.source.nick].pick_up(amount, item):
        if players[event.source.nick].entity['pickups'] >= 20:
            next_turn()

@command('wield', True, doc="Wields a weapon. Only one weapon can be wielded at a time, and most weapons have limited uses, and can't be used without being first wielded.")
def wield(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message('{}: Join first!'.format(event.source.nick))
        return

    if len(args) < 1:
        players[event.source.nick].wield() # exactly, nothing!

    if players[event.source.nick].wield(' '.join(args)):
        pass # for now, I guess?

@command('craft', True, doc="Crafts an item, based in a recipe and a prerequisite list (e.g. a flint, for planks).")
def craft(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message('{}: Join first!'.format(event.source.nick))
        return

    if len(args) < 1:
        interface.send_message(event.target, '{}: Syntax: craft <amount> <item name>'.format(event.source.nick))
        return

    try:
        int(args[0])

    except ValueError:
        interface.send_message(event.target, '{}: Syntax: craft <amount> <item name>'.format(event.source.nick))
        return

    players[event.source.nick].craft(' '.join(args[1:]), int(args[0]))

@command('stats', doc="Status about you. Provide an argument to display something else's status. Only living creatures.")
def stats(interface, connection, event, args):
    name = (' '.join(args) if len(args) > 0 else event.source.nick)
    e = world.from_name(name)

    if not e or not e['living']:
        interface.send_message(event.target, "{}: No such creature named '{}'!".format(event.source.nick, ' '.join(args)))
        return

    interface.send_message(event.target, "{} is a {} {}, with {:.2f} hitpoints (initially {}), at {}. Has {:.2f} Rm immune level, weights {:.2f} kg and has a {:.2f} metre size ({:.2f}% the average human's size); wields {}{}, and is friends with {}.".format(
        e.name,
        e['gender'],
        e.variant['name'],
        e['health'],
        e['spawnHealth'],
        e.place,
        e['immune'],
        e['weight'],
        e['size'] * 1.5,
        e['size'] * 100,
        ('' if not e['weapon'] else ('a ' if e['weapon'][0] in namegen.consonants else 'an ')),
        (e['weapon'] if e['weapon'] is not None else 'nothing'),
        (', '.join(map(lambda x: str(x), e.pointer_list('friends'))) if len(e['friends']) > 0 else 'nobody')
    ))

# @command('gethealth')
# def gethealth(interface, connection, event, args):
    # if len(args) < 1:
        # interface.send_message(event.target, '{}: Syntax: gethealth <entity name (e.g. Axamur)>'.format(event.source.nick))
        # return

    # if not world.from_name(args[0]):
        # interface.send_message(event.target, "{}: {} doesn't exist, I guess!".format(event.source.nick, args[0]))
        # return

    # elif world.from_name(args[0])['health'] is None:
        # interface.send_message(event.target, "{}: {} isn't a living being!".format(event.source.nick, args[0]))
        # return

    # interface.send_message(event.target, "{}: {} has {} health!".format(event.source.nick, args[0], world.from_name(args[0])['health']))

def plural(name, amount=2):
    if amount == 1:
        return name

    elif name.endswith('us') or name.endswith('is'):
        return name[:-2] + 'i'

    elif name[-1] == 's':
        return name + 'es'

    else:
        return name + 's'

@command('msg', doc="Messages someone in another channel or network, who has already said something in any channel SMAdventure is in.")
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

    last_interface[recipient].send_message(last_chan[recipient], '[{} @ {}] <{}> {}: {}'.format(event.target, interface.name, event.source.nick, recipient, message))
    interface.send_message(event.target, 'Message sent to {} @ {} ({}) succesfully!'.format(recipient, last_chan[recipient], last_interface[recipient].name))

@command('inventory', doc="Lists your current inventory items.")
def inventory(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message(event.target, '{}: Join first!'.format(event.source.nick))
        return

    interface.send_message(event.target, "{}: You have {}.".format(event.source.nick, ', '.join("{} {}".format(v, plural(k, v)) for k, v in players[event.source.nick].entity['inventory'].items())))

@command('listitems', doc="Lists the items in the ground at your place.")
def listitems(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message(event.target, '{}: Join first!'.format(event.source.nick))
        return

    interface.send_message(event.target, "{}: Here you can see {}.".format(event.source.nick, ', '.join("{} {}".format(v, plural(k, v)) for k, v in world.find_place(players[event.source.nick].entity.place)['items'].items())))

@command('listobjects', doc="Lists the living objects (creatures) at the same location.")
def listobjects(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message('{}: Join first!'.format(event.source.nick))
        return

    interface.send_message(event.target, "{}: Here you can see {}.".format(event.source.nick, ', '.join("{} the {}".format(world.from_id(e).name, world.from_id(e).variant['name']) for e in world.entities if world.from_id(e)['living'] and world.from_id(e).place == players[event.source.nick].entity.place)))

@command('infect', True, doc="Attempts to infect a living creature. Only valid for Mush creatures. Players automatically begin as Mush.")
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

@command('paths', doc="Lists all the locations that can be directly accessed from your location with a single 'move' command.")
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

@command('move', True, doc="Finds a path toward a location, then moves you one place through it. There is a chance for failure, depending in the player class' agility.")
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

@command('pass', True, doc="Passes your turn. Equivalent to waiting in real life.")
def pass_turn(interface, connection, event, args):
    if event.source.nick not in players:
        interface.send_message(event.target, '{}: Join first!'.format(event.source.nick))
        return

    if event.source.nick != turnorder[turn]:
        interface.send_message(event.target, "{}: It isn't your turn yet; it's {}'s turn right now!".format(event.source.nick, turnorder[turn]))
        return

    world.broadcast(3, '{} passed the turn!'.format(event.source.nick))
    next_turn()

@command('recipe', doc="Retrieves and displays the recipe for crafting 1 unit of an item.")
def recipe(interface, connection, event, args):
    if len(args) < 1:
        interface.send_message(event.target, '{}: Syntax: recipe <item name (e.g. flint sword)>'.format(event.source.nick))
        return

    item = world.find_item(' '.join(args))

    if item is None:
        interface.send_message(event.target, '{}: No such item! That sounds like mythology.'.format(event.source.nick))
        return

    if 'recipe' not in item['attr']:
        interface.send_message(event.target, '{}: The recipe is mixing {} quarks, {} protons, {} neutrons, {} electrons and {} muons. You must essentially be Einstein and have a subatomic assembler!'.format(event.source.nick, *(random.randint(20000, 9000000) for _ in range(5))))
        return

    recipe = ', '.join(("{} {}".format(v, plural(k, v))) for k, v in item['attr']['recipe'].items())
    prerequisites = ', '.join(("{} {}".format(v, plural(k, v))) for k, v in item['attr'].get('prerequisites', {}).items())

    msg = "{}:".format(event.source.nick)

    if recipe:
        msg += " In order to craft 1 {}, you will spend {}.".format(item['name'], recipe)

    if prerequisites:
        msg += " In order to craft 1 {}, you must have (won't be consumed) {}.".format(item['name'], recipe)

    if not (bool(prerequisites) or bool(recipe)):
        msg += " The recipe is not apparent. I guess you can make it out of thin air, for some reason? Nonetheless, it's most likely an issue with the XML item definitions. Please warn the author about this!"

    interface.send_message(event.target, msg)

@command('attack', True, doc="Attacks a living creature, as long as it is in the same place.")
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

import pg8000
conn = pg8000.connect(user='SMAdventure', password=open('sqlpass.txt').read(), database='HangmanCorpus')
cursor = conn.cursor()

@command('hm_start', doc="Begins the Hangman minigame.")
def reload_hangman(interface, connection, event, args):
    cursor.execute("SELECT * FROM Corpus ORDER BY random() LIMIT 1")
    [word, hint] = cursor.fetchone()
    interface.hangword[event.target] = word
    interface.hanghint[event.target] = hint
    interface.found[event.target] = ""
    interface.tries[event.target] = 5

    interface.send_message(event.target, "Hangman began!")
    interface.display_hangman(event)

HM_SUCCESS = [
    'Nice one!',
    'Good catch!',
    'Nice, boy!',
    'Woah there, bud! Good!',
    'Nice catch!',
    'Very good!',
    'Well done!',
    "Woah, you're pretty fly!"
]

@command('hm_guess', doc="Guesses a letter for the Hangman minigame.")
def reload_hangman(interface, connection, event, args):
    if len(set(l for l in interface.found[event.target] if l in interface.hangword[event.target])) == len(set(interface.hangword[event.target].replace(' ', ''))):
        interface.send_message(event.target, "Thou already won! Do {}hm_start again.".format(interface.prefix))
        return

    if interface.tries[event.target] <= 0:
        interface.send_message(event.target, "Game over, boy! Do {}hm_start again.".format(interface.prefix))
        return

    if event.target not in interface.tries:
        interface.send_message(event.target, "The hangman minigame has not begun yet!")
        return

    if len(args) != 1:
        interface.send_message(event.target, "Thou need to supply exactly one letter as an argument.")
        return

    if len(args[0]) != 1:
        interface.send_message(event.target, "Thou need to supply exactly ONE letter as an argument, not {}!".format(len(args[0])))
        return

    guess = args[0]

    if guess in interface.found[event.target]:
        interface.send_message(event.target, "Thou already tried the letter {}!".format(args[0].upper()))
        return

    interface.found[event.target] += guess

    if guess not in interface.hangword[event.target]:
        interface.send_message(event.target, "WRONG LETTER!")
        interface.tries[event.target] -= 1
        interface.display_hangman(event)

    else:
        if len(set(l for l in interface.found[event.target] if l in interface.hangword[event.target])) == len(set(interface.hangword[event.target].replace(' ', ''))):
            interface.send_message(event.target, "CONGRATULATIONS! Thou hast found the word!")

        else:
            interface.send_message(event.target, random.choice(HM_SUCCESS))

        interface.display_hangman(event)

class IRCInterface(SingleServerIRCBot):
    def display_hangman(self, event):
        w = self.hangword[event.target]
        self.send_message(event.target, ' '.join(((w[i].upper() if (w[i] in self.found[event.target] or self.tries[event.target] <= 0) else '_') if w[i] != ' ' else ' ') for i in range(len(w))) + ' | ' + (' Tries: {} | Hint: {}'.format(self.tries[event.target], self.hanghint[event.target]) if self.tries[event.target] > 0 else 'Game Over!'))

    def __init__(self, name, nick, realname, server, port, channels, account, prefix):
        super().__init__([ServerSpec(server, port)], nick, realname)
        self.name = name
        self.prefix = prefix
        self.joinchans = channels
        self.account = account
        self.chan_population = {}
        self.hangword = {}
        self.found = {}
        self.hanghint = {}
        self.tries = {}

        def _channel(chan):
            def __wrapper__(m, place, level):
                if (place in map(lambda p: players[p].entity.place, self.chan_population.get(chan, set())) or place is None) or level >= 3:
                    self.send_message(chan, m)
                    return True

                return False

            return __wrapper__

        for j in self.joinchans:
            world.add_broadcast_channel(2, _channel(j))

    def send_message(self, channel, msg):
        wp = textwrap.wrap(msg, 439 - len(channel))

        for i, line in enumerate(wp):
            self.connection.privmsg(channel, line)

            if i < len(wp) - 1:
                time.sleep(0.6)

    def on_pubmsg(self, connection, event):
        last_chan[event.source.nick] = event.target
        last_interface[event.source.nick] = self

        if event.arguments[0].startswith(self.prefix):
            cmd_full = event.arguments[0][len(self.prefix):]
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
            time.sleep(3)

            for c in self.joinchans:
                self.connection.join(c)

        Thread(target=_joinchan_postwait).start()
