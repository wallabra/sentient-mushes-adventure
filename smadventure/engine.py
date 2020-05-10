try:
    import simplejson as json

except ImportError:
    import json

import trio
import logging
import random
import sys

sys.modules['_elementtree'] = None

import xml.etree.ElementTree as etree

from . import namegen, player, embedcode
from queue import Queue, Empty



class LineTrackingParser(etree.XMLParser):
    def _start(self, *args, **kwargs):
        element = super(self.__class__, self)._start(*args, **kwargs)
        element._start_line = self.parser.CurrentLineNumber
        return element


idnum = 0 # The default ID counter.


# Broadcast levels
BCAST_VERBOSE = -2
BCAST_DEBUG = -1
BCAST_INFO = 0
BCAST_INTERESTING = 1
BCAST_IMPORTANT = 2
BCAST_EVENT = 3

class EntityType(object):
    """An entity type.

    Think like this: each kind of entity ingame perform
    a distinct set of actions and obey to a distinct
    set of rules. Each entity is just a string in a
    list, but this string is changed by instances of this
    class, which will perform these actions in place of the
    functionally inane entity string.

    So, if we have a 'dragon#Mountain#large#{""}'"""

    def __init__(self, name, id=None, base_attributes=(), variants=(), functions=(), systems=(), default_entity_attr=()):
        global idnum

        self.name = name
        self.id = id or idnum
        self.base_attributes = dict(base_attributes)
        self.variants = dict(variants)
        self.functions = dict(functions)
        self.systems = list(systems)
        self.default_attr = dict(default_entity_attr)

        for k, v in variants.items():
            variants[k]['flags'] = set(v['flags'])

        base_attributes['flags'] = set(base_attributes['flags'])

        for k, v in dict(base_attributes['attr']).items():
            for vk, vv in dict(variants).items():
                if k not in vv['attr']:
                    self.variants[vk]['attr'][k] = v

        for f in base_attributes['flags']:
            for vk, vv in dict(variants).items():
                if f not in vv['flags']:
                    self.variants[vk]['flags'].add(f)

        if not id:
            idnum += 1

    def __str__(self):
        return self.name

    def instantiate(self, world, place, variant, name=None, extra_attr={}):
        """Creates an entity in its default state and returns it."""

        if isinstance(variant, dict):
            variant = variant['id']

        attr = dict(self.default_attr)

        for k, v in self.variants[variant]['default'].items():
            attr[k] = v

        for k, v in extra_attr.items():
            attr[k] = v

        id = ''.join([random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(24)])

        while world.from_id(id):
            id = ''.join([random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(24)])

        return [id, self.id, name or namegen.generate_name(random.randint(6, 15)), place, variant, attr]

    def call(self, func, entity, *args, **kwargs):
        if entity is None:
            return None

        return self.functions[func](entity, *args, **kwargs)

