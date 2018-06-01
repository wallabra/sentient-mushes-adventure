import random

def drops(event, entity):
    if event == 'death' and entity['drops'] and entity['instigator']:
        if entity['instigator'] and entity.world.from_id(entity['instigator'])['isPlayer']:
            inv = entity.world.from_id(entity['instigator'])['inventory']
        
        print("Dropping all items from: " + str(entity))
        
        for item, amount in entity['drops'].items():
            if type(amount) in (tuple, list):
                amount = random.randint(amount[0], amount[1])
        
            if item in map(lambda x: x['name'], entity.world.item_types):
                if entity['instigator'] and entity.world.from_id(entity['instigator'])['isPlayer']:
                    if item in inv:
                        inv[item] += amount
                        
                    else:
                        inv[item] = amount
                        
                else:
                    if item in entity.world.find_place(entity.place)['items']:
                        entity.world.find_place(entity.place)['items'][item] += amount
                        
                    else:
                        entity.world.find_place(entity.place)['items'][item] = amount
                
            else:
                print("Warning: Item {} dropped by a {} not found in world's item definitions!".format(
                    item,
                    entity.variant['name']
                ))
                
        for item, amount in entity['inventory'].items():
            if item in map(lambda x: x['name'], entity.world.item_types):
                if 'alwaysDrop' in entity.world.find_item(item)['flags']: 
                    if entity['instigator']:    
                        if item in inv:
                            inv[item] += amount
                            
                        else:
                            inv[item] = amount
                    
                    else:
                        if item in entity.world.find_place(entity.place)['items']:
                            entity.world.find_place(entity.place)['items'][item] += amount
                            
                        else:
                            entity.world.find_place(entity.place)['items'][item] = amount
                
            else:
                print("Warning: Item {} dropped by a {} not found in world's item definitions!".format(
                    item,
                    entity.variant['name']
                ))
                
        if entity['instigator'] and entity.world.from_id(entity['instigator'])['isPlayer']:
            entity.world.from_id(entity['instigator'])['inventory'] = inv