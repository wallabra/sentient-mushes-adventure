
def fly(entity):
    if entity['destination'] == entity.place:
        return False

    i = 3

    while entity['destination'] != entity.place and i > 0:
        if not entity.call('pathmove', entity['destination']):
            return False

        i -= 1

    return i > 0
