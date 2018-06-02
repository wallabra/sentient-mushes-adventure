import json
import lxml
import embedcode
import time
import logging
import namegen
import importlib
import random
import atexit
import yaml
import threading

from lxml import etree
from queue import Queue, Empty


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
        
    def instantiate(self, world, place, variant, extra_attr={}):
        """Creates a default entity string and returns it."""
        attr = self.default_attr
        
        for k, v in self.variants[variant]['default'].items():
            attr[k] = v
        
        for k, v in extra_attr.items():
            attr[k] = v
        
        id = ''.join([random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(24)])
        
        while world.from_id(id):
            id = ''.join([random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(24)])

        return "{}#{}#{}#{}#{}#{}".format(id, self.id, namegen.generate_name(random.randint(3, 10)), place, variant, json.dumps(attr))
        
    def call(self, func, entity, *args):
        return self.functions[func](entity, *args)

class LoadedEntity(object):
    def __init__(self, world, index, s):
        self.world = world
        self.index = index
        self.id = s.split("#")[0]
        self.type = world.etypes[s.split("#")[1]]
        self.name = s.split('#')[2]
        self.place = s.split("#")[3]
        self.variant = self.type.variants[s.split("#")[4]]
        self.attr = json.loads(s.split("#")[5])
        
        world.all_loaded_entities.append(self)
        
    def set_variant(self, variant):
        for k, v in self.variant['default'].items():
            if k in self.attr and self.attr[k] == v:
                self.attr.pop(k)
                
        self.variant = self.type.variants[variant]
        
        for k, v in self.variant['default'].items():
            if k not in self.attr:
                self.attr[k] = v
        
    def __setitem__(self, key, val):
        self.attr[key] = val
        self.update()
     
    def pointer(self, key):
        if not self[key]:
            return None
    
        return self.world.from_id(self[key])
             
    def pointer_list(self, key):
        for a in self[key]:
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
        world.add_entity(e)
        
        if return_loaded:
            return world.from_id(e)
            
        else:
            return e.split('#')[0]
     
    def of(self, type):
        return self.etype.id == type
     
    def set_name(self, name):
        self.name = name
        self.update()
        
    def update(self):
        try:
            self.world.set_with_id(self.id, "{}#{}#{}#{}#{}#{}".format(self.id, self.type.id, self.name, self.place, self.variant['id'], json.dumps(self.attr)))
            
        except TypeError as e:
            bad = {}
            
            for k, v in self.attr.items():
                try:
                    json.dumps(v)
                    
                except TypeError:
                    bad[k] = v
                    
            if len(bad) > 0:
                print("Bad unserializable stuff found in {}: {}".format(self, ", ".join("{} ({})".format(k, repr(v)) for k, v in bad.items())))
        
            raise
            
        self.world.update_loaded_entities()
        
    def __worldlist_unload(self):
        for i, e in enumerate(self.world.all_loaded_entities):
            if e is self:
                self.world.all_loaded_entities.pop(i)
        
    def now(self):
        n = self.world.from_id(self.id)
        self.index = n.index
        self.id = n.id
        self.type = n.type
        self.name = n.name
        self.place = n.place
        self.variant = n.variant
        self.attr = n.attr
        n.__worldlist_unload()
        
    def __getitem__(self, key):
        a = self.attr.get(key)
        b = (a if a is not None else self.variant['attr'].get(key))
            
        return (b if b is not None else (True if key in self.variant['flags'] else None))
    
    def call(self, func, *args):
        logging.debug("ENTITY CALL: {}.{}({})".format(self.type.id, func, self.name))
        return self.type.call(func, self, *args)
        
    def event(self, evt, *args):
        for s in self.type.systems:
            s(evt, self, *args)
            
        for s in self.variant['systems']:
            s(evt, self, *args)
            
        for s in self.world.global_systems:
            s(evt, self, *args)
    
    def set_place(self, p):
        self.place = p
        self.update()
        
    def despawn(self):
        self.now()
        self.world.entities.pop(self.index)
        self.__worldlist_unload()
            
    def print_attr(self):
        for k, v in self.attr.items():
            print('  * {} -> {}'.format(k, v))
            
    def __str__(self):
        return "{} the {} from {}".format(self.name, self.variant['name'], self.place)
        
