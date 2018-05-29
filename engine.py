import json
import lxml
import embedcode
import namegen
import importlib
import random

from lxml import etree


idnum = 0 # The default ID counter.

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
        
    def instantiate(self, world, place, variant):
        """Creates a default entity string and returns it."""
        attr = self.default_attr
        
        for k, v in self.variants[variant]['default'].items():
            attr[k] = v
        
        id = ''.join([random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(24)])
        
        while world.from_id(id):
            id = ''.join([random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(24)])
        
        return "{}#{}#{}#{}#{}#{}".format(id, self.id, namegen.generate_name(random.randint(4, 9)), place, variant, json.dumps(attr))
        
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
        
    def __setitem__(self, key, val):
        self.attr[key] = val
        self.world.entities[self.index] = "{}#{}#{}#{}#{}".format(self.type.id, self.name, self.place, self.variant, json.dumps(self.attr))
        
    def __getitem__(self, key):
        return self.attr.get(key, None) or self.variant['attr'].get(key, None)
    
    def call(self, func, *args):
        return self.type.call(func, self, *args)
        
    def event(self, evt):
        for s in self.type.systems:
            s(evt, self)
            
    def __str__(self):
        return "{} the {} from {}".format(self.name, self.variant['name'], self.place)
        
    def __format__(self):
        return str(self)
        
class GameWorld(object):
    def __init__(self, etypes=(), paths=(), places=(), entities=(), item_types=()):
        self.etypes = dict(etypes)
        self.paths = list(paths)
        self.places = list(places)
        self.entities = list(entities)
        self.item_types = list(item_types)
        
        self.broadcast_channels = []
        
    def add_broadcast_channel(self, *channels):
        self.broadcast_channels.extend(channels)
        
    def broadcast(self, *message):
        m = ""
        
        for node in message:
            if isinstance(node, LoadedEntity):
                m += "{} the {} from {}".format(node.name, node.variant['name'], node.place)
                
            elif isinstance(node, EntityType):
                m += node.name
                
            else:
                m += str(node)
    
        for b in self.broadcast_channels:
            b(m)
        
    def tick(self):
        for i, e in enumerate(self.entities):
            en = LoadedEntity(self, i, e)
            et = self.etypes[en.type]

            if 'tick' in et.functions:
                en.call('tick')
                
            for s in et.systems:
                s('tick', en)
        
    def from_id(self, uid):
        for i, e in enumerate(self.entities):
            if e.split("#")[0] == uid:
                return LoadedEntity(self, i, e)
                
        return None
        
    def item_type(self, name):
        for it in self.item_types:
            if it.name == name:
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
        
        world = GameWorld()
        
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
                        for sub in p:
                            if sub.tag == "flock":
                                if sub.get('type') in world.etypes:
                                    amount = sub.get('amount')
                                    
                                    if '-' in amount:
                                        amount = random.randint(int(amount.split('-')[0]), int(amount.split('-')[1]))
                                        
                                    else:
                                        amount = int(amount)
                                
                                    for _ in range(amount):
                                        world.entities.append(world.etypes[sub.get('type')].instantiate(world, p.get('name'), (random.choice(sub.get('variant').split(';')) if sub.get('variant') != '*' else random.choice(tuple(world.etypes[sub.get('type')].variants.keys())))))
                                        
                            elif sub.tag == "entity":
                                if sub.get('type') in world.etypes:
                                    world.entities.append(world.etypes[sub.get('type')].instantiate(world, p.get('name'), (random.choice(sub.get('variant').split(';')) if sub.get('variant') != '*' else random.choice(tuple(world.etypes[sub.get('type')].variants.keys())))))
                    
                        world.places.append(p.get('name'))
                
            elif el.tag == "paths":
                for p in el:
                    if p.tag == "path":
                        world.paths.append(set(p.get('ends').split(';')))
                        
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
            
            def import_attr(el):
                imported = etree.parse(open(el.get('href')))
                                
                for a in imported.getroot():
                    if a.tag == "attribute":
                        default[a.get('key')] = eval(a.get('value'))
                        
                    elif a.tag == "declare":
                        default[a.get('key')] = None
                        
                    elif a.tag == "import":
                        import_attr(el)
                
                    elif a.tag == "flag":
                        base['flags'].add(a.get('name'))
                        
                    elif a.tag == "static":
                        base['attr'][a.get('name')] = eval(a.get('value'))
                        
                    elif a.tag == "function":
                        fncs = list(funcholder.quick("{}-{}".format(id, a.get('name')), a.text).values())
                        functions[a.get('name')] = fncs[-1]
                        
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
                        fncs = list(funcholder.quick("{}-{}".format(id, f.get('name')), f.text).values())
                        functions[f.get('name')] = fncs[-1]
                        
                elif sub.tag == "base":
                    for a in sub:
                        if a.tag == "attr":
                            base['attr'][a.get('name')] = eval(a.get('value'))
                            
                        elif a.tag == "flag":
                            base['flags'].add(a.get('name'))
                            
                elif sub.tag == "systems":
                    for sys in sub:
                        if sys.tag == "system":
                            fncs = list(funcholder.quick("{}-{}".format(id, sys.get('name')), open(sys.get('href')).read()))
                            systems.append(fncs[-1])
                            
                elif sub.tag == "default":
                    for att in sub:
                        if att.tag == "import":
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
                                    i['functions'][char.get('name')] = tuple(funcholder.quick('{}-{}'.format(item.get('name'), char.get('name')), char.text).values())[-1]
                                    
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
                        v = { 'name': va.get('name'), 'id': va.get('id'), 'attr': {}, 'flags': set(), 'default': {} }
                        
                        for a in va:
                            if a.tag == "attr":
                                v['attr'][a.get('name')] = eval(a.get('value'))
                                
                            elif a.tag == "flag":
                                v['flags'].add(a.get('name'))

                            elif a.tag == "default":
                                v['default'][a.get('key')] = eval(a.get('value'))
                                
                        variants[va.get('id')] = v
                        
        finally:
            funcholder.deinit()
        
        return (EntityType(name, id, base, variants, functions, systems, default), item_types)