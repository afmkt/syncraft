from __future__ import annotations
import pytest
from dataclasses import dataclass, replace, field
from syncraft.regex import parse
from syncraft.cache import Cache
from syncraft.syntax import Syntax
# from rich import print
from syncraft.constraint import Bindable, Binding
from syncraft.ast import Token
from syncraft.fa import Builder
from syncraft.input import StreamCursor
from syncraft.parser import parse as parser_run


from syncraft.regex import benchmark_fair, verify
from syncraft.alphabet import Alphabet
from syncraft.parser import  parse_word
import syncraft.generator as gen
from rich import print

from syncraft.regex import benchmark_fair, verify


def test():
    pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*])[A-Za-z\d!@#$%^&*]{8,}$'
    ret = parse(pattern, raw = False, cache=None)
    print(str(ret))


if __name__ == "__main__":
    # test()
    r = benchmark_fair()
    for line in r:
        print(line)
