#!/usr/bin/env python3
"""
Copyright (c) 2019-2020 David Shin.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

Adapted from Peter Jin's tokenizer.rs
"""
from abc import ABCMeta, abstractmethod
from enum import Enum
import os
import sys
from typing import List, Optional, Union


DEBUG = False
def debug_print(x):
    if DEBUG:
        print(x)


char = str


def char_repr(c: char):
    c = r'\n' if c=='\n' else c
    return f'"{c}"'


class Mode(Enum):
    Text = 0
    InlineMath = 1
    DisplayMath = 2


class MathStart(Enum):
    Dollar = 0
    Bracket = 1


class Pos(Enum):
    Begin = 0
    End = 1


def type_str(s):
    s = str(type(s))
    s = s.split("'")[1]
    s = s.replace('__main__.', '')
    s = s.split('.')[-1]
    return s


StrBuf = List[str]
StrBufLike = Union[StrBuf, str, None]


def to_str_buf(s: StrBufLike) -> StrBuf:
    if isinstance(s, str):
        return [s]
    if isinstance(s, list):
        return s
    return []


class LatexToken:
    def __str__(self):
        return f'[{type_str(self)}]'


class Item(metaclass=ABCMeta):
    def __str__(self):
        return f'[{type_str(self)}]'

    @abstractmethod
    def to_toks(self) -> List[LatexToken]:
        pass

    @abstractmethod
    def handle(self, tokenizer: 'LatexTokenizer', c: char) -> Optional[bool]:
        """
        A truthy return value indicates that the parent loop should continue.
        """
        pass


class BufItem(Item, metaclass=ABCMeta):
    def __init__(self, s: StrBufLike=None):
        self.buf: StrBuf = to_str_buf(s)

    def __str__(self):
        return f'[{type_str(self)}:{"".join(self.buf)}]'


class LatexTokenizer:
    def __init__(self, emit_digits=False):
        self.stack: List[Item] = [Items.Text('')]
        self.mode: Mode = Mode.Text
        self.toks: List[LatexToken] = []
        self.emit_digits: bool = emit_digits

    def buf_commit(self, item: BufItem):
        if not item.buf: return
        self.commit(LatexTokens.Text(item.buf))

    def commit_text(self, buf: str):
        if buf:
            self.commit(LatexTokens.Text(buf))

    def commit(self, token: LatexToken):
        debug_print(f'Commit: {token}')
        assert isinstance(token, LatexToken)
        self.toks.append(token)

    def enqueue(self, item: Item):
        debug_print(f'Enqueue: {item}')
        self.stack.append(item)

    def pop(self) -> Item:
        return self.stack.pop()

    def tokenize_math_char(self, math_item: 'BufItem', c: char):
        debug_print(f'tokenize_math_char({math_item}, {char_repr(c)})')
        if c in "+-<>.,?;:[]()^_{}'":
            self.commit_text(''.join(math_item.buf))
            self.commit(LatexTokens.from_char(c, True))
            self.enqueue(math_item)
        elif c.isspace():
            # math-mode can ignore whitespace
            self.enqueue(math_item)
        elif c.isnumeric():
            if self.emit_digits:
                self.commit(LatexTokens.from_char(c, True))
                self.enqueue(math_item)
                return
            self.commit_text(''.join(math_item.buf))
            self.enqueue(math_item)
            self.commit(LatexTokens.from_char(c, True))
        elif c == '\\':
            self.commit_text(''.join(math_item.buf))
            self.enqueue(math_item)
            self.enqueue(Items.Command())
        else:
            self.commit_text(c)
            self.enqueue(math_item)

    def tokenize_char(self, c: char):
        debug_print(f'tokenize_char({char_repr(c)})')
        while self.stack:
            item: Item = self.stack.pop()
            debug_print(f'stack: {item} {char_repr(c)}')
            if not item.handle(self, c):
                break

    def tokenize(self, source: str):
        debug_print('Reading source')
        for c in source:
            self.tokenize_char(c)
        debug_print('Popping remaining stack')
        while self.stack:
            item = self.stack.pop()
            debug_print(f'stack: {item}')
            for tok in item.to_toks():
                self.commit(tok)


class LatexTokenWithText(LatexToken):
    def __init__(self, buf: StrBufLike):
        self.text = ''.join(to_str_buf(buf))

    def __str__(self):
        text = self.text.replace('\n', '\\n')
        return f'[{type_str(self)}:{text}]'


