
def slash(entity):
    if entity.attr['target'] is None:
        return

    entity.call('attack', entity.world.from_id(entity['target']), __import__('random').uniform(30, 50))
