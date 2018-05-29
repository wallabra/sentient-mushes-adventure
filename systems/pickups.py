import random

def pickups(event, entity):
    if event == 'player:pickup' and entity['isPlayer'] and entity['eventArg'] and len(entity.world.find_place(entity.place)['items']) > 0:
        iname = entity['eventArg']
        item = entity.world.find_item(iname)
        num = entity.world.find_place(entity.place)['items'][iname]
        
        