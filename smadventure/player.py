from . import engine



class PlayerInterface(object):
    def __init__(self, entity, name):
        self.entity = entity
        
        entity.set_name(name)

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

    def move(self, place):
        return self.entity.call('player_move', self, place)

    def attack_name(self, other_name):
        return self.entity.call('player_attack', self, self.entity.world.from_name(other_name))

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
    def join(self, world, name, place, type, variant):
        entity = world.etypes[type].instantiate(world, place, variant, name)
        world.add_entity(entity)
        entity = world.from_ent(entity)

        return PlayerInterface(entity, name)
