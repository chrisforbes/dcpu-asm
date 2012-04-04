#!/usr/bin/env python2

import sys, operator
from pyparsing import *

# assembler for notch's dcpu-16 architecture
# specifications here: http://0x10c.com/doc/dcpu-16.txt

# todo:
#   - support more flexible constexprs
#   - support something more than just a literal address for org
#   - better error reporting
#   - better arg parsing
#   - make everything case-insensitive [except string literals]
#   - support extended ops in 0-opcode space (just jsr so far)
#   - more pseudo-ops (at least ret => set pc,[sp+]
#   - macros!
#   - support [busted] push/pop/peek as well as [-sp]/[sp+]/[sp]
#   - support notch's weird label syntax (leading-:)

# note: dat,org pseudo-ops
ops = [None, 'set','add','sub','mul','div','mod','shl','shr',
       'and','bor','xor','ife','ifn','ifg','ifb','dat','org','jsr']

def Keywords(xs):
    return reduce(operator.or_, map(Keyword,xs))

class MemRef(object):
    def __init__(self,expr):
        self.expr = expr[0]
    def __repr__(self):
        return 'MemRef(' + str(self.expr) + ')'

class StrData(object):
    def __init__(self,expr):
        self.expr = expr[0][1:-1]
    def __repr__(self):
        return 'StrData(' + str(self.expr) + ')'

class AddExpr(object):
    def __init__(self,expr):
        self.a = expr[0]
        self.b = expr[1]
    def __repr__(self):
        return 'AddExpr(' + str(self.a) + ',' + str(self.b) + ')'

def maybeAdd(x):
    if len(x) > 1:
        return AddExpr(x)
    return x

def basenum(x): return int(str(x[0]),0)

ident     = Keyword('sp+') | Keyword('-sp') |\
                Word(alphas + '_.', alphanums + '_.')
number    = Regex('0x[0-9a-fA-F]+|[0-9]+').setParseAction(basenum)
comment   = Regex(';.*$')
label     = ident + Suppress(':')
op        = Keywords([o for o in ops if o])
val3      = ident | number | quotedString.setParseAction(StrData)
val2      = (val3 + Optional(Suppress('+') + val3)).setParseAction(maybeAdd);
memref    = (Suppress('[') + val2 + Suppress(']')).setParseAction(MemRef);
val       = val2 | memref
inst      = Group(op) + Group(delimitedList(val))
line      = Group(Optional(label)) +\
                Optional(inst) +\
                Suppress(Optional(comment))

class State(object):
    def __init__(self):
        self.org = 0                # current assembly position
        self.maxorg = 0             # high water mark for what we must actually emit
        self.out = [0] * 0x10000
        self.localsyms = {}         # sym -> addr
        self.globalsyms = {}        # sym -> addr
        self.fixups = {}            # addr -> sym

    def emit(self,x):
        if type(x) == int: self.out[ self.org ] = x
        else:              self.fixups[ self.org ] = x
        self.org += 1

    def flushlocals(self):
        for f,s in self.fixups.items()[:]:
            if s.startswith('.'):
                if s in self.localsyms:
                    self.out[f] = self.localsyms[s]
                    del self.fixups[f]
                else:
                    raise Exception('Unresolved local symbol %s' % s)
        self.localsyms = {}

    def flushglobals(self):
        for f,s in self.fixups.items()[:]:
            if not s.startswith('.'):
                if s in self.globalsyms:
                    self.out[f] = self.globalsyms[s]
                    del self.fixups[f]
                else:
                    raise Exception('Unresolved global symbol %s' % s)
        self.globalsyms = {}

    def define(self, sym):
        # if it's global, we need to flush the locals.
        if not sym.startswith('.'):
            self.flushlocals()
            self.globalsyms[sym] = self.org
        else:   # otherwise just add it to the local syms
            self.localsyms[sym] = self.org

