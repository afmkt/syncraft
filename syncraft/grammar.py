from __future__ import annotations
from typing import (
    Callable, Any, Dict, Union, Literal, Iterator, Optional, overload, TYPE_CHECKING, Literal
)
from syncraft.format import LayoutDoc, Group
from syncraft.algebra import Error
from syncraft.ast import SyncraftError, Unknown
from syncraft.syntax import Syntax
from syncraft.algebra import Algebra
from syncraft.parser import parser
from syncraft.generator import generator, validator
from syncraft.cache import Cache
from syncraft.input import StreamCursor
from syncraft.utils import file as get_file, line as get_line, func as get_func
import io
import asyncio
import textwrap

if TYPE_CHECKING:
    from syncraft.vis import SVGVisualization



NO_NAME = "<no_name>"

def rule(syntax: Syntax, *, name: str | None = None, is_root: bool = False) -> Syntax:
    """Define a named grammar rule with optional metadata.
    
    Marks a syntax definition as a named rule within a grammar, automatically
    capturing source location metadata for debugging and error reporting.
    
    Args:
        syntax: The syntax definition to mark as a rule.
        name: Optional name for the rule. If None, uses the variable name.
        is_root: Whether this rule is the root/entry point of the grammar.
    
    Returns:
        The syntax with updated metadata and root status.
    
    Example:
        >>> number = rule(Syntax.re(r"[0-9]+"), name="number")
        >>> expr = rule(number | operator, is_root=True)
    """
    level:int = 1
    file, line, func = get_file(level), get_line(level), get_func(level)
    if not isinstance(syntax, Syntax):
        raise TypeError("Argument to rule must be a Syntax instance")
    if is_root:
        syntax = syntax.as_root()
    ret = syntax._named(name=name, file=file, line=line, func=func)
    assert ret.is_root == is_root, "Rule root status does not match is_root argument"
    return ret



def lazy(S: type[Syntax], name: str | None | Callable[..., Syntax] = None, *, is_root: bool = False) -> Any:
    """Create a lazy-evaluated syntax rule for recursive or forward-referenced grammars.
    
    Enables defining recursive grammars by deferring syntax evaluation until needed.
    Can be used as a decorator or directly with a callable.
    
    Args:
        S: The Syntax class to use for creating the lazy syntax.
        name: Optional name for the lazy rule, or a callable returning Syntax.
              If callable, used directly. If string/None, used as decorator.
        is_root: Whether this lazy rule is the root of the grammar.
    
    Returns:
        If name is callable: Lazy syntax wrapping that callable.
        If name is string/None: Decorator function for wrapping a callable.
    
    Example:
        >>> @lazy(Syntax, "expr")
        ... def expr():
        ...     return term + operator + expr | term
        
        >>> # Or use directly:
        >>> expr = lazy(Syntax, lambda: term + operator + expr)
    """
    level = 1
    file, line, func = get_file(level), get_line(level), get_func(level)
    if callable(name):
        if is_root:
            return S.lazy(name).as_root()._named(name=None, file=file, line=line, func=func)
        else:
            return S.lazy(name)._named(name=None, file=file, line=line, func=func)
    elif isinstance(name, str) or name is None:
        def wrapper(f: Callable[..., Syntax]) -> Syntax:
            if is_root:
                return S.lazy(f).as_root()._named(name=name if name is not None else f.__name__, file=file, line=line, func=func)
            else:
                return S.lazy(f)._named(name=name if name is not None else f.__name__, file=file, line=line, func=func)
        return wrapper
    else: 
        raise TypeError(f"Argument to lazy must be a callable or a string or a boolean, got {type(name)}")
    


def class_field_location(cls):
    import inspect
    import ast
    source = textwrap.dedent(inspect.getsource(cls))
    filename = inspect.getsourcefile(cls)
    start_line = inspect.getsourcelines(cls)[1]
    tree = ast.parse(source)
    field_locations = {}
    class_node = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    for stmt in class_node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            field_locations[stmt.target.id] = (filename, stmt.lineno + start_line - 1)
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    field_locations[target.id] = (filename, stmt.lineno + start_line - 1)

    return field_locations