class LoadedEntity(object):
    def __init__(self, world, spl):
        self.world = world
        self.spl = spl
        self.despawned = False

    @property
    def id(self):
        return self.spl[0]

    @property
    def type(self):
        return self.world.etypes[self.spl[1]]

    @property
    def name(self):
        return self.spl[2]

    @name.setter
    def name(self, val):
        self.spl[2] = val

    @property
    def place(self):
        return self.spl[3]

    @place.setter
    def place(self, val):
        self.spl[3] = val

    @property
    def variant(self):
        return self.type.variants[self.spl[4]]

    @variant.setter
    def variant(self, variant):
        if isinstance(variant, dict):
            variant = variant['id']

        self.spl[4] = variant

    @property
    def attr(self):
        return self.spl[5]

    #========

    def __dict__(self):
        return self.attr

    def __hash__(self):
        return hash(self.id)

    def set_variant(self, variant):
        if self.despawned:
            return

        for k, v in self.variant['default'].items():
            if k in self.attr and self.attr[k] == v:
                self.attr.pop(k)

        self.variant = self.type.variants[variant]

        for k, v in self.variant['default'].items():
            if k not in self.attr:
                self.attr[k] = v

    def __deitem__(self, key):
        sentinel = object()
        
        if self.pop(key, sentinel) is sentinel:
            loggings.warn('No attribute "{}" found when trying to delete it in entity "{}" ({})'.format(key, str(self), self.id))

    def pop(self, key, default=None):
        if self.despawned:
            return

        res = self.attr.pop(key, default)

        return res

    def __setitem__(self, key, val):
        if self.despawned:
            return

        self.attr[key] = val

    def pointer(self, key):
        if not self[key]:
            return None

        return self.world.from_id(self[key])

    def pointer_set(self, key, ent):
        if not ent:
            self[key] = None

        self[key] = ent.id

    def pointer_list(self, key):
        for a in self[key]:
            if a and a in self.world.entities:
                yield self.world.from_id(a)

    def spawn(self, type=None, variant=None, place=None, extra_attr=None, return_loaded=True):
        if type is None:
            type = self.type

        elif isinstance(type, str):
            _a = type
            type = self.world.etypes[type]

            if not type:
                raise ValueError("No such entity type: {}".format(_a))

        if variant is None:
            variant = random.choice(tuple(type.variants.keys()))

        if place is None:
            place = self.place

        if extra_attr is None:
            extra_attr = {}

        e = type.instantiate(self.world, place, variant, extra_attr)

        self.world.add_entity(e)
        self.world.unload_all()

        if return_loaded:
            return self.world.from_ent(e)

        else:
            return e[0]

    def of(self, type):
        return self.etype.id == type

    def set_name(self, name):
        if self.despawned:
            return

        self.name = name

    def __repr__(self):
        return 'Entity<{} {}>'.format(self.variant['name'], repr(self.name))

    def __getitem__(self, key):
        if self.despawned:
            return None

        a = self.attr.get(key)
        b = (a if a is not None else self.variant['attr'].get(key))

        return (b if b is not None else (True if key in self.variant['flags'] else None))

    def call(self, func, *args, **kwargs):
        if self.despawned:
            return

        fspace = getattr(self.type.functions[func], '__funcspace', "")

        if fspace != "":
            fspace = "<" + fspace + ">"

        logging.debug("ENTITY CALL: {}('{}', '{}', '{}').{}{}({})".format(self.type.id, self.name, self.variant['name'], self.place, func, fspace, ', '.join([(repr(a.name) if isinstance(a, LoadedEntity) else (repr(a.entity.name) if isinstance(a, player.PlayerInterface) else repr(a))) for a in args])))
        return self.type.call(func, self, *args, **kwargs)

    def event(self, evt, *args, **kwargs):
        if self.despawned:
            return

        for s in self.type.systems:
            s(evt, self, *args, **kwargs)

        for s in self.variant['systems']:
            s(evt, self, *args, **kwargs)

        for s in self.world.global_systems:
            s(evt, self, *args, **kwargs)

    def set_place(self, p):
        if self.despawned:
            return

        self.place = p

    def despawn(self):
        self.world.queue_removal(self.id)

        self.despawned = True

    def print_attr(self):
        if self.despawned:
            return

        for k, v in self.attr.items():
            print('  * {} -> {}'.format(k, v))

    def get_name(self):
        return self['fancy_name'] if self['fancy_name'] is not None else self.name

    def __str__(self):
        return "{} the {} from {}".format(self.get_name(), self.variant['name'], self.place)

