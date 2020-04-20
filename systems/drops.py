import random
import logging

def drops(event, entity):
    if event == 'death' and entity['drops']:
        if entity['instigator'] and entity.world.from_id(entity['instigator'])['isPlayer']:
            inv = entity.world.from_id(entity['instigator'])['inventory']

        else:
            inv = entity.world.find_place(entity.place)['items']

        logging.debug("Dropping all items from: %s", str(entity))

        for item, amount in entity['drops'].items():
            if isinstance(amount, (tuple, list)):
                amount = random.randint(amount[0], amount[1])

            if item in entity.world.item_types:
                if 'neverDrop' not in entity.world.find_item(item)['flags']:
                    if item in inv:
                        inv[item] += amount

                    else:
                        inv[item] = amount

            else:
                logging.warn("Warning: Item {} dropped by a {} not found in world's item definitions!".format(
                    item,
                    entity.variant['name']
                ))

        for item, amount in entity['inventory'].items():
            if item in map(lambda x: x['name'], entity.world.item_types):
                if 'alwaysDrop' in entity.world.find_item(item)['flags']:
                    if 'neverDrop' not in entity.world.find_item(item)['flags']:
                        if item in inv:
                            inv[item] += amount

                        else:
                            inv[item] = amount

            else:
                print("Warning: Item {} dropped by a {} not found in world's item definitions!".format(
                    item,
                    entity.variant['name']
                ))