def grammar(cls: type) -> type:
    """Class decorator for defining grammars with automatic metadata collection.
    
    Transforms a class with Syntax attributes into a Grammar with automatic
    source location tracking, rule naming, and root rule detection. All class
    attributes that are Syntax instances become grammar rules.
    
    The decorated class inherits from Grammar and gains parse(), generate(),
    and validate() methods for working with the grammar.
    
    Args:
        cls: Class containing Syntax definitions as class attributes.
    
    Returns:
        The class with Grammar functionality and metadata attached.
    
    Raises:
        ValueError: If multiple root rules are defined or rules lack location info.
    
    Example:
        >>> @grammar
        ... class SimpleGrammar(Grammar):
        ...     number = Syntax.lit("123")
        ...     expr = rule(number, is_root=True)
        
        >>> result = SimpleGrammar.parse("123")
    """
    locations = class_field_location(cls)
    rules = dict()
    root = None
    for name, value in list(cls.__dict__.items()):
        if isinstance(value, Syntax):
            if value.spec.name is None:
                s_name = name
            elif value.spec.name == NO_NAME:
                s_name = None
            else:
                s_name = value.spec.name
            if value.location is None:                
                if name in locations:
                    file, line = locations[name]
                    value.update_meta_in_place(name = s_name, file=file, line=line, func=None, _location=True)
                    
                else:
                    raise ValueError(f"Grammar rules must have location information, but rule '{name}' does not.")
            else:
                value.update_meta_in_place(name = s_name, file = None, line= None, func=None, _location=False)
                
            rules[name] = value
            if value.is_root:
                if root is not None:
                    raise ValueError("Multiple root rules defined for grammar")
                root = value
            setattr(cls, name, value)
    setattr(cls, '_rules', rules)
    setattr(cls, '_root_rule', root)
    setattr(cls, '_parser', dict())
    setattr(cls, '_generator', dict())
    setattr(cls, '_validator', dict())
    return cls

        

    

class GrammarMeta(type):
    def __str__(cls) -> str:
        return type.__str__(cls)

    def __repr__(cls) -> str:
        return type.__repr__(cls)


