
import random

def tick(entity):
    entity.call('creature_tick')

    if random.random() <= 0.1: 
        # wander
        possib = set()

        for p in entity.world.paths:
            if entity.place in p:
                possib |= p

        possib -= {entity.place}

        if len(possib) > 0:
            p = random.choice(tuple(possib))
            entity.world.broadcast(0, entity, " wanders to ", p, ".", place=p)
            entity.call('move', p)