class GameWorld(object):
    def __init__(self, etypes=(), paths=(), places=(), entities=(), item_types=(), beginning=None):
        self.etypes = dict(etypes)
        self.paths = list(paths)
        self.places = list(places)
        self.entities = list(entities)
        self.item_types = list(item_types)
        self.beginning = beginning
        
        self.message_queue = Queue()
        self.broadcast_channels = []
        self.global_systems = []
        
        self.all_loaded_entities = []
        
        t = threading.Thread(name="Game Broadcast Loop", target=self._broadcast_loop)
        t.start()
    
    def update_loaded_entities(self):
        for l in self.all_loaded_entities:
            l.now()
    
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
        
    def add_broadcast_channel(self, level, *channels):
        for c in channels:
            def _exit():
                c('\n')
                
            atexit.register(_exit)
            setattr(c, '_level', level)
    
        self.broadcast_channels.extend(channels)
        
    def broadcast(self, level, *message, place=None):
        self.message_queue.put((level, message, place))
    
    def _broadcast_loop(self):
        while True:
            try:
                [level, message, place] = self.message_queue.get_nowait()
            
            except Empty:
                time.sleep(1)
                continue
                
            m = ""
            
            for node in message:
                m += str(node)
        
            can_wait = False
        
            for b in self.broadcast_channels:
                if not b._level or level >= b._level:
                    b(m, place, level)
                    can_wait = True
        
            if can_wait:
                time.sleep(0.65)
        
    def tick(self):
        self.all_loaded_entities = []
        
        for i, e in enumerate(self.entities):
            en = LoadedEntity(self, i, e)

            if 'tick' in en.type.functions:
                en.call('tick')
                
            for s in en.type.systems:
                s('tick', en)
                
            self.all_loaded_entities = []
        
    def add_entity(self, e):
        self.entities.append(e)
        
        funcs = self.etypes[e.split('#')[1]].functions
        
        if 'init' in funcs:
            funcs['init'](self.from_id(e))
        
    def find_item(self, name):
        for i in self.item_types:
            if i['name'] == name:
                return i
                
        return None
        
    def find_place(self, name):
        for p in self.places:
            if p['name'] == name:
                return p
                
        return None
        
    def from_name(self, name):
        for i, e in enumerate(self.entities):
            if e.split("#")[2] == name:
                return LoadedEntity(self, i, e)
                
        return None
        
    def from_id(self, uid):
        for i, e in enumerate(self.entities):
            if e.split("#")[0] == uid.split('#')[0]:
                return LoadedEntity(self, i, e)
                
        return None
        
    def from_index(self, ind):
        return self.from_id(self.entities[ind].split('#')[0])
        
    def set_with_id(self, id, val):
        e = self.from_id(id)
        
        if e:
            self.entities[e.index] = val
            return True
        
        return False
        
    def all_in_place(self, cplace):
        res = []
        
        for i, e in enumerate(self.entities):
            le = LoadedEntity(self, i, e)
        
            if le.place == cplace:
                res.append(le)
                
        return res
        
    def item_type(self, name):
        for it in self.item_types:
            if it['name'] == name:
                return it
               
        return None
        
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
        
        for el in xworld.getroot():
            if el.tag == 'etypes':
                for t in el:
                    if t.tag == 'etype':
                        (e, items) = self.load_entity_type(world, t.get('filename'))
                        world.etypes[e.id] = e
                        world.item_types.extend(items)
                    
        for el in xworld.getroot():
            if el.tag == "places":
                for p in el:
                    if p.tag == "place":
                        i = {}
                    
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
                    
                        world.places.append({
                            'name': p.get('name'),
                            'id': p.get('id'),
                            'items': i
                        })
                
            elif el.tag == "paths":
                for p in el:
                    if p.tag == "path":
                        world.paths.append(set(p.get('ends').split(';')))
                        
        world.entities = random.sample(world.entities, len(world.entities))
        return world
        
    def load_entity_type(self, world, filename):
        """Returns an EntityType instance.
        
        The filename is one of the entity type filenames
        described by the world. EntityType must be called
        to create the instance after processing the file's
        content."""
        
        try:
            item_types = [] # Entity's item definitions
            
            etype = etree.parse(open(filename))
            name = etype.getroot().get('name')
            id = etype.getroot().get('id')
            
            functions = {}
            base = { 'attr': {}, 'flags': set() }
            variants = {}
            systems = []
            default = {}
            
            def import_attr(el, level=1):
                imported = etree.parse(open(el.get('href')))
                                
                for a in imported.getroot():
                    if a.tag == "attribute":
                        default[a.get('key')] = eval(a.get('value'))
                        
                    elif a.tag == "declare":
                        default[a.get('key')] = None
                        
                    elif a.tag == "import":
                        # print("Importing attribute library '{}' from '{}'".format(a.get('name'), imported.getroot().get('name')))
                        import_attr(a, level + 1)
                
                    elif a.tag == "flag":
                        base['flags'].add(a.get('name'))
                        
                    elif a.tag == "static" and a.get('name') not in base['attr']:
                        base['attr'][a.get('name')] = eval(a.get('value'))
                        
                    elif a.tag == "function":
                        if (a.get('name') not in functions) or (level <= getattr(functions[a.get('name')], '__priority', 0)):
                            allfunc = tuple(funcholder.quick("{}_a{}_{}".format(id, level, a.get('name')), a.text).values())
                            fncs = filter(lambda f: f.__name__ == a.get('name'), allfunc)
                            
                            try:
                                f = tuple(fncs)[-1]
                                setattr(f, '__priority', level)
                                functions[a.get('name')] = f
                                
                            except IndexError:
                                print("No matching function for '{}'!".format(a.get('name')))
                                raise
                        
                    elif a.tag == 'item':
                        name = a.get('name')
                        
                        if name in map(lambda item: item['name'], world.item_types):
                            continue
                    
                        i = {
                            'name': name,
                            'functions': {},
                            'attr': {},
                            'flags': set()
                        }
                        
                        for char in a:
                            if char.tag == 'function':
                                i['functions'][char.get('name')] = funcholder.quick('{}-{}'.format(a.get('name'), char.get('name')), char.text)
                                
                            elif char.tag == 'attribute':
                                val = char.get('value')
                                
                                if val:
                                    i['attr'][char.get('key')] = eval(val)
                                    
                                else:
                                    i['attr'][char.get('key')] = None
                                    
                            elif char.tag == 'flag':
                                i['flags'].add(char.get('name'))
                        
                        item_types.append(i)
            
            funcholder = embedcode.CodeHolder()
            
            for sub in etype.getroot():
                if sub.tag == "functions":
                    for f in sub:
                        if f.tag == "function":
                            fncs = filter(lambda g: g.__name__ == f.get('name'), list(funcholder.quick("{}-{}".format(id, f.get('name')), f.text).values()))
                            
                            try:
                                functions[f.get('name')] = tuple(fncs)[-1]
                                
                            except IndexError:
                                print("No matching function for '{}'!".format(f.get('name')))
                                raise
                        
                elif sub.tag == "base":
                    for a in sub:
                        if a.tag == "attr":
                            base['attr'][a.get('name')] = eval(a.get('value'))
                            
                        elif a.tag == "flag":
                            base['flags'].add(a.get('name'))
                            
                elif sub.tag == "systems":
                    for sys in sub:
                        if sys.tag == "system":
                            fncs = filter(lambda f: f.__name__ == sys.get('name'), list(funcholder.quick("{}-{}".format(id, sys.get('name')), open(sys.get('href')).read()).values()))
                            
                            try:
                                systems.append(tuple(fncs)[-1])
                                
                            except IndexError:
                                print("No matching function for '{}' while parsing Entity Type '{}'!".format(sys.get('name'), id))
                                raise
                            
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
                                    i['functions'][char.get('name')] = tuple(filter(lambda f: f.__name__ == char.get('name'), tuple(funcholder.quick('{}-{}'.format(item.get('name'), char.get('name')), char.text).values())))[-1]
                                    
                                elif char.tag == 'attribute':
                                    val = char.get('value')
                                     
                                    if val:
                                        i['attr'][char.get('key')] = eval(val)
                                        
                                    else:
                                        i['attr'][char.get('key')] = None
                        
                                elif char.tag == 'flag':
                                    i['flags'].add(char.get('key'))
                            
                            item_types.append(i)
                            
                elif sub.tag == "variants":
                    for va in sub:
                        v = { 'name': va.get('name'), 'id': va.get('id'), 'attr': {}, 'flags': set(), 'default': {}, 'systems': [] }
                        
                        for a in va:
                            if a.tag == "attr":
                                v['attr'][a.get('name')] = eval(a.get('value'))
                                
                            elif a.tag == "flag":
                                v['flags'].add(a.get('name'))

                            elif a.tag == "default":
                                v['default'][a.get('key')] = eval(a.get('value'))
                                
                            elif a.tag == "system":
                                fncs = filter(lambda f: f.__name__ == sys.get('name'), list(funcholder.quick("{}-{}".format(id, sys.get('name')), open(sys.get('href')).read()).values()))
                            
                                try:
                                    v.systems.append(tuple(fncs)[-1])
                                    
                                except IndexError:
                                    print("No matching function for '{}'!".format(sys.get('name')))
                                    raise
                                
                        variants[va.get('id')] = v
                        
        finally:                
            funcholder.deinit()
        
        return (EntityType(name, id, base, variants, functions, systems, default), item_types)