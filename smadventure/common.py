import math


def plural(name: str, amount: int = 2):
    if amount == 1:
        return name

    elif name.endswith('us') or name.endswith('is'):
        return name[:-2] + 'i'

    elif name.endswith('ff'):
        return name[:-2] + 'ves'
        
    elif name.endswith('s'):
        return name + 'es'

    else:
        return name + 's'

def size_cm(centimetres: float):
    if centimetres < 100:
        metric = '{:.2f}cm'.format(centimetres)

    else:
        metres = math.floor(centimetres / 100)
        metric = '{}m{}cm'.format(metres, int(centimetres - metres * 100))

    inches = centimetres / 2.54

    if inches < 12:
        imperial = '{:.2f}"'.format(inches)

    else:
        feet = math.floor(inches / 12)
        imperial = '{}\'{}"'.format(feet, int(inches - feet * 12))

    return '{} ({})'.format(metric, imperial)