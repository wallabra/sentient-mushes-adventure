import random

def drop_system(event, entity):
    if event == 'death' and entity['drops'] and entity['instigator']:
        inv = entity.world.from_index(entity['instigator'])['inventory']
        
        for item, amount in entity['drops'].items():
            if item in map(lambda x: x['name'], entity.world.item_types):
                inv[item] += random.randint(amount[0], amount[1]) # amount is a tuple (min, max)
                
            else:
                print("Warning: Item {} dropped by a {} not found in world's item definitions!".format(
                    item,
                    entity.variant['name']
                ))
                
        entity.world.from_index(entity['instigator'])['inventory'] = inv