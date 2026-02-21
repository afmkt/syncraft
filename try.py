from typing import Type

import pytest

from syncraft.regex import parse
from syncraft.syntax import Syntax as S
from syncraft.fa import Builder as B
from syncraft.algebra import Error
from syncraft.regex import (
    parse, RE, 
    UnsupportedFeature,
    LiteralAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)


def test():
    x = parse(r'\\d{2,}\\U000F44C9{2}\\U000AA4AB{1,5}[Av]*|(?b)|$')
    print(x)





if __name__ == "__main__":
    test()
    