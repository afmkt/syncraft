from __future__ import annotations

from typing import List
from syncraft.ast import TokenClass




from sqlglot import tokenize
from sqlglot import Token as SQLGlotToken



def sqlglot_token_class()->TokenClass[SQLGlotToken]:
    return TokenClass(TokenConstructor=SQLGlotToken)

def sqlglot_lex(input: str, dialect: str) -> List[SQLGlotToken]:
    tkns = tokenize(input, dialect=dialect)
    return tkns