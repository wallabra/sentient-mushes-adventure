import engine

loader = engine.XMLGameLoader()
world = loader.load_world('mushworld.xml')

for e in world.entities:
    le = engine.LoadedEntity(world, e)
    print("{} from {}".format(le.name, le.place))