class Grammar(metaclass=GrammarMeta):
    """Base class for declarative grammar definitions.
    
    Grammar provides a high-level interface for defining, parsing, and generating
    text according to syntax rules. Grammars are typically defined using the
    @grammar class decorator, which automatically collects Syntax rules and
    provides parsing and generation methods.
    
    The Grammar class caches parsers and generators for efficiency across
    multiple parse/generate operations.
    
    Attributes:
        _rules: Dictionary mapping rule names to Syntax definitions.
        _root_rule: The entry point syntax for the grammar (marked with is_root=True).
        _parser: Cache of parser algebras for rules.
        _generator: Cache of generator algebras for rules.
    
    Example:
        >>> @grammar
        ... class MyGrammar(Grammar):
        ...     digit = Syntax.re("[0-9]+")
        ...     number = rule(digit.many(at_least=1), is_root=True)
        
        >>> result = MyGrammar.parse("123")
        >>> doc = MyGrammar.generate(result, seed=0)
        >>> text = doc.render()
    """
    _rules: Dict[str, Syntax]
    _root_rule: Syntax | None
    _parser: Dict[Syntax, Algebra]
    _generator: Dict[Syntax, Algebra]
    _validator: Dict[Syntax, Algebra]


    @classmethod
    def vis(cls, syntax: Syntax | None = None, depth: int = 3) -> Optional["SVGVisualization"]:
        if syntax is None:
            syntax = cls._root_rule
        if syntax is None:
            raise ValueError("No root rule defined for the grammar")
        return syntax.vis(depth=depth)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._rules = dict()
        cls._root_rule = None
        cls._parser = dict()
        cls._generator = dict()
        cls._validator = dict()
    

    @classmethod
    def parser(cls, syntax: Syntax | None = None) -> Algebra:
        """Get (and cache) a parser algebra for this grammar.

        Args:
            syntax: Optional non-root syntax to build a parser for.

        Returns:
            Parser algebra instance.
        """
        if syntax is None:
            if cls._root_rule is None:
                raise ValueError("No root rule defined for the grammar")
            syntax = cls._root_rule
        if syntax in cls._parser:
            return cls._parser[syntax]
        ret = parser(syntax=syntax)
        cls._parser[syntax] = ret
        return ret
    
    @classmethod
    def generator(cls, syntax: Syntax | None = None) -> Algebra:
        """Get (and cache) a generator algebra for this grammar.

        Args:
            syntax: Optional non-root syntax to build a generator for.

        Returns:
            Generator algebra instance.
        """
        if syntax is None:
            if cls._root_rule is None:
                raise ValueError("No root rule defined for the grammar")
            syntax = cls._root_rule
        if syntax in cls._generator:
            return cls._generator[syntax]
        ret = generator(syntax=syntax)
        cls._generator[syntax] = ret
        return ret
    
    @classmethod
    def validator(cls, syntax: Syntax | None = None) -> Algebra:
        """Get (and cache) a validator algebra for this grammar.

        Args:
            syntax: Optional non-root syntax to build a validator for.

        Returns:
            Validator algebra instance.
        """
        if syntax is None:
            if cls._root_rule is None:
                raise ValueError("No root rule defined for the grammar")
            syntax = cls._root_rule
        if syntax in cls._validator:
            return cls._validator[syntax]
        ret = validator(syntax=syntax)
        cls._validator[syntax] = ret
        return ret

    @classmethod
    def parse(cls, data: str, syntax: Syntax | None = None) -> Any:
        """Parse text using the grammar.

        Args:
            data: Input text.
            syntax: Optional non-root syntax to parse with.

        Returns:
            Parsed value.
        """
        from syncraft.parser import Runner
        parser = cls.parser(syntax=syntax)
        runner: Runner = Runner()
        cursor = StreamCursor.from_data(data)
        for result in runner.run(parser, state=None, cursor=cursor, once=True, cache=Cache()):
            return result
        raise SyncraftError("Regex did not yield any results", offender=None, expect="at least one result")

    @classmethod
    def parse_file(cls, 
                   file_path: str,
                   mode: Literal['text', 'binary'] = 'text',
                   encoding: str = 'utf-8',
                   syntax: Syntax | None = None) -> Iterator[Any]:
        """Parse a file using the grammar, yielding all matches."""
        if mode == 'text':
            with open(file_path, "r", encoding=encoding) as f:
                yield from cls.parse_stream(f, mode=mode, syntax=syntax)
        elif mode == 'binary':
            with open(file_path, "rb") as f:
                yield from cls.parse_stream(f, mode=mode, syntax=syntax)
        else:
            raise ValueError(f"Unsupported mode: {mode}")
        

    @classmethod
    @overload
    def parse_stream(cls,
                     data: io.TextIOBase,
                     mode: Literal['text'] = 'text',
                     syntax: Syntax | None = None) -> Iterator[Any]: ...

    @classmethod
    @overload
    def parse_stream(cls,
                     data: io.BufferedIOBase,
                     mode: Literal['binary'] = 'binary',
                     syntax: Syntax | None = None) -> Iterator[Any]: ...

    @classmethod
    @overload
    def parse_stream(cls,
                     data: asyncio.StreamReader,
                     mode: Literal['text', 'binary'] = 'text',
                     syntax: Syntax | None = None) -> Iterator[Any]: ...

    @classmethod
    def parse_stream(cls, 
                     data: Union[io.TextIOBase, io.BufferedIOBase, asyncio.StreamReader], 
                     mode: Literal['text', 'binary'] = 'text',
                     syntax: Syntax | None = None) -> Iterator[Any]:
        """Parse from a stream using the grammar.

        Args:
            data: Text, binary, or async stream source.
            mode: Stream mode for decoding/iteration strategy.
            syntax: Optional non-root syntax to parse with.

        Yields:
            Parsed values produced by the parser.
        """
        from syncraft.parser import Runner
        parser = cls.parser(syntax=syntax)
        runner: Runner = Runner()
        if isinstance(data, io.TextIOBase):
            if mode != "text":
                raise ValueError("TextIOBase requires mode='text'")
            cursor: StreamCursor[Any] = StreamCursor.from_stream(data, mode="text")
        elif isinstance(data, io.BufferedIOBase):
            if mode != "binary":
                raise ValueError("BufferedIOBase requires mode='binary'")
            cursor = StreamCursor.from_stream(data, mode="binary")
        elif isinstance(data, asyncio.StreamReader):
            cursor = StreamCursor.from_stream(data, mode=mode)
        else:
            raise TypeError(f"Unsupported stream type: {type(data)}")
        for result in runner.run(parser, state=None, cursor=cursor, once=False, cache=Cache()):
            yield result
                
    @classmethod
    def generate(cls, data: Any = Unknown(), syntax: Syntax | None = None, seed: int | None = None, replay: bool = False) -> LayoutDoc:
        """Generate text using the grammar.

        Args:
            data: Source value/AST used for generation. ``None`` is treated as
                ``Unknown()``.
            syntax: Optional non-root syntax to generate with.
            seed: Optional random seed for reproducible stochastic choices.
            replay: When ``True``, replay provided structure instead of freely
                sampling pruned/implicit parts.

        Returns:
            A ``LayoutDoc`` representing generated output.
        """
        from syncraft.generator import Runner
        import random
        generator = cls.generator(syntax=syntax)        
        runner = Runner(ast=data if data is not None else Unknown(),
                        seed=seed if seed is not None else random.randint(0, 2**32 - 1), 
                        replay=replay)
        for result in runner.run(generator, state=None, cursor=None, once=True, cache=Cache()):  # type: ignore[arg-type]
            return LayoutDoc.from_ast(result)
        raise SyncraftError("Generation did not yield any results", offender=None, expect="at least one result")
        
        
    @classmethod
    def validate(cls, data: Any, syntax: Syntax | None = None, seed: int | None = None) -> Literal[True] | Error:
        """Validate data against the grammar.

        Args:
            data: Value/AST to validate.
            syntax: Optional non-root syntax to validate against.
            seed: Optional random seed used for deterministic internal choices.

        Returns:
            ``True`` when validation succeeds, or ``Error`` if validation fails.
        """
        from syncraft.generator import Runner
        import random
        validator = cls.validator(syntax=syntax)   
        runner = Runner(ast=data if data is not None else Unknown(), 
                        seed=seed if seed is not None else random.randint(0, 2**32 - 1),
                        replay=True)
        try:
            for result in runner.run(validator, state=None, cursor=None, once=True, cache=Cache()):
                if isinstance(result, Error):
                    return result
            return True
        except SyncraftError as e:
            return Error.new(this=None, message=f"Exception {e} during validation", error=e)
        
        
