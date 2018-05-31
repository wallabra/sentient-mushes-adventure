import random

def pinata_drops(event, entity):
    if event == 'death' and entity['inventory']:
        for item, amount in entity['inventory'].items():
            if item in map(lambda x: x['name'], entity.world.item_types):
                if not entity.world.find_item(item)['flags']['alwaysDrop']:
                    if item in entity.world.find_place(entity.place)['items']:
                        entity.world.find_place(entity.place)['items'][item] += amount
                        
                    else:
                        entity.world.find_place(entity.place)['items'][item] = amount
                
            else:
                print("Warning: Item {} dropped by a {} not found in world's item definitions!".format(
                    item,
                    entity.variant['name']
                ))