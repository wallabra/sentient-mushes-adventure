import importlib
import textwrap
import os

class CodeHolder(object):
    def __init__(self):
        self.files = set()
        
    def __setitem__(self, key, code):
        f = open("tmp_{}.py".format(key), 'wb')
        f.write(textwrap.dedent(code).encode('utf-8'))
        
        self.files.add(key)
        
        f.close()
        
    def __getitem__(self, key):
        mod = importlib.import_module("tmp_" + key)
        
        funcs = list(filter(lambda x: hasattr(x, '__call__') and hasattr(x, '__name__'), map(lambda x: getattr(mod, x), dir(mod))))
        res = {}
        
        for f in funcs:
            res[f.__name__] = f

        return res
                
    def quick(self, key, code):
        self[key] = code
        # print(open("tmp_{}.py".format(key)).read())
        return self[key]

    def deinit(self):
        for k in self.files:
            os.unlink("tmp_{}.py".format(k))