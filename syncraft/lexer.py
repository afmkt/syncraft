from __future__ import annotations

from typing import (
    Any, Tuple, Generator as PyGenerator, TypeVar, Optional, Callable, Hashable, List
)
from dataclasses import dataclass, replace, field
from syncraft.algebra import (
    Algebra, Either, Right, Incomplete, Left, SyncraftError
)
from syncraft.fa import NFA
from syncraft.ast import ThenSpec, ManySpec, ChoiceSpec, ThenKind
from syncraft.constraint import Bindable, FrozenDict
from syncraft.cache import Cache
import re
import io
from syncraft.syntax import Syntax

from rich import print