class GameWorld(object):
    def __init__(self, etypes=(), paths=(), places=(), entities=(), item_types=(), beginning=None):
        self.etypes = dict(etypes)
        self.paths = list(paths)
        self.places = dict(places)
        self.entities = dict(entities)
        
        self.entity_names = {}
        
        for e in self:
            self.entity_names.setdefault(e[2], set()).add(e[0])
        
        self.item_types = dict(item_types)
        self.beginning = beginning

        self.message_queue = Queue()
        self.broadcast_channels = set()
        self.global_systems = []

        self._last_tick_removals = set()

        self._queued_removals = None

    def dumps(self, yaml=True):
        save = {
            'entities': self.entities,
            'places': self.places
        }

        if yaml:
            return yaml.dump(save)

        return json.dumps(save)

    def loads(self, data, yaml=True):
        if yaml:
            data = yaml.load(data)

        else:
            data = json.loads(data)

        self.entities = data['entities']
        self.places = data['places']

    def add_broadcast_channel(self, level, *channels, name=None):
        for c in channels:
            setattr(c, '_level', level)

        if name:
            for c in channels:
                setattr(c, '__chan_name', name)

        self.broadcast_channels |= set(channels)

    def remove_broadcast_channel(self, name):
        for bc in set(self.broadcast_channels):
            bcname = getattr(bc, '__chan_name', None)

            if bcname and bcname == name and bc in self.broadcast_channels:
                self.broadcast_channels.remove(bc)

    def broadcast(self, level, *message, place=None, to=None):
        if isinstance(place, str):
            place = {place}

        self.message_queue.put((level, message, place, to))

    async def _broadcast_loop(self):
        while True:
            try:
                level, message, place, to = self.message_queue.get_nowait()

            except Empty:
                await trio.sleep(0.3)
                continue

            m = ""

            for node in message:
                m += str(node)

            logging.debug("BROADCAST: PLACE={} LVL={} MSG={}".format(repr(place), level, repr(m)))

            can_wait = [False]

            async def broadcast_to(channel):
                if not hasattr(channel, '_level') or level >= channel._level:
                    can_wait[0] = await channel(m, place, level) or can_wait[0]

            if to:
                await broadcast_to(to)

            for b in self.broadcast_channels:
                await broadcast_to(b)

            if can_wait[0]:
                await trio.sleep(0.5)

            else:
                await trio.sleep(0)

    async def tick(self):
        perc = 0

        self._queued_removals = set()

        for eid, e in self.entities.items():
            if eid not in self._queued_removals:
                en = LoadedEntity(self, e)

                if 'tick' in en.type.functions:
                    try:
                        en.call('tick')

                    except BaseException:
                        print(repr(en), str(en))
                        raise

                en.event('tick')

            perc += 1

            logging.debug("TICK: {:.2f}% complete.".format(100.0 * perc / len(self.entities)))

        self.broadcast(4, '<Tick finished.>')
        self.resolve_removals()

        self._queued_removals = None

    def queue_removal(self, eid):
        self._queued_removals.add(eid)

    def resolve_removals(self):
        for qr in self._queued_removals:
            self._last_tick_removals.add(qr)
            n = self.from_id(qr).name

            del self.entities[qr]

            self.entity_names[n].remove(qr)

            if not self.entity_names[n]:
                del self.entity_names[n]

        self._queued_removals = set()

    def add_entity(self, e):
        ent = LoadedEntity(self, e)

        self.entities[ent.id] = e
        self.entity_names.setdefault(ent.name, set()).add(ent.id)

        if 'init' in self.etypes[e[1]].functions:
            ent.call('init')

    def find_item(self, name):
        return self.item_types.get(name, None)

    def find_place(self, name):
        return self.places.get(name, None)

    def from_name(self, name):
        if name in self.entity_names:
            return [self.from_id(x) for x in self.entity_names[name]][0]

        return None

    def from_id(self, eid):
        if eid not in self.entities:
            return None
    
        return self.from_ent(self.entities[eid])

    def from_ent(self, e):
        assert e[0] in self.entities
        return LoadedEntity(self, e)

    def __iter__(self):
        return (self.from_ent(e) for e in self.entities.values())

    def all_in_place(self, cplace):
        for e in self:
            if e.place == cplace:
                yield e

class GameLoader(object):
    """A class which children will load
    SMA (Sentient Mushes: Adventure) and derivated
    games for you."""

    def __init__(self):
        if type(self) is GameLoader:
            raise TypeError("Do not use GameLoader directly!")

    def load_world(self, filename):
        """Returns a GameWorld instance containing all of the
        Location instances that represent places in
        the game world. This should also call self.load_entity_type
        so that it may load the referenced entity types into the
        game world."""
        return None

    def load_entity_type(self, filename):
        """Returns an EntityType instance.

        The filename is one of the entity type filenames
        described by the world. EntityType must be called
        to create the instance after processing the file's
        content."""
        return None

