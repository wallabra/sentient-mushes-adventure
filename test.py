import engine

loader = engine.XMLGameLoader()
world = loader.load_world('mushworld.xml')

log = open('event.log', 'a')

def console_channel(msg):
    print(msg)

def log_channel(msg):
    log.write(msg + '\n')
    
world.add_broadcast_channel(-1, console_channel)
world.add_broadcast_channel(-2, log_channel)

if __name__ == "__main__":
    print("There are {} entities loaded.\n".format(len(world.entities)))

    for i, e in enumerate(world.entities):
        le = engine.LoadedEntity(world, i, e)
        print("[{}] {} the {} from {}".format(le.id, le.name, le.variant['name'], le.place))
        
        for k, v in le.attr.items():
            print("  * {}: {}".format(k, v))
            
        print()