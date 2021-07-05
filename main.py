import re
from codecs import encode, decode
from functools import partial
from itertools import takewhile
import fileinput
import sys

def unescape(sample):
    return decode(encode(sample, 'latin-1', 'backslashreplace'), 'unicode-escape')

def alpha(char):
    return alphabet.index(char.lower())

number = re.compile(r'\d+')
letter = re.compile(r'\w')
operation = re.compile(r'<=|>=|==|/=|[+\-*/%^&|~<>]$')
token = re.compile(r'\d+|[a-z]|[+\-*/%^&|~<>=!]=|#\'?|\$[\'`_,]?|[+\-*/%^&|~<>=()\[\]{}:;@]|"[^"]+"')
alphabet = 'abcdefghijklmnopqrstuvwxyz'
endings = {'_':' ', '`':'\n', ',':', ', "'":''}

ops = {
    '+': lambda x, y: x + y,
    '-': lambda x, y: x - y,
    '*': lambda x, y: x * y,
    '/': lambda x, y: x // y,
    '%': lambda x, y: x % y,
    '^': lambda x, y: x ** y,
    '&': lambda x, y: x & y,
    '|': lambda x, y: x | y,
    '~': lambda x, y: x ^ y,
    '>': lambda x, y: int(x > y),
    '<': lambda x, y: int(x < y),
    '>=': lambda x, y: int(x >= y),
    '<=': lambda x, y: int(x <= y),
    '==': lambda x, y: int(x == y),
    '!=': lambda x, y: int(x != y),
}

def const(x, progm):
    'getter'
    progm.setval(x)
    return x
def getter(i, progm):
    'getter'
    progm.setval(progm.get(i))
    return progm.getval()
def applier(fn, y, progm): progm.setval(fn(progm.getval(), y(progm)))
def setter(i, progm): progm.set(i, progm.getval())
def inputter(progm):
    progm.input()
def outputter(do_ascii, end, progm):
    x = progm.getval()
    if do_ascii: x = chr(x)
    print(x, end=end)
def if_expr(cond, body, progm):
    if progm.run(cond):
        progm.run(body)
def while_loop(cond, body, progm):
    while progm.run(cond):
        progm.run(body)
def for_expr(list, body, progm):
    for fn in list:
        fn(progm)
        progm.run(body)
def for_modify(list, body, registers, progm):
    for fn, i in zip(list, registers):
        fn(progm)
        progm.set(alpha(i), progm.run(body))
def pointerto(body, progm):
    progm.setval(progm.addheap(body))
def caller(pointer, progm):
    x = progm.getval()
    fns = progm.heapget(pointer(progm))
    progm.setval(x)
    progm.run(fns)
def updater(op, i, progm):
    # x = progm.getval()
    progm.set(i, op(progm.get(i), progm.getval()))
    # progm.setval(x)
def ignorer(fns, progm):
    x = progm.getval()
    progm.run(fns)
    progm.setval(x)

def compiletoken(token, tokens):
    if number.match(token):
        return partial(const, int(token))
    if letter.match(token):
        return partial(getter, alpha(token))
    if operation.match(token):
        return partial(applier, ops[token], compiletoken(next(tokens), tokens))
    if token == '=':
        return partial(setter, alpha(next(tokens)))
    if '=' in token:
        return partial(updater, ops[token[0]], alpha(next(tokens)))
    if token in ['#', '#\'']:
        return inputter
    if token[0] == '$':
        return partial(outputter, len(token) == 1, endings[(token + "'")[1]])
    if token == '(':
        type, *cond = compile(tokens)
        if type == ')':
            return partial(ignorer, cond)
        end, *body = compile(tokens)
        if type == ':':
            return partial(if_expr, cond, body)
        elif type == ';':
            return partial(while_loop, cond, body)
    if token == '[':
        type = box()
        cond = list(takewhile(lambda t: type.set(t) not in ':;', tokens))
        tail, cond = cond, compile(iter(cond))
        # type, *cond = compile(tokens)
        end, *body = compile(tokens)
        if end == ':':
            tail = list(takewhile(lambda t: t != ']', tokens))
            return partial(for_modify, cond, body, tail)
        if type == ':':
            return partial(for_expr, cond, body)
        elif type == ';':
            return partial(for_modify, cond, body, tail)
    if token == '{':
        _, *body = compile(tokens)
        return partial(pointerto, body)
    if token == '@':
        return partial(caller, compiletoken(next(tokens), tokens))
    if token in ':;)]}':
        raise StopIteration(token)

def compile(tokens):
    out = []
    try:
        for token in tokens:
            fn = compiletoken(token, tokens)
            out.append(fn)
    except StopIteration as err:
        out.insert(0, err.value)
    return out

def tokenize(source):
    tokens = []
    source = source.strip()
    while (m := token.match(source)):
        if (tk := m.group())[0] == '"':
            for char in unescape(tk[1:-1]):
                tokens.append(str(ord(char)))
        else:
            tokens.append(tk)
        source = source[m.end():].lstrip()
    if len(source) > 0:
        raise BaseException('could not parse token at the position "%s..."'
            % repr(source[:10])[1:-1]
        )
    return tokens

class Program:
    def __init__(self, input): 
        self.value, self.registers = 0, [0]*26
        self.buffer, self.inputter = '', input
        self.heap = {}
    def getval(self): return self.value
    def setval(self, x): self.value = x
    def get(self, i): return self.registers[i]
    def set(self, i, x): self.registers[i] = x
    def run(self, fns):
        for fn in fns: fn(self)
        return self.getval()
    def input(self):
        if not self.buffer:
            try:
                self.buffer += next(self.inputter)
            except (StopIteration, KeyboardInterrupt):
                return self.setval(0)
        x = ord(self.buffer[0])
        self.buffer = self.buffer[1:]
        return self.setval(x)
    def addheap(self, x):
        id = hash(tuple(x))
        self.heap |= {id:x}
        return id
    def heapget(self, p):
        return self.heap[p]

class box:
    def set(self, x):
        self.val = x
        return x
    def __eq__(self, o): return self.val == o

if __name__ == '__main__':
    filename = sys.argv.pop(1)
    with open(filename) as file:
        string = file.read()

    inp = iter(fileinput.input())
    tokens = tokenize(string)
    comp = compile(iter(tokens))
    prog = Program(inp)
    prog.run(comp)