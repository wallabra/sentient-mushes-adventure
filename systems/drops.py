import random

def drop_system(event, index, entity):
    if event == 'death' and entity['drops'] and entity['killer']:
        for item, amount in entity['drops'].items():
            if item in map(lambda x: x['name'], entity.world.item_types):
                inv = entity.world.load_entity_index(entity['killer'])['inventory']
                inv[item] += random.randint(amount[0], amount[1]) # amount is a tuple (min, max)
                entity.world.load_entity_index(entity['killer'])['inventory'] = inv
                
            else:
                print("Warning: Item {} dropped by a {} not found in world's item definitions!".format(
                    item,
                    entity.variant['name']
                ))