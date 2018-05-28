import json
import lxml
import tempfile
import namegen
import random

# from irc.bot import SimpleIRCBot
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

    def __init__(self, name, id=None, base_attributes=(), variants=(), functions=()):
        self.name = name
        self.id = id or idnum
        self.base_attributes = dict(base_attributes)
        self.variants = dict(variants)
        self.functions = dict(functions)
        
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
        
    def instantiate(self, place, variant):
        """Creates an entity string and returns it."""
        return "{}#{}#{}#{}".format(self.id, "{} the {}".format(namegen.generate_name(random.randint(4, 12)), self.variants[variant]['name']), place, variant)
        
    def call(self, func, index, entity, world):
        return self.functions[func](index, entity, world)

class LoadedEntity(object):
    def __init__(self, world, s):
        self.type = world.etypes[s.split("#")[0]]
        self.name = s.split('#')[1]
        self.place = s.split("#")[2]
        self.variant = self.type.variants[s.split("#")[3]]
        
class GameWorld(object):
    def __init__(self, etypes, paths, places, entities):
        self.etypes = dict(etypes)
        self.paths = list(paths)
        self.places = list(places)
        self.entities = list(entities)
        
    def tick(self):
        for i, e in enumerate(self.entities):
            en = LoadedEntity(self, e)
            et = self.etypes[en.type]

            if 'tick' in self.etypes.functions:
                self.etypes.call('tick', i, e, self)
        
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
        etypes = {}
        paths = []
        places = []
        entities = []
        
        for el in xworld.iter():
            if el.tag == 'etypes':
                for t in el:
                    if t.tag == 'etype':
                        e = self.load_entity_type(t.get('filename'))
                        etypes[e.id] = e
                    
        for el in xworld.iter():
            if el.tag == "places":
                for p in el:
                    for sub in p:
                        if sub.tag == "flock":
                            if sub.get('type') in etypes:
                                amount = sub.get('amount')
                                
                                if '-' in amount:
                                    amount = random.randint(int(amount.split('-')[0]), int(amount.split('-')[1]))
                                    
                                else:
                                    amount = int(amount)
                            
                                for _ in range(amount):
                                    entities.append(etypes[sub.get('type')].instantiate(p.get('name'), (random.choice(sub.get('variant').split(';')) if sub.get('variant') != '*' else random.choice(tuple(etypes[sub.get('type')].variants.keys())))))
                                    
                        elif sub.tag == "entity":
                            if sub.get('type') in etypes:
                                entities.append(etypes[sub.get('type')].instantiate(p.get('name'), (random.choice(sub.get('variant').split(';')) if sub.get('variant') != '*' else random.choice(tuple(etypes[sub.get('type')].variants.keys())))))
                
                    places.append(p.get('name'))
                
            elif el.tag == "paths":
                for p in el:
                    if p.tag == "path":
                        paths.append(set(p.get('ends').split(';')))
                
        return GameWorld(etypes, paths, places, entities)
        
    def load_entity_type(self, filename):
        """Returns an EntityType instance.
        
        The filename is one of the entity type filenames
        described by the world. EntityType must be called
        to create the instance after processing the file's
        content."""
        
        try:
            etype = etree.parse(open(filename))
            name = etype.getroot().get('name')
            id = etype.getroot().get('id')
            
            functions = {}
            base = { 'attr': {}, 'flags': set() }
            variants = {}
            
            funcholder = tempfile.CodeHolder()
            
            for sub in etype.iter():
                if sub.tag == "functions":
                    for f in sub:
                        fncs = list(funcholder.quick("{}-{}".format(id, f.get('name')), f.text).values())
                        functions[f.get('name')] = fncs[-1]
                        
                elif sub.tag == "base":
                    for a in sub:
                        if a.tag == "attr":
                            base['attr'][a.get('name')] = a.get('value')
                            
                        elif a.tag == "flag":
                            base['flags'].add(a.get('name'))
                            
                elif sub.tag == "variants":
                    for va in sub:
                        v = { 'attr': {}, 'flags': set() }
                        
                        for a in va:
                            if a.tag == "attr":
                                v['attr'][a.get('name')] = a.get('value')
                                
                            elif a.tag == "flag":
                                v['flags'].add(a.get('name'))
                                
                        v['name'] = va.get('name')
                        variants[va.get('id')] = v
                        
        finally:
            funcholder.deinit()
        
        return EntityType(name, id, base, variants, functions)