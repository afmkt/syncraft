from __future__ import annotations
from rich import print
from rich.table import Table as RichTable
from typing import Tuple, Any, Set
from syncraft.syntax import Syntax
from syncraft.algebra import  Left, Right, Error, Either, Algebra

from syncraft.parser import ParserState, Token
from sqlglot.expressions import Expression


def rich_error(err: Error)->None:
    lst = err.to_list(lambda _: True)
    root, leaf = lst[0], lst[-1]
    tbl = RichTable(title="Parser Error", show_lines=True)
    tbl.add_column("Root Parser Field", style="blue")
    tbl.add_column("Root Parser Value", style="green")
    tbl.add_column("...")
    tbl.add_column("Leaf Parser Field", style="blue")
    tbl.add_column("Leaf Parser Value", style="yellow")
    flds: Set[str] = set(root.keys()) | set(leaf.keys())
    for fld in sorted(flds):
        root_value = root.get(fld, "N/A")
        leaf_value = leaf.get(fld, "N/A")
        tbl.add_row(f"{fld}", f"{root_value}", "...", f"{fld}", f"{leaf_value}")
    print(tbl)


def rich_parser(p: Any)-> None:
    print("Parser Debug Information:")
    print(p._string or repr(p))

def rich_debug(this: Algebra[Any, ParserState[Any]], 
               state: ParserState[Any], 
               result: Either[Any, Tuple[Any, ParserState[Any]]])-> None:
    def value_to_str(value: Any, prefix:str='') -> str:
        if isinstance(value, (tuple, list)):
            if len(value) == 0:
                return prefix + str(value)
            else:
                return '\n'.join(value_to_str(item, prefix=prefix+' - ') for item in value)
        else:                
            if isinstance(value, Expression):
                return prefix + value.sql()
            elif isinstance(value, Token):
                return prefix + f"{value.token_type.name}({value.text})"
            elif isinstance(value, (Error, ParserState, Syntax)):
                return prefix + (value._string or 'N/A')
            else:
                return prefix + str(value)

    tbl = RichTable(title=f"Debug: {this.name}", show_lines=True)
    tbl.add_column("Parser", style="blue")
    tbl.add_column("Old State", style="cyan")
    tbl.add_column("Result", style="magenta")
    tbl.add_column("New State", style="green")
    tbl.add_column("Consumed", style="green")
    if isinstance(result, Left):
        tbl.add_row(value_to_str(this), value_to_str(state), value_to_str(result.value), 'N/A', 'N/A')
    else:
        assert isinstance(result, Right), f"Expected result to be a Right value, got {type(result)}, {result}"
        value, new_state = result.value
        tbl.add_row(value_to_str(this), 
                    value_to_str(state),
                    value_to_str(value), 
                    value_to_str(new_state), 
                    value_to_str(state.delta(new_state)))

    print(tbl)

