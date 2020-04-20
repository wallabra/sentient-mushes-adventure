import textwrap



class CodeHolder:
    def __init__(self):
        self.files = {}
        self.cache = {}

    def set(self, key, code, override: bool = False, linepad: int = 0):
        if key in self.files and not override:
            return False

        if override and key in self.cache:
            assert key in self.files
            del self.cache[key]

        self.files[key] = b'\n' * linepad + textwrap.dedent(code).strip('\n').encode('utf-8')

        return True

    def __setitem__(self, key, code):
        return self.set(key, code)

    def __getitem__(self, key):
        return self.get(key)

    def get(self, key, filename: str = None):
        if key in self.cache:
            return self.cache[key]

        # Get symbols created in code embed
        from . import namegen

        mod = dict(globals())
        mod['namegen'] = namegen

        pre = dict(mod)

        # print('Loading code fragment: {}'.format(key))
        compiled = compile(self.files[key], filename, 'exec')
        exec(compiled, mod)

        # Fetch all functions
        res = {k: v for k, v in mod.items() if hasattr(v, '__call__') and hasattr(v, '__name__') if k not in pre or pre[k] != v}

        for v in res.values():
            v.__lookup_name__ = v.__name__
            v.__name__ = key.replace(' ', '_').replace('-', '.')

        self.cache[key] = res
        return res

    def __delitem__(self, key):
        del self.files[key]

    def quick(self, key, code, linepad: int = 0, filename: str = None):
        self.set(key, code, linepad=linepad)
        return self.get(key, filename)

    def deinit(self):
        self.files = {}
