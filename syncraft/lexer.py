from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, List, Iterable
import re
from enum import Enum, auto


import re
from dataclasses import dataclass, fields, field
from enum import Enum
from typing import Optional, Callable, Dict, List, Tuple, Any, Pattern


# -----------------------
# Rule decorator
# -----------------------
def rule(state: str = "DEFAULT", next_state: Optional[str] = None):
    """Decorator to attach lexer metadata to dataclass fields."""
    def wrapper(f):
        setattr(f, "_rule_meta", {"state": state, "next_state": next_state})
        return f
    return wrapper


@dataclass
class Lexer:
    TokenType: Enum  # will be generated automatically
    _states: Dict[str, re.Scanner] = field(default_factory=dict, init=False)
    @classmethod
    def build(cls) -> "Lexer":
        # 1. generate TokenType enum from dataclass fields
        cls.TokenType = Enum(
            cls.__name__ + "Type",
            {f.name: f.name for f in fields(cls)}
        )

        # 2. collect regex rules per state
        states: Dict[str, List[Tuple[str, Callable]]] = {}

        for f in fields(cls):
            regex = getattr(cls, f.name)
            meta = getattr(f, "_rule_meta", {})
            state = meta.get("state", "DEFAULT")
            next_state = meta.get("next_state")

            if state not in states:
                states[state] = []

            states[state].append(
                (regex, cls._make_action(f.name, next_state))
            )

        # 3. build Scanner per state
        instance = cls.__new__(cls)
        instance._states = {
            s: re.Scanner(rules) for s, rules in states.items()
        }
        instance._current_state = "DEFAULT"

        # make parent accessible to action functions
        for scanner in instance._states.values():
            scanner.parent = instance

        return instance

    @staticmethod
    def _make_action(name: str, next_state: Optional[str] = None):
        def action(scanner: Any, token: str):
            if next_state:
                scanner.parent.switch(next_state)
            return (scanner.parent.TokenType[name], token)
        return action

    def switch(self, state: str) -> None:
        if state not in self._states:
            raise ValueError(f"No such state: {state}")
        self._current_state = state

    def tokenize(self, text: str) -> List[Tuple[Enum, str]]:
        tokens, remainder = self._states[self._current_state].scan(text)
        if remainder:
            raise SyntaxError(f"Unrecognized input: {remainder!r}")
        return tokens


# -----------------------
# Example SQLite-like lexer
# -----------------------
@dataclass(frozen=True)
class SQLiteLexer(Lexer):
    # Default state tokens
    @rule(state="DEFAULT")
    WS: str = r"[ \t\n]+"

    @rule(state="DEFAULT")
    NUMBER: str = r"\d+(\.\d+)?([eE][+-]?\d+)?"

    @rule(state="DEFAULT")
    IDENT: str = r"[a-zA-Z_][a-zA-Z0-9_]*"

    @rule(state="DEFAULT", next_state="STRING")
    STRING_QUOTE: str = r"'"

    @rule(state="DEFAULT")
    PLUS: str = r"\+"

    @rule(state="DEFAULT")
    EQ: str = r"="

    # String state tokens
    @rule(state="STRING")
    STRING_TEXT: str = r"[^']+"

    @rule(state="STRING", next_state="DEFAULT")
    STRING_END: str = r"'"

    # Example comment (line comment)
    @rule(state="DEFAULT")
    COMMENT: str = r"--[^\n]*"


# -----------------------
# Usage example
# -----------------------
if __name__ == "__main__":
    lexer = SQLiteLexer.build()
    sql = "abc + 123 'hello' -- comment"

    tokens = lexer.tokenize(sql)
    for tok_type, value in tokens:
        print(f"{tok_type.name:12} : {value!r}")