def main(args):
    src = ''
    has_src = False
    dest = None
    next_is_out = False
    for a in args[1:]:
        if a != '-' and a.startswith('-'):
            if a == '--help':
                print 'usage: asm.py -o outfile infile ...'
                return 0
            pass
        else:
            if next_is_out:
                if dest: raise Exception( 'Output already specified.' )
                # todo: support `-` => stdout
                dest = file(a, 'wb')
            else:
                # todo: support `-` => stdin
                src += file(a).read()
                has_src = True
        next_is_out = a == '-o'

    if not has_src:
        raise Exception( 'No input files.' )
    if not dest:
        raise Exception( 'No output specified.' )

    state = State()

    def assemble_arg(x):
        # return (bits,[extra words])
        direct_regs = { 'a':0, 'b':1, 'c':2, 'x':3, 'y':4, 'z':5,
                        'i':6, 'j':7, 'sp':27, 'pc':28, 'o':29 }
        indirect_regs = { 'a':8, 'b':9, 'c':10, 'x':11, 'y':12, 'z':13,
                        'i':14, 'j':15, 'sp':25, 'sp+':24, '-sp':26 }
        indirect_ofs_regs = { 'a':16, 'b':17, 'c':18, 'x':19, 'y':20, 'z':21,
                        'i':22, 'j':23 }
        if type(x) == int:
            if x >= 0 and x < 32: return (32+x, [])   # try short immediate form in operand first
            return (31,[x])                           # otherwise, put it in the next word.
        if type(x) == str:
            if x in direct_regs: return (direct_regs[x], [])
            return (31,[x])                           # todo: support emitting short immediate here?
        if type(x) == MemRef: # [arg]
            y = x.expr
            if type(y) == int:
                return (30,[y])
            if type(y) == AddExpr:
                # todo: do this properly
                if type(y.a) == str and (y.a) in indirect_ofs_regs:
                    if type(y.b) == str or type(y.b) == int:
                        return (indirect_ofs_regs[y.a], [y.b])
                if type(y.b) == str and (y.b) in indirect_ofs_regs:
                    if type(y.a) == str or type(y.a) == int:
                        return (indirect_ofs_regs[y.b], [y.a])
            if type(y) == str:
                if y in indirect_regs: return (indirect_regs[y], [])
                return (30,[y])                       # indirect immediate
        raise Exception( 'Don\'t know how to assemble arg `%s`' % x )

    for l in src.split('\n'):      # todo: parse everything at once, so we get proper line numbers
        rr = line.parseString(l,parseAll=True)

        if len(rr[0]):
            state.define(rr[0][0])

        # actually assemble some opcodes
        if len(rr) > 1:
            op = rr[1][0]
            args = rr[2]

            def check_num_operands(expected):
                if len(args) != expected:
                    raise Exception( 'Expected %d operands for `%s`, got %d' % (expected, op, len(args)) )

            opindex = ops.index(op)
            if op == 'org':
                check_num_operands(1)
                state.maxorg = max(state.org,state.maxorg)
                if type(args[0]) == int:
                    state.org = args[0]
                else:
                    raise Exception( 'Don\'t know how to evaluate `%s` in argument of `ord`' % args[0] )
            elif op == 'dat':         # various literal data
                for a in args:
                    if type(a) == int: state.emit(a)
                    elif type(a) == StrData:
                        for x in a.expr: state.emit(ord(x))
                    else: state.emit(a) # a symbol

            elif op == 'jsr':     # todo: proper dispatch for extended ops
                check_num_operands(1)
                # extended instruction format aaaaaaoooooo0000: 0=zero, o=opcode, a=operand
                op1,e1 = assemble_arg(args[0])
                state.emit(0 | (1<<4) | (op1<<10))
                for e in e1: state.emit(e)

            else:
                check_num_operands(2)
                op1,e1 = assemble_arg(args[0])
                op2,e2 = assemble_arg(args[1])
                # instruction format: bbbbbbaaaaaaoooo: o=opcode, a=first operand, b=second operand
                state.emit(opindex | (op1<<4) | (op2<<10))
                for e in e1+e2: state.emit(e)

    state.flushlocals()
    state.flushglobals()
    state.maxorg = max(state.org,state.maxorg)

    # now output the assembled code:
    for i in xrange(0,state.maxorg):
        dest.write( chr(state.out[i] & 0xff) )
        dest.write( chr((state.out[i] >> 8) & 0xff) )

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
