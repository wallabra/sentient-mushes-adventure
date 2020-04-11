import importlib
import textwrap
import os

class CodeHolder(object):
    def __init__(self):
        self.files = set()
        self.cache = {}
        
    def __setitem__(self, key, code, override=False):
        if key in self.files and not override:
            return False
    
        f = open("tmp_{}.py".format(key), 'wb')
        f.write(textwrap.dedent(code).strip('\n').encode('utf-8'))
        
        self.files.add(key)
        
        f.close()
        
        if key in self.cache:
            self.cache.pop(key)
        
        return True
        
    def __getitem__(self, key):
        if key in self.cache:
            return self.cache[key]
    
        mod = importlib.import_module("tmp_" + key)
        
        funcs = list(filter(lambda x: hasattr(x, '__call__') and hasattr(x, '__name__'), map(lambda x: getattr(mod, x), dir(mod))))
        res = {}
        
        for f in funcs:
            res[f.__name__] = f
            
        self.cache[key] = res
        return res
                
    def quick(self, key, code):
        self[key] = code
        # print(open("tmp_{}.py".format(key)).read())
        return self[key]

    def deinit(self):
        for k in self.files:
            os.unlink("tmp_{}.py".format(k))