class LatexTokens:
    class Text(LatexTokenWithText): pass
    class Number(LatexTokenWithText): pass
    class Command(LatexTokenWithText): pass
    class Symbol(LatexTokenWithText): pass
    class Punct(LatexTokenWithText): pass

    class LBrack(LatexToken): pass
    class RBrack(LatexToken): pass
    class LCurly(LatexToken): pass
    class RCurly(LatexToken): pass
    class LParen(LatexToken): pass
    class RParen(LatexToken): pass
    class LQuote(LatexToken): pass
    class RQuote(LatexToken): pass
    class LDQuote(LatexToken): pass
    class RDQuote(LatexToken): pass
    class VBar(LatexToken): pass
    class Space(LatexToken): pass
    class Super(LatexToken): pass
    class Sub(LatexToken): pass
    class LGroup(LatexToken): pass
    class RGroup(LatexToken): pass
    class StartInlineMath(LatexToken): pass
    class EndInlineMath(LatexToken): pass
    class StartDisplayMath(LatexToken): pass
    class EndDisplayMath(LatexToken): pass

    punct_chars = '.,?;:'
    symbol_chars = '+-<>'

    char_map = {
        '[': LBrack,
        ']': RBrack,
        '(': LParen,
        ')': RParen,
        '{': LGroup,
        '}': RGroup,
        '`': LQuote,
        "'": RQuote,
        '|': VBar,
    }

    cmd_char_map = dict(char_map)
    cmd_char_map.update({
        '{': LCurly,
        '}': RCurly,
        '^': Super,
        '_': Sub,
    })

    @staticmethod
    def from_char(c: char, cmd=False) -> LatexToken:
        if c in LatexTokens.punct_chars:
            return LatexTokens.Punct(c)
        if c in LatexTokens.symbol_chars:
            return LatexTokens.Symbol(c)
        if c.isspace():
            return LatexTokens.Space()
        if c.isnumeric():
            return LatexTokens.Number(c)
        if c == '\\':
            return LatexTokens.Command(c)
        cmap = LatexTokens.cmd_char_map if cmd else LatexTokens.char_map
        return cmap[c]()


