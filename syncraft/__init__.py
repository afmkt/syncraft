from .syntax import (
	Syntax,
    SyntaxSpec,
	Graph,
    LazySpec,
    AltSpec,
	SeqSpec,
    ManySpec,
    
)

from syncraft.regex import (
    RegexError,
)

from .algebra import (
    Algebra,
    Error,
    Left,
    Right,
    Either,
    EntryCategory,
)
from .bimap import (
    DataError, 
    bimap,
    iso,
    Not
)
from .ast import (
	AST,
    Seq,
    Alt,
	Token,
	Many,
    Nothing,
    SyncraftError,
)

from .grammar import (
    Grammar, 
    rule, 
    lazy,
    grammar, 
)
from .format import (
    LayoutDoc,
    Concat,
    Text,
    Group    
)

from .ebnf import (
    EBNF,
    GrammarDef,
)

try:
    from importlib.metadata import version
    __version__ = version("syncraft")
except Exception:
    __version__ = "0.0.0+unknown"

# Export commonly used class methods for convenience

__all__ = [
    "Grammar", "grammar", "rule", "lazy",
    "Algebra", "Error", "Left", "Right", "Either", "EntryCategory",
	"Syntax", "SyntaxSpec", "Graph", "LazySpec", "SeqSpec", "AltSpec", "ManySpec",
	"AST", "Token", "Many", "Nothing", "Seq", "Alt",
    "DataError", "Not", "bimap", "iso",
    "EBNF", "GrammarDef",
    "SyncraftError",
    "RegexError",
    "LayoutDoc", "Concat", "Text", "Group",
    "__version__",
]