class XMLGameLoader(object):
    """The default loader. Sentient Mushes: Adventure is XML!
    (I'm tired of people telling me XML sucks, please shut up,
    I use what I want! I'm *indie*!)"""

    def load_world(self, filename):
        """Returns a GameWorld instance containing all of the
        Location instances that represent places in
        the game world."""
        xworld = etree.parse(open(filename))

        world = GameWorld(beginning=xworld.getroot().get('beginning'))
        funcholder = embedcode.CodeHolder()

        logging.info("Loading entity types...")

        for el in xworld.getroot():
            if el.tag == 'etypes':
                for t in el:
                    if t.tag == 'etype':
                        (e, items) = self.load_entity_type(world, t.get('filename'), funcholder)
                        world.etypes[e.id] = e

                        for item in items:
                            world.item_types[item['name']] = item

        funcholder.deinit()

        logging.info("Loading and populating places...")

        for el in xworld.getroot():
            if el.tag == "places":
                for p in el:
                    if p.tag == "place":
                        i = {}
                        attr = {}

                        for sub in p:
                            if sub.tag == "flock":
                                if sub.get('type') in world.etypes:
                                    amount = sub.get('amount')

                                    if '-' in amount:
                                        amount = random.randint(int(amount.split('-')[0]), int(amount.split('-')[1]))

                                    else:
                                        amount = int(amount)

                                    for _ in range(amount):
                                        world.add_entity(world.etypes[sub.get('type')].instantiate(world, p.get('name'), (random.choice(sub.get('variant').split(';')) if sub.get('variant') != '*' else random.choice(tuple(world.etypes[sub.get('type')].variants.keys())))))

                                    # print('  * Adding {} {} entities.'.format(amount, world.etypes[sub.get('type')].name))

                            elif sub.tag == "entity":
                                if sub.get('type') in world.etypes:
                                    world.add_entity(world.etypes[sub.get('type')].instantiate(world, p.get('name'), (random.choice(sub.get('variant').split(';')) if sub.get('variant') != '*' else random.choice(tuple(world.etypes[sub.get('type')].variants.keys())))))

                            elif sub.tag == "attr":
                                attr[sub.get('key')] = sub.get('value', None)

                            elif sub.tag == "items":
                                if world.find_item(sub.get('type')):
                                    amount = sub.get('amount')

                                    if amount:
                                        if '-' in amount:
                                            amount = random.randint(int(amount.split('-')[0]), int(amount.split('-')[1]))

                                        else:
                                            amount = int(amount)

                                    else:
                                        amount = 1

                                    if sub.get('type') in i:
                                        i[sub.get('type')] += amount

                                    else:
                                        i[sub.get('type')] = amount

                        logging.debug("- Loaded place {}".format(p.get('name')))

                        new_place = {
                            'name': p.get('name'),
                            'attr': attr,
                            'items': i
                        }

                        world.places[p.get('name')] = new_place

            elif el.tag == "paths":
                for p in el:
                    if p.tag == "path":
                        world.paths.append(set(p.get('ends').split(';')))

        logging.info("World loaded!")

        return world

    def load_entity_type(self, world, filename, funcholder=None):
        """Returns an EntityType instance.

        The filename is one of the entity type filenames
        described by the world. EntityType must be called
        to create the instance after processing the file's
        content."""

        try:
            item_types = [] # Entity's item definitions

            etype = etree.parse(open(filename), parser=LineTrackingParser())
            name = etype.getroot().get('name')
            id = etype.getroot().get('id')

            functions = {}
            base = { 'attr': {}, 'flags': set() }
            variants = {}
            systems = []
            default = {}

            def import_attr(el, level=1):
                href = el.get('href')
                imported = etree.parse(open(href), parser=LineTrackingParser())

                for a in imported.getroot():
                    if a.tag == "attribute":
                        if a.get('key') not in default:
                            default[a.get('key')] = eval(a.get('value'))

                    elif a.tag == "declare":
                        default[a.get('key')] = None

                    elif a.tag == "import":
                        import_attr(a, level + 1)

                    elif a.tag == "flag":
                        base['flags'].add(a.get('name'))

                    elif a.tag == "unflag":
                        base['flags'] -= {a.get('name')}

                    elif a.tag == "static" and a.get('name') not in base['attr']:
                        base['attr'][a.get('name')] = eval(a.get('value'))

                    elif a.tag == "function":
                        if (a.get('name') not in functions) or (level <= getattr(functions[a.get('name')], '__priority', 0)):
                            fname = a.get('name')

                            for fnc in funcholder.quick("{}-{}".format(imported.getroot().get('name'), a.get('name')), a.text, linepad=a._start_line, filename=href).values():
                                if fnc.__lookup_name__ == fname:
                                    setattr(fnc, '__priority', level)
                                    setattr(fnc, '__funcspace', imported.getroot().get('name'))

                                    functions[fname] = fnc

                                    break

                            else: raise RuntimeError("No matching function for method '{}' in while parsing Attribute Imports '{}' referenced by Entity Type '{}'!".format(fname, imported.getroot().get('name'), id))

                    elif a.tag == 'item':
                        name = a.get('name')

                        i = {
                            'name': name,
                            'functions': {},
                            'attr': {},
                            'flags': set()
                        }

                        for char in a:
                            if char.tag == 'function':
                                i['functions'][char.get('name')] = funcholder.quick('{}-{}'.format(a.get('name'), char.get('name')), char.text, linepad=char._start_line, filename=href)

                            elif char.tag == 'attribute':
                                val = char.get('value')

                                if val:
                                    i['attr'][char.get('key')] = eval(val)

                                else:
                                    i['attr'][char.get('key')] = None

                            elif char.tag == 'flag':
                                i['flags'].add(char.get('name'))

                        item_types.append(i)

            _f = funcholder is None

            if _f:
                funcholder = embedcode.CodeHolder()

            for sub in etype.getroot():
                if sub.tag == "functions":
                    for f in sub:
                        if f.tag == "function":
                            fname = f.get('name')

                            for fnc in funcholder.quick("{}-{}".format(id, f.get('name')), f.text, linepad=f._start_line, filename=filename).values():
                                if fnc.__lookup_name__ == fname:
                                    functions[fname] = fnc
                                    break

                            else: raise RuntimeError("No matching function for method '{}' while parsing Entity Type '{}'!".format(f.get('name'), id))

                elif sub.tag == "base":
                    for a in sub:
                        if a.tag == "attr":
                            base['attr'][a.get('name')] = eval(a.get('value'))

                        elif a.tag == "flag":
                            base['flags'].add(a.get('name'))

                        elif a.tag == "unflag":
                            base['flags'] -= {a.get('name')}

                elif sub.tag == "systems":
                    for sys in sub:
                        if sys.tag == "system":
                            sname = sys.get('name')

                            for fnc in funcholder.quick("{}-{}".format(id, sname), open(sys.get('href')).read(), filename=sys.get('href')).values():
                                if fnc.__lookup_name__ == sname:
                                    systems.append(fnc)
                                    break

                            else: raise RuntimeError("No matching function for system '{}' while parsing Entity Type '{}'!".format(sys.get('name'), id))

                elif sub.tag == "default":
                    for att in sub:
                        if att.tag == "import":
                            # print("Importing attribute library: {}".format(a.get('name')))
                            import_attr(att)

                        elif a.tag == "declare":
                            default[att.get('key')] = None

                        elif att.tag == "attribute":
                            default[att.get('key')] = eval(att.get('value'))

                elif sub.tag == "itemdefs":
                    for item in sub:
                        if item.tag == 'item':
                            i = {
                                'name': item.get('name'),
                                'functions': {},
                                'attr': {},
                                'flags': set()
                            }

                            for char in item:
                                if char.tag == 'function':
                                    cname = char.get('name')

                                    for fnc in funcholder.quick('{}-{}'.format(i['name'], cname), char.text, linepad=char._start_line, filename=filename).values():
                                        if fnc.__lookup_name__ == cname:
                                            i['functions'][cname] = fnc
                                            break

                                    else: raise RuntimeError("No matching function for item function '{}' while parsing item '{}' in Entity Type '{}'!".format(cname, i['name'], id))

                                elif char.tag == 'attribute':
                                    val = char.get('value')

                                    if val:
                                        i['attr'][char.get('key')] = eval(val)

                                    else:
                                        i['attr'][char.get('key')] = None

                                elif char.tag == 'flag':
                                    i['flags'].add(char.get('name'))

                            item_types.append(i)

                elif sub.tag == "variants":
                    for va in sub:
                        v = { 'name': va.get('name'), 'id': va.get('id'), 'attr': {}, 'flags': set(), 'default': {}, 'systems': [] }

                        for a in va:
                            if a.tag == "attr":
                                v['attr'][a.get('name')] = eval(a.get('value'))

                            elif a.tag == "flag":
                                v['flags'].add(a.get('name'))

                            elif a.tag == "unflag":
                                v['flags'] -= {a.get('name')}

                            elif a.tag == "default":
                                v['default'][a.get('key')] = eval(a.get('value'))

                            elif a.tag == "system":
                                sname = sys.get('name')

                                for fnc in funcholder.quick("{}-{}-{}".format(id, sname), v['id'], open(sys.get('href')).read(), filename=sys.get('href')).values():
                                    if fnc.__lookup_name__ == sname:
                                        v.systems.append(fnc)
                                        break

                                else: raise RuntimeError("No matching function for system '{}' while parsing Entity Type '{}'!".format(sys.get('name'), id))

                        variants[va.get('id')] = v

        finally:
            if _f:
                funcholder.deinit()

        logging.debug("Imported Entity Type {}, with {} variants, {} functions and {} item types loaded.".format(name, len(variants), len(functions), len(item_types)))

        return (EntityType(name, id, base, variants, functions, systems, default), item_types)
