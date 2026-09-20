#TODO documentation pls

class GenFile:
    def __init__(self, f, is_load=False):
        """I think basically for cursor.copy_from() the is_current column needs to be explicit on loads but not on maintenance?"""
        self._gen = self.add_true(f) if is_load else self.strip_last_pipe(f)

    def strip_last_pipe(self, f):
        for line in f:
            line = line.rstrip("\n")
            yield (line[:-1] if line.endswith("|") else line) + "\n"

    def add_true(self, f):
        for line in f:
            line = line.rstrip("\n")
            yield line + "true \n"

    def readline(self, *_):
        return next(self._gen, "")

    def read(self, *_):
        return "".join(self._gen)
