import engine

loader = engine.XMLGameLoader()
world = loader.load_world('mushworld.xml')

for i, e in enumerate(world.entities):
    le = engine.LoadedEntity(world, i, e)
    print("{} the {} from {}".format(le.name, le.variant['name'], le.place))