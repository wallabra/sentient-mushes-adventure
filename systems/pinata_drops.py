import logging


def pinata_drops(event, entity):
    if event == 'death' and entity['inventory']:
        if entity['instigator'] and entity.world.from_id(entity['instigator'])['isPlayer']:
            inv = entity.world.from_id(entity['instigator'])['inventory']

        else:
            inv = entity.world.find_place(entity.place)['items']

        for item, amount in entity['inventory'].items():
            if item in map(lambda x: x['name'], entity.world.item_types):
                if not entity.world.find_item(item)['flags']['neverDrop']:
                    if item in inv:
                        inv[item] += amount

                    else:
                        inv[item] = amount

            else:
                logging.warn("Warning: Item {} dropped by {} not found in world's item definitions!".format(
                    item,
                    str(entity)
                ))
