from __future__ import annotations
from typing import Any
from syncraft.syntax import Syntax, lazy, choice
import syncraft.parser as dsl
from syncraft.utils import rich_error, rich_debug, rich_parser
from sqlglot import TokenType


