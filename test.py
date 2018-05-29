import engine

loader = engine.XMLGameLoader()
world = loader.load_world('mushworld.xml')

print("There are {} entities loaded.\n".format(len(world.entities)))

for i, e in enumerate(world.entities):
    le = engine.LoadedEntity(world, i, e)
    print("[{}] {} the {} from {}".format(le.id, le.name, le.variant['name'], le.place))
    
    for k, v in le.attr.items():
        print("  * {}: {}".format(k, v))
        
    print()