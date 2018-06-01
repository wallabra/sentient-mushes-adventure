import engine

class PlayerInterface(object):
    def __init__(self, channels, entity, name, global_cast=False):
        self.entity = entity
        entity.set_name(name)
        
        self.channels = channels
        
        if global_cast:
            entity.world.add_broadcast_channel(2, *self.channels)
        
    def print_out(self, *message, place=False): # False = automatic, None = none indeed
        m = ""
    
        if place is False:
            place = self.entity.place
    
        for node in message:
            if isinstance(node, engine.LoadedEntity):
                m += "{} the {} from {}".format(node.name, node.variant['name'], node.place)
                
            elif isinstance(node, engine.EntityType):
                m += node.name
                
            else:
                m += str(node)
            
        #print(m)
            
        # no need to check for levels.
        for c in self.channels:
            c(m, place, 5)
        
    def move(self, place):
        return self.entity.call('player_move', self, place)
        
    def attack_name(self, other_name):
        return self.entity.call('player_attack', self.entity.world.from_name(other_name))
        
    def attack(self, other):
        return self.entity.call('player_attack', self, other)
        
    def craft(self, item, amount):
        return self.entity.call('craft', self, item, amount)
        
    def pick_up(self, amount=1, item=None):
        return self.entity.call('pick_up', self, amount, item)
        
    def infect(self, other):
        return self.entity.call('infect', self, other)
        
    def wield(self, item=None):
        return self.entity.call('wield', self, item)
        
    @classmethod
    def join(self, channels, world, name, place, type, variant):
        entity = world.etypes[type].instantiate(world, place, variant)
        world.entities.append(entity)
        entity = world.from_id(entity)

        return PlayerInterface(channels, entity, name)