class Items:
    class Text(BufItem):
        def to_toks(self):
            return [LatexTokens.Text(self.buf)] if self.buf else []

        def handle(self, tokenizer: LatexTokenizer, c: char):
            tokenizer.mode = Mode.Text
            if c == '$':
                tokenizer.buf_commit(self)
                tokenizer.enqueue(Items.Text())
                tokenizer.enqueue(Items.InlineMath(MathStart.Dollar, Pos.Begin))
            elif c in '.,?;:(){}':
                tokenizer.buf_commit(self)
                tokenizer.commit(LatexTokens.from_char(c))
                tokenizer.enqueue(Items.Text())
            elif c in "`'\\" or c.isspace():
                tokenizer.buf_commit(self)
                tokenizer.enqueue(Items.Text())
                tokenizer.enqueue(Items.from_char(c))
            else:
                self.buf.append(c)
                tokenizer.enqueue(self)

    class LQuote(Item):
        def to_toks(self):
            return [LatexTokens.LQuote()]

        def handle(self, tokenizer: LatexTokenizer, c: char):
            if c == '`':
                tokenizer.commit(LatexTokens.LDQuote())
            else:
                tokenizer.commit(LatexTokens.LQuote())
                return True

    class RQuote(Item):
        def to_toks(self):
            return [LatexTokens.RQuote()]

        def handle(self, tokenizer: LatexTokenizer, c: char):
            if c == "'":
                tokenizer.commit(LatexTokens.RDQuote())
            else:
                tokenizer.commit(LatexTokens.RQuote())
                return True

    class Number(Item):
        def __init__(self):
            self.buf: StrBuf = []

        def to_toks(self):
            return [LatexTokens.Number(self.buf)] if self.buf else []

        def handle(self, tokenizer: LatexTokenizer, c: char):
            if c.isnumeric():
                self.buf.append(c)
                tokenizer.enqueue(self)
            else:
                assert self.buf, 'bug'
                tokenizer.commit(LatexTokens.Number(self.buf))
                return True

    class Command(BufItem):
        def to_toks(self):
            return [LatexTokens.Command(self.buf)] if self.buf else []

        def handle(self, tokenizer: LatexTokenizer, c: char):
            if not self.buf and c == '[':
                item: Item = tokenizer.pop()
                assert type(item) == Items.Text
                tokenizer.buf_commit(item)
                tokenizer.commit(LatexTokens.StartInlineMath())
                tokenizer.enqueue(Items.Text())
                tokenizer.enqueue(Items.InlineMath(MathStart.Bracket, Pos.End))
            elif not self.buf and c == ']':
                item: Item = tokenizer.pop()
                assert type(item) == Items.InlineMath
                assert item.start == MathStart.Bracket
                tokenizer.buf_commit(self)
                tokenizer.commit(LatexTokens.EndInlineMath())
            elif not self.buf and c in '{}|':
                tokenizer.commit(LatexTokens.from_char(c, cmd=True))
            elif c.isalpha():
                self.buf.append(c)
                tokenizer.enqueue(Items.Command(self.buf))
            elif c == ' ':
                if not self.buf:
                    # "/ " is a whitespace command
                    self.buf.append(c)
                tokenizer.commit(LatexTokens.Command(self.buf))
                return True
            else:
                assert self.buf
                tokenizer.commit(LatexTokens.Command(self.buf))
                return True

    class Space(Item):
        def to_toks(self):
            return [LatexTokens.Space()]

        def handle(self, tokenizer: LatexTokenizer, c: char):
            if c.isspace():
                tokenizer.enqueue(self)
            else:
                if tokenizer.mode == Mode.Text:
                    tokenizer.commit(LatexTokens.Space())
                return True

    class InlineMath(BufItem):
        def __init__(self, start: MathStart, pos: Pos, s: StrBufLike=None):
            self.start = start
            self.pos = pos
            super().__init__(s)

        def __str__(self):
            return f'[{type_str(self)}:{self.start}:{self.pos}]'

        @staticmethod
        def lambda_init(start: MathStart):
            return lambda *args: Items.InlineMath(start, *args)

        def to_toks(self):
            raise Exception(f'Unterminated InlineMath({self.start})')

        def handle(self, tokenizer: LatexTokenizer, c: char):
            tokenizer.mode = Mode.InlineMath
            if self.pos == Pos.Begin:
                if c == '$':
                    assert self.start == MathStart.Dollar
                    assert not self.buf
                    tokenizer.enqueue(Items.Text())
                    tokenizer.enqueue(Items.DisplayMath(Pos.Begin))
                    return
                else:
                    tokenizer.commit(LatexTokens.StartInlineMath())
            if c == '$':
                assert self.start == MathStart.Dollar
                tokenizer.buf_commit(self)
                tokenizer.commit(LatexTokens.EndInlineMath())
            else:
                self.pos = Pos.End
                tokenizer.tokenize_math_char(self, c)

    class DisplayMath(BufItem):
        def __init__(self, pos: Pos, s: StrBufLike=None):
            self.pos = pos
            self.close_count = 0
            super().__init__(s)

        def __str__(self):
            return f'[{type_str(self)}:{self.pos}]'

        def to_toks(self):
            raise Exception('Unterminated DisplayMath')

        def handle(self, tokenizer: LatexTokenizer, c: char):
            tokenizer.mode = Mode.DisplayMath
            if self.pos == Pos.Begin:
                assert c != '$'
                tokenizer.commit(LatexTokens.StartDisplayMath())
                tokenizer.enqueue(Items.Text())
                tokenizer.enqueue(Items.DisplayMath(Pos.End))
                return
            if c == '$':
                self.close_count += 1
                if self.close_count == 1:
                    tokenizer.buf_commit(self)
                    tokenizer.enqueue(self)
                else:
                    tokenizer.commit(LatexTokens.EndDisplayMath())
            else:
                self.pos = Pos.End
                tokenizer.tokenize_math_char(self, c)

    char_map = {
        '`': LQuote,
        "'": RQuote,
    }

    @staticmethod
    def from_char(c: char) -> Item:
        if c == '\\':
            return Items.Command(c)
        if c.isspace():
            return Items.Space()
        return Items.char_map[c]()


class LatexDocument:
    def __init__(self, text: str, emit_digits=False):
        self.text = text
        tokenizer = LatexTokenizer(emit_digits)
        tokenizer.tokenize(text)
        self.toks = tokenizer.toks


if __name__ == '__main__':
    filename = os.path.expanduser(sys.argv[1])
    with open(filename) as f:
        text = f.read()
    doc = LatexDocument(text)
    #doc = LatexDocument(text, True)
    print('\n'.join(map(str, doc.toks)))

