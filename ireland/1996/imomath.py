"""
This is a mock-up module that demonstrates how a formal language
representation can be converted into a natural language one.

TODO: organize this properly into separate modules, and move into
different directory.

TODO: the objects in this module deserve to have equality/hash
operations, and to exist as singletons via metaclass magic.
"""
from typing import Optional, Tuple


class StrReprEquivalent:
    """
    Convenience class that allow you to just define __str__ and then
    get __repr__ for free.

    TODO: do some metaclass magic so that you can define either one
    and then you get the other for free
    """
    def __repr__(self):
        return str(self)


class Expression(StrReprEquivalent):
    """
    Base class for all expressions.

    TODO: __str__ representations sometimes contain undesirable
    extraneous parentheses, like "(n)!" rather than "n!". This is not
    wrong, but it is not stylish. Come up with a smarter
    parenthesization framework/algorithm - I'm sure there is a
    standard solution for this.
    """
    def __add__(self, other):
        return SumExpression(self, other)


class SumExpression(Expression):
    def __init__(self, left, right):
        self._left = left
        self._right = right

    def __str__(self):
        return f'{self._left} + {self._right}'


class FactorialExpression(Expression):
    def __init__(self, expr):
        self._expr = expr

    def __str__(self):
        return f'({self._expr})!'


def factorial(expr):
    return FactorialExpression(expr)


class GCDExpression(Expression):
    """
    TODO: devise more general machinery here. I separated this from
    FactorialExpression because I want the string representation of
    gcd expressions to use more natural language constructs. This
    detail should rather be an attribute of a more general function
    construct.
    """
    def __init__(self, left, right):
        self._left = left
        self._right = right

    def __str__(self):
        return f'greatest common divisor of {self._left} and {self._right}'


def gcd(left, right):
    """
    TODO: gcd should take variable number of args.
    """
    return GCDExpression(left, right)


class Symbol(Expression):
    def __init__(self, name: str):
        self._name = name

    def __str__(self):
        return self._name


class Sentence(StrReprEquivalent):
    pass


class Clause(StrReprEquivalent):
    pass


class LetXbeYSentence(Sentence):
    def __init__(self, noun_clause, direct_object):
        self._noun_clause = noun_clause
        self._direct_object = direct_object

    def __str__(self):
        return f'Let {self._noun_clause} be {self._direct_object}.'


class Let:
    def __init__(self, noun_clause):
        self._noun_clause = noun_clause

    def be(self, direct_object) -> Sentence:
        return LetXbeYSentence(self._noun_clause, direct_object)


class Find(Clause):
    def __init__(self, noun_clause):
        self._noun_clause = noun_clause

    def __str__(self):
        return f'Find the {self._noun_clause}'


class NounClause(Clause):
    def __init__(self, noun: str, adjectives: Optional[Tuple[str]]=None):
        self._noun = noun
        self._adjectives = adjectives if adjectives else tuple()

    def apply_adjective(self, adjective) -> 'NounClause':
        adjectives = tuple([adjective] + list(self._adjectives))
        return NounClause(self._noun, adjectives)

    def __str__(self):
        return f'{" ".join(self._adjectives)} {self._noun}'


def a(noun_clause : NounClause) -> NounClause:
    """
    TODO: "a" is not a great name, as it runs a high risk of
    colliding with a variable named "a". Consider renaming to "a_".
    """
    return noun_clause.apply_adjective('a')


def positive(noun_clause: NounClause) -> NounClause:
    return noun_clause.apply_adjective('positive')


integer = NounClause('integer')


class Problem:
    def __init__(self, *sentences):
        self._sentences = tuple(sentences)

    def __str__(self):
        return ' '.join(map(str, self._sentences))

