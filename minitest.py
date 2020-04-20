import smadventure.engine, trio



WORLD = smadventure.engine.XMLGameLoader().load_world('mushworld.xml')

def format_offs(num):
    if num > 0:
        return '+' + str(num)

    return str(num)

def main_test():
    init_size = len(WORLD.entities)
    trio.run(WORLD.tick)
    next_size = len(WORLD.entities)
    return init_size, next_size


if __name__ == '__main__':
    def do_test():
        l_a, l_b = main_test()
        print('{} -> {} ({})'.format(l_a, l_b, format_offs(l_b - l_a)))

    do_test()
