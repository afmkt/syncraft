from __future__ import annotations

from typing import List
from syncraft.token import Structured




from sqlglot import tokenize
from sqlglot import Token as SQLGlotToken



def sqlglot_token_class()->Structured[SQLGlotToken]:
    return Structured(TokenConstructor=SQLGlotToken)

def sqlglot_lex(input: str, dialect: str) -> List[SQLGlotToken]:
    tkns = tokenize(input, dialect=dialect)
    return tkns