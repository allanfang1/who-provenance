class GenFile:
    def __init__(self, f):
        self._gen = self.strip_last_pipe(f)

    def strip_last_pipe(self, f):
        for line in f:
            line = line.rstrip("\n")
            yield (line[:-1] if line.endswith("|") else line) + "\n"

    def readline(self, *_):
        return next(self._gen, "")

    def read(self, *_):
        return "".join(self._gen)
