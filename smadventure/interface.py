from typing import Set

import math
import random
import triarc.bot
import string
import time

from collections import deque

from . import engine, namegen, player
from .common import plural, size_cm



pad_alphabet = string.ascii_uppercase + string.digits

def generate_pad(event: triarc.bot.Message, size=8):
    return PlayerPad(event, ''.join(random.choice(pad_alphabet) for _ in range(size)))

class PlayerPad:
    def __init__(self, event: triarc.bot.Message, value: str, expiration: float = 10800): # default 3 hours valid
        self.event = event
        self.value = value
        self.expiration = time.time() + expiration
        self.duration = expiration

    async def validate(self, other_value: str):
        if time.time() > self.expiration:
            return False

        if other_value == self.value:
            await self.event.reply_privately("Your single use pad '{}' has been spent.".format(self.value))
            self.expiration = time.time()
            
            return True

        return False


def make_game(world_file: str, prefix: str) -> (triarc.bot.CommandBot, engine.GameWorld):
    loader = engine.XMLGameLoader()
    world = loader.load_world(world_file)
    players = {}
    player_pads = {}
    turn_rotation = deque([None])
    player_addrs = {}
    player_names = {}
    last_chan = {}
    _chan_already = set()

    def turn_name():
        if turn_rotation[0] is None:
            if len(turn_rotation) > 1:
                return player_addrs[turn_rotation[1]]

            return '(nobody)'

        return player_addrs[turn_rotation[0]]

    async def _infra_channel(m, place, level):
        for chan in set(last_chan.values()):
            await chan.reply(m)

        return True

    world.add_broadcast_channel(engine.BCAST_EVENT, _infra_channel, name='infrachannel')

    class SMAdventureBot(triarc.bot.CommandBot):
        def __init__(self, name):
            super().__init__(name, [], prefix)

    bot = SMAdventureBot('smadventure')

    def _rotate_turn():
        turn_rotation.rotate(-1)

    async def next_turn():
        async def _tick():
            _cmds = bot.commands
            bot.commands = {k: v for k, v in bot.commands.items() if not v.important}

            await world.tick()

            bot.commands = _cmds

        if len(turn_rotation) == 1:
            return

        _rotate_turn()

        world.broadcast(3, "It's now ", turn_name(), "'s turn! {}".format("Wait for the tick to end processing first." if turn_rotation[0] is None else ""))

        if turn_rotation[0] is None:
            await _tick()

            _rotate_turn()

    log_file = open('event.log', 'w')

    def command(name: str, game_relevant: bool = False, doc: str = "There is no documentation for this command."):
        def __decorator__(func):
            @bot.add_command(name, doc)
            def command_definer(define):
                class DefinedCommand:
                    def __init__(self, important):
                        self.important = important

                    async def __call__(self, interface, event, *args):
                        last_chan[event.author_addr] = event
                        return await func(interface, event, *args)

                defined = DefinedCommand(game_relevant)

                return define(defined)

            return command_definer

        return __decorator__

    async def log_channel(m, place, level):
        log_file.write(m)

    world.add_broadcast_channel(-1, log_channel)

    @command('guide', doc="Use this command to get helpful information on a topic, such as 'command.<cmd>' to get info about the command cmd.")
    async def guide(interface, event, topic=None):
        if not topic:
            await event.reply("{}: Use the guide command to get information about a topic; for example, command.<cmd> for any command, like those commands decribed in the quickstart excerpt.".format(event.author_name))
            return

        docstr = bot.help.get(topic, "There is no such command found!")

        await event.reply("{}: {}".format(event.author_name, docstr))

    @command('quickstart', doc="Use this command to learn to play!")
    async def quickstart(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        await event.reply("{0}: First, use the {1}join command to make part of the game. Remember, every command must be prepended by '{1}' (without quotes)! Now, you must know your surroundings before performing any action. Do {1}stats to know more about you and the surrounding creatures, and, if you plan on attacking someone or something, do {1}listobjects to list every creature at your location, and {1}listitems to see what you can {1}pickup. Use {1}wield to wield weapon items, which may be found in some locations or crafted ({1}craft) from other materials. Now {1}attack an enemy, which, once weak, you may either finish off or {1}infect. You may also explore immediately reachable places using {1}paths, and reach them using {1}move. Finally, every player class has a distinct {1}special, for example, the Kangaroo's Kick, the Velociraptor's Run, or the Dragon's Firebreath. For more commands, do {1}list. Good luck".format(event.author_name, bot.prefix))
        return

    @command('players', doc="List the players currently in the game.")
    async def list_players(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        await event.reply("There are the following {} players: " + ', '.join(len(players), tuple(players.keys())))

    @command('dumpplaces', doc="List every known location in the game world.")
    async def list_places(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        await event.reply("{} places: ".format(len(world.places)) + ', '.join(map(lambda p: p['name'], world.places)))

    # @command('reset_world', True, doc="Reset the whole world! Can't be performed during tick for security reasons.")
    # async def reset_world(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        # global world, players, turnorder, turn

        # world = loader.load_world("mushworld.xml")
        # players = {}
        # turnorder = []
        # turn = 0

        # await event.reply("{}: World reloaded and player list reset.".format(event.author_name))

    @command('list', doc="List all the commands available.")
    async def list_cmds(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        await event.reply("Available commands: {}".format(', '.join(bot.commands.keys())))

    @command('turn', doc="Display the name of the current turn's player.")
    async def help(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        if len(turn_rotation) > 1:
            await event.reply("It's now {}'s turn! There are {} people around.".format(turn_name(), len(turn_rotation) - 1))

        else:
            await event.reply("Nobody's playing! :<")

    @command('makepad', doc='Generate a single-use pad to access your player.')
    async def make_new_pad(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            await event.reply('{}: You need to have a player in the first place.'.format(event.author_name))
            return

        pad = generate_pad(event)
        player_pads[pl_name] = pad

        await event.reply('{}: Done! Check private messages for more info.'.format(event.author_name))
        await event.reply_private('Your new pad code is \'{}\' (without the quotes). It expires in {}!'.format(event.author_name,
            (
                '{} seconds'.format(pad.duration)
                if int(pad.duration) < 60
                
                else (
                    '{} minutes and {} seconds'.format(math.floor(pad.duration / 60), int(pad.duration) % 60)
                    if pad.duration % 60 != 0
                    
                    else '{} minutes'.format(int(pad.duration / 60))
                )
            )
        ))

    @command('usepad', doc="Uses a single-use pad to access your player.")
    async def use_player_pad(interface: triarc.backend.Backend, event: triarc.bot.Message, value: str = None, name: str = None, *args):
        if not value:
            await message.reply('Syntax: usepad <pad> [player name]')
            return
    
        pl_name = name or player_names.get((id(interface), event.author_addr), None)
    
        pad = player_pads.get(pl_name)

        if not (pl_name and pl_name in players):
            await message.reply("{}: No such player '{}'!".format(event.author_name, pl_name))
            return

        if not pad:
            await message.reply('{}: This player \'{}\' does not have a pad!'.format(event.author_name, pl_name))
            return

        if not pad.validate(value):
            await message.reply('{}: This pad has already expired or been spent!'.format(event.author_name))
            return

        player_names[id(interface), event.author_addr] = pl_name
        await message.reply("{}: Pad used with success! You may not reuse it now. Nonetheless, you now play as {}!".format(event.author_name, str(players[pl_name].entity)))

    @command('join', doc="Join the game!")
    async def player_join(interface: triarc.backend.Backend, event: triarc.bot.Message, name: str = None, *args):
        global _chan_already

        pl_name = name or event.author_name

        player_addrs[pl_name] = event.author_name
        player_names[id(interface), event.author_addr] = pl_name

        while True:
            if pl_name in players:
                if players[pl_name].entity['dead']:
                    if len(turn_rotation) > 1:
                        await event.reply('{}: You can only rejoin after a game tick, once your body has fully rot.'.format(event.author_name))

                    else:
                        if players[pl_name].entity.id in world.entities:
                            del world.entities[players[pl_name].entity.id]
                            
                        break

                else:
                    await event.reply('{}: There is already a player with the name \'{}\'!'.format(event.author_name, pl_name))

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

        p = player.PlayerInterface.join(world, event.author_name, random.choice(world.beginning.split(';')), type, variant)

        async def _super_channel(m: str, place: Set[str], level: int):
            if place and p.entity.place in place and level < engine.BCAST_EVENT:
                await last_chan[event.author_addr].reply(m)
                return True

        world.add_broadcast_channel(engine.BCAST_INFO, _super_channel, name='superchannel:{}'.format(event.author_addr))
        
        players[pl_name] = p

        def __handle_dead_player():
            if pl_name in players:
                del players[pl_name]

            while pl_name in turn_rotation:
                turn_rotation.remove(pl_name)

        if '__handle_dead_player' not in p.entity.type.variants[p.entity.variant['id']]:
            p.entity.type.variants[p.entity.variant['id']]['__handle_dead_player'] = { p.entity.name: __handle_dead_player }

        else:
            p.entity.type.variants[p.entity.variant['id']]['__handle_dead_player'][p.entity.name] = __handle_dead_player

        assert len(turn_rotation) > 0

        if len(turn_rotation) > 1:
            turn_rotation.append(pl_name)

        else:
            turn_rotation.appendleft(pl_name)

        world.broadcast(4, "A new player joined: ", p.entity, "! Currently it is ", turn_name(), "'s turn.")

        # await event.reply("Welcome, {}. Thou hast just joined the Mush, a parasitic, mind-controlling alien fungus race. Thy goal resumes in subjugating enemies, making new friends, exploring areas, crafting... all in order to finally save the world from yet another alien race... you'll discover it all by yourself eventually. Best of luck in thy journey!".format(p.entity.name))

    @command('special', True, doc="Perform your player class' special. For example, velociraptors can move multiple places in one turn, at the cost of health, and dragons can firebreath.")
    async def special(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            await event.reply('{}: Join first!'.format(event.author_name))
            return

        p = players[pl_name]
        e = p.entity

        if e['dead']:
            await event.reply("{}: You're dead! Join back after a tick, ie, after the AI creatures' turn.".format(event.author_name))
            return

        if e.call('player_special', p, args):
            await event.reply("Special performed.")
            await next_turn()

    @command('leave', doc="Kills you.")
    async def player_leave(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            await event.reply('{}: Join first!'.format(event.author_name))
            return

        p = players[pl_name]
        e = p.entity
        world.broadcast(3, '{} left the game!'.format(e))
        e['leaving'] = True

        while not e['dead']:
            e.call('take_damage', e['health'] * 1000)

        if turn_rotation[0] == pl_name and len(turn_rotation) > 1:
            await next_turn()

        if pl_name in turn_rotation: # shouldn't, but just in case
            event.reply('Warning: Turn rotation still had former player name; removal ensured.')
            turn_rotation.remove(pl_name)

    greek_items = ['Icarus\' wing', 'ambrosia', "Zeus staff", 'Achilles boot', "Pythagoras' Number Arché Orb", "Democrat's Atomic Arché Orb"]

    @command('ping', doc="Life check. Not necessary if the guide command worked :)")
    async def ping(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        await event.reply("{}: Pong! I got another score! You're too slow at this arcade game! I mean, have you ever truly played a Pong arcade? It's more fun than you think.".format(event.author_name))

    @command('pickup', True, doc="Picks up an item lying around at your current place. List these using 'listitems'.")
    async def pick_up(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            event.reply('{}: Join first!'.format(event.author_name))
            return

        if args:
            try:
                amount = min(int(args[0]), 20 - players[pl_name].entity['pickups'])

                if len(args) > 1:
                    item = ' '.join(args[1:])

                else:
                    item = None
    
            except ValueError:
                amount = 1
                item = ' '.join(args)

        else:
            item = None
            amount = 1

        if item and not world.find_item(item):
            if amount > 1 and item[-1] in 'si':
                item = item[:-1]

                if item[-2:] == 'es':
                    item = item[:-1]

                if not world.find_item(item):
                    await event.reply("{}: No such item '{}'! Is that from some Greek myth? Like, {} don't really exist either.".format(event.author_name, plural(item), random.choice(greek_items)))
                    return

            else:
                await event.reply("{}: No such item '{}'! Is that from some Greek myth? Like, {} don't really exist either.".format(event.author_name, plural(item), random.choice(greek_items)))
                return

        if players[pl_name].pick_up(amount, item):
            if players[pl_name].entity['pickups'] >= 20:
                await next_turn()

    @command('wield', True, doc="Wields a weapon. Only one weapon can be wielded at a time, and most weapons have limited uses, and can't be used without being first wielded.")
    async def wield(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            event.reply('{}: Join first!'.format(event.author_name))
            return

        if len(args) < 1:
            players[pl_name].wield() # exactly, nothing!

        if players[pl_name].wield(' '.join(args)):
            pass # for now, I guess?

    @command('craft', True, doc="Crafts an item, based in a recipe and a prerequisite list (e.g. a flint, for planks).")
    async def craft(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            event.reply('{}: Join first!'.format(event.author_name))
            return

        if len(args) < 1:
            await event.reply('{}: Syntax: craft <amount> <item name>'.format(event.author_name))
            return

        try:
            int(args[0])

        except ValueError:
            await event.reply('{}: Syntax: craft <amount> <item name>'.format(event.author_name))
            return

        players[pl_name].craft(' '.join(args[1:]), int(args[0]))

    @command('stats', doc="Status about you. Provide an argument to display something else's status. Only living creatures.")
    async def stats(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
        name = (' '.join(args) if len(args) > 0 else pl_name)

        if name:
            e = world.from_name(name)

        else:
            if not pl_name and not args:
                await event.reply("{}: Not joined! Maybe try querying on someone (or something) else, instead?".format(event.author_name))
                
            return

        if not e:
            await event.reply("{}: No such creature named '{}'!".format(event.author_name, name))
            return

        if not e['living']:
            await event.reply("{}: '{}' is not a creature!".format(event.author_name, name))
            return

        print(str(e), str(e['mush']))
        await event.reply("{} is a {} {}, with {:.2f} hitpoints (initially {}), at {}. Has {:.2f} Rm immune level{}, weights {:.2f} kg and has a {} size ({:.2f}% the average human's size); wields {}{}, and is friends with {}.{}{}".format(
            e.name,
            e['gender'],
            e.variant['name'],
            e['health'],
            e['spawnHealth'],
            e.place,
            e['immune'],
            ('' if not e['mush'] else ', is a mush'),
            e['weight'],
            size_cm(e['size'] * 100),
            e['size'] / 1.6,
            ('' if not e['weapon'] else ('a ' if e['weapon'][0] in namegen.consonants else 'an ')),
            (e['weapon'] if e['weapon'] is not None else 'nothing'),
            (', '.join(map(lambda x: str(x), e.pointer_list('friends'))) if len(e['friends']) > 0 else 'nobody'),
            (' Is pregnant.' if e['pregnant'] else ''),
            (' Is ovulating.' if e['pregnancyTimer'] <= 4 and e['gender'] == 'female' else '')
        ))

    # @command('gethealth')
    # def gethealth(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        # if len(args) < 1:
            # await event.reply('{}: Syntax: gethealth <entity name (e.g. Axamur)>'.format(event.author_name))
            # return

        # if not world.from_name(args[0]):
            # await event.reply("{}: {} doesn't exist, I guess!".format(event.author_name, args[0]))
            # return

        # elif world.from_name(args[0])['health'] is None:
            # await event.reply("{}: {} isn't a living being!".format(event.author_name, args[0]))
            # return

        # await event.reply("{}: {} has {} health!".format(event.author_name, args[0], world.from_name(args[0])['health']))


    @command('inventory', doc="Lists your current inventory items.")
    async def inventory(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            await event.reply('{}: Join first!'.format(event.author_name))
            return

        await event.reply("{}: You have {}.".format(event.author_name, ', '.join("{} {}".format(v, plural(k, v)) for k, v in players[pl_name].entity['inventory'].items())))

    @command('listitems', doc="Lists the items in the ground at your place.")
    async def listitems(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            await event.reply('{}: Join first!'.format(event.author_name))
            return

        await event.reply("{}: Here you can see {}.".format(event.author_name, ', '.join("{} {}".format(v, plural(k, v)) for k, v in world.find_place(players[pl_name].entity.place)['items'].items())))

    @command('listobjects', doc="Lists the living objects (creatures) at the same location.")
    async def listobjects(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            event.reply('{}: Join first!'.format(event.author_name))
            return

        await event.reply("{}: Here you can see {}.".format(event.author_name, ', '.join("{} the {}".format(world.from_id(e).name, world.from_id(e).variant['name']) for e in world.entities if world.from_id(e)['living'] and world.from_id(e).place == players[pl_name].entity.place)))

    @command('infect', True, doc="Attempts to infect a living creature. A successful infection will render the target a Mush, but requires a weakened immune system, and may be dangerous for their health.")
    async def infect(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            await event.reply('{}: Join first!'.format(event.author_name))
            return

        if turn_rotation[0] != pl_name:
            await event.reply("{}: It isn't your turn yet; it's {}'s turn right now!".format(event.author_name, turn_rotation[0]))
            return

        if len(args) < 1:
            await event.reply('{}: Syntax: infect <infectee name (e.g. Azoleo)>'.format(event.author_name))
            return

        if players[pl_name].infect(world.from_name(args[0])):
            await next_turn()

    @command('paths', doc="Lists all the locations that can be directly accessed from your location with a single 'move' command.")
    async def paths(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            await event.reply('{}: Join first!'.format(event.author_name))
            return

        pl = set()

        for p in world.paths:
            if players[pl_name].entity.place in p:
                pl |= p

        pl -= {players[pl_name].entity.place}

        await event.reply("{}: From here you can go to {}".format(event.author_name, ', '.join(tuple(pl))))

    @command('move', True, doc="Finds a path toward a location, then moves you one place through it. There is a chance for failure, depending in the player class' agility.")
    async def move(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            await event.reply('{}: Join first!'.format(event.author_name))
            return

        if turn_rotation[0] != pl_name:
            await event.reply("{}: It isn't your turn yet; it's {}'s turn right now!".format(event.author_name, turn_rotation[0]))
            return

        if len(args) < 1:
            await event.reply('{}: Syntax: move <place name>'.format(event.author_name))
            return

        if world.find_place(' '.join(args)) is None:
            await event.reply('{}: No such place!'.format(event.author_name))
            return

        p = players[pl_name]
        e = p.entity
        pre_place = e.place

        res = p.move(' '.join(args))

        def _move_broadcast(lvl, *args):
            world.broadcast(lvl, *args, place=e.place)

            if pre_place != e.place:
                world.broadcast(1, *args, place=pre_place)

        assert res in ('SUCCESS', 'SLOW', 'DEAD', 'ALREADY', 'NOPATH')

        if res == 'DEAD':
            _move_broadcast(2, "{} is dead and cannot move!".format(event.author_name))

        if res == 'ALREADY':
            _move_broadcast(2, "{} is already at {}!".format(event.author_name, e.place))

        if res == 'NOPATH':
            _move_broadcast(2, "{} has found no path toward {}!".format(event.author_name, ' '.join(args)))

        if res == 'SLOW':
            _move_broadcast(2, "{} is slow and could not move to another place in one turn{}!".format(event.author_name, (' while heading toward {}'.format(' '.join(args)) if ' '.join(args) != e.place else '')))

        if res == 'SUCCESS':
            _move_broadcast(2, "{} has moved with success to {}{}!".format(event.author_name, e.place, (', heading toward {}'.format(' '.join(args)) if ' '.join(args) != e.place else '')))

        if res not in ('DEAD', 'ALREADY', 'NOPATH'):
            assert res in ('SUCCESS', 'SLOW')
            await next_turn()

    @command('pass', True, doc="Passes your turn. Equivalent to waiting in real life.")
    async def pass_turn(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            await event.reply('{}: Join first!'.format(event.author_name))
            return

        if turn_rotation[0] != pl_name:
            await event.reply("{}: It isn't your turn yet; it's {}'s turn right now!".format(event.author_name, turn_rotation[0]))
            return

        world.broadcast(3, '{} passed the turn!'.format(event.author_name))
        await next_turn()

    @command('recipe', doc="Retrieves and displays the recipe for crafting 1 unit of an item.")
    async def recipe(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        if len(args) < 1:
            await event.reply('{}: Syntax: recipe <item name (e.g. flint sword)>'.format(event.author_name))
            return

        item = world.find_item(' '.join(args))

        if item is None:
            await event.reply('{}: No such item! That sounds like mythology.'.format(event.author_name))
            return

        if 'recipe' not in item['attr']:
            await event.reply('{}: The recipe is mixing {} quarks, {} protons, {} neutrons, {} electrons and {} muons. You must essentially be Einstein and have a subatomic assembler!'.format(event.author_name, *(random.randint(20000, 9000000) for _ in range(5))))
            return

        recipe = ', '.join(("{} {}".format(v, plural(k, v))) for k, v in item['attr']['recipe'].items())
        prerequisites = ', '.join(("{} {}".format(v, plural(k, v))) for k, v in item['attr'].get('prerequisites', {}).items())

        msg = "{}:".format(event.author_name)

        if recipe:
            msg += " In order to craft 1 {}, you will spend {}.".format(item['name'], recipe)

        if prerequisites:
            msg += " In order to craft 1 {}, you must have (won't be consumed) {}.".format(item['name'], recipe)

        if not (bool(prerequisites) or bool(recipe)):
            msg += " The recipe is not apparent. I guess you can make it out of thin air, for some reason? Nonetheless, it's most likely an issue with the XML item definitions. Please warn the author about this!"

        await event.reply(msg)

    @command('attack', True, doc="Attacks a living creature, as long as it is in the same place.")
    async def attack(interface: triarc.backend.Backend, event: triarc.bot.Message, *args):
        pl_name = player_names.get((id(interface), event.author_addr), None)
    
        if not (pl_name and pl_name in players):
            await event.reply('{}: Join first!'.format(event.author_name))
            return

        if turn_rotation[0] != pl_name:
            await event.reply("{}: It isn't your turn yet; it's {}'s turn right now!".format(event.author_name, turn_rotation[0]))
            return

        if len(args) < 1:
            await event.reply('{}: Syntax: attack <enemy name (e.g. Axamur)>'.format(event.author_name))
            return

        if players[pl_name].attack_name(args[0]):
            await next_turn()

    return bot, world
