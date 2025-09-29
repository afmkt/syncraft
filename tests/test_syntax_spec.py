from __future__ import annotations

from typing import Dict, Iterable, List, Set

from syncraft.syntax import (
    Syntax,
    SyntaxSpec,
    LazySpec,
    ThenSpec,
    ChoiceSpec,
    ManySpec,
    FactorySpec,
)
from syncraft.ast import (
    Token,
    Then,
    Choice,
    Many,
    Marked,
    Collect,
    Nothing,
    Lazy,
    ThenKind,
    TokenClass,
)
from syncraft.fa import FABuilder
from syncraft.parser import parse_word


def _rehydrate(
    cls: type[Syntax],
    spec: SyntaxSpec,
    cache: Dict[SyntaxSpec, Syntax] | None = None,
) -> Syntax:
    """Rebuild a ``Syntax`` node from its spec tree."""

    if cache is None:
        cache = {}
    if spec in cache:
        return cache[spec]

    if isinstance(spec, LazySpec):
        syntax = cls.lazy(lambda: _rehydrate(cls, spec.spec(), cache))
    elif isinstance(spec, ThenSpec):
        left = _rehydrate(cls, spec.left, cache)
        right = _rehydrate(cls, spec.right, cache)
        if spec.kind == ThenKind.BOTH:
            syntax = left + right
        elif spec.kind == ThenKind.LEFT:
            syntax = left // right
        elif spec.kind == ThenKind.RIGHT:
            syntax = left >> right
        else:  # pragma: no cover - defensive guard
            raise AssertionError(f"Unsupported ThenKind: {spec.kind!r}")
    elif isinstance(spec, ChoiceSpec):
        syntax = _rehydrate(cls, spec.left, cache) | _rehydrate(cls, spec.right, cache)
    elif isinstance(spec, ManySpec):
        inner = _rehydrate(cls, spec.spec, cache)
        syntax = inner.many(at_least=spec.at_least, at_most=spec.at_most)
    elif isinstance(spec, FactorySpec):
        kwargs = dict(spec.kwargs)
        if spec.name == "success":
            (value,) = spec.args
            syntax = cls.success(value)
        elif spec.name == "fail":
            (error,) = spec.args
            syntax = cls.fail(error)
        elif spec.name == "token":
            syntax = cls.token(**kwargs)
        else:
            if spec.args:
                raise AssertionError(
                    f"FactorySpec '{spec.name}' currently only supports kwargs, got args={spec.args!r}"
                )
            syntax = cls.factory(spec.name, **kwargs)
    else:  # pragma: no cover - defensive guard
        raise AssertionError(f"Unsupported SyntaxSpec node: {spec!r}")

    cache[spec] = syntax
    return syntax


def _collect_terminal_builders(spec: SyntaxSpec) -> Set[FABuilder]:
    visited: Set[SyntaxSpec] = set()
    builders: Set[FABuilder] = set()

    def visit(node: SyntaxSpec) -> None:
        if node in visited:
            return
        visited.add(node)

        if isinstance(node, LazySpec):
            visit(node.spec())
        elif isinstance(node, ThenSpec):
            visit(node.left)
            visit(node.right)
        elif isinstance(node, ChoiceSpec):
            visit(node.left)
            visit(node.right)
        elif isinstance(node, ManySpec):
            visit(node.spec)
        elif isinstance(node, FactorySpec):
            if node.name == "token":
                kwargs = dict(node.kwargs)
                text = kwargs.get("text")
                tag = kwargs.get("token_type")
                if isinstance(text, (str, bytes)):
                    builders.add(FABuilder.literal(text, tag=tag))
        else:  # pragma: no cover - defensive guard
            raise AssertionError(f"Unexpected spec node: {node!r}")

    visit(spec)
    return builders


def _flatten_choices(spec: SyntaxSpec) -> List[SyntaxSpec]:
    if isinstance(spec, ChoiceSpec):
        return _flatten_choices(spec.left) + _flatten_choices(spec.right)
    return [spec]


def _is_left_recursive(alt: SyntaxSpec, root: SyntaxSpec) -> bool:
    current = alt
    while isinstance(current, ThenSpec):
        candidate = current.left
        if candidate is root:
            return True
        current = candidate
    return False


def _strip_left_recursion(alt: SyntaxSpec, root: SyntaxSpec) -> SyntaxSpec:
    if not isinstance(alt, ThenSpec):  # pragma: no cover - defensive guard
        raise AssertionError("Left-recursive alternative must be a ThenSpec")
    if alt.left is root:
        return alt.right
    if isinstance(alt.left, ThenSpec):
        new_left = _strip_left_recursion(alt.left, root)
        return ThenSpec(kind=alt.kind, left=new_left, right=alt.right)
    raise AssertionError("Unable to strip root from left-recursive branch")


def _grammar_is_left_recursive(spec: SyntaxSpec) -> bool:
    inner = spec.spec() if isinstance(spec, LazySpec) else spec
    return any(_is_left_recursive(alt, spec) for alt in _flatten_choices(inner))


def _flatten_token_text(node: object) -> List[str]:
    if isinstance(node, Token):
        return [node.text]
    if isinstance(node, Then):
        return _flatten_token_text(node.left) + _flatten_token_text(node.right)
    if isinstance(node, Choice):
        return _flatten_token_text(node.value) if node.value is not None else []
    if isinstance(node, Many):
        items: List[str] = []
        for child in node.value:
            items.extend(_flatten_token_text(child))
        return items
    if isinstance(node, Lazy):
        return _flatten_token_text(node.value)
    if isinstance(node, Marked):
        return _flatten_token_text(node.value)
    if isinstance(node, Collect):
        return _flatten_token_text(node.value)
    if isinstance(node, Nothing):
        return []
    return []


def _or_all(nodes: Iterable[Syntax]) -> Syntax:
    iterator = iter(nodes)
    first = next(iterator)
    result = first
    for node in iterator:
        result = result | node
    return result


def test_spec_preserves_terminal_data_for_lexers() -> None:
    TestSyntax = Syntax.config(token_class=TokenClass.simple())
    literal = TestSyntax.literal
    identifier = TestSyntax.token(text="id", token_type="IDENT")

    grammar = (literal("a") + identifier) | literal("b")

    builders = _collect_terminal_builders(grammar.spec)
    seen = {(builder.text, builder.tag) for builder in builders}

    assert seen == {("a", None), ("id", "IDENT"), ("b", None)}


def test_spec_can_drive_left_recursion_elimination() -> None:
    TestSyntax = Syntax.config(token_class=TokenClass.simple())
    literal = TestSyntax.literal

    Expr = TestSyntax.lazy(lambda: (Expr + literal("+") + literal("n")) | literal("n"))  # type: ignore[name-defined]

    assert _grammar_is_left_recursive(Expr.spec)

    root_spec = Expr.spec
    inner = root_spec.spec() if isinstance(root_spec, LazySpec) else root_spec
    alternatives = _flatten_choices(inner)

    recursive_alts = [alt for alt in alternatives if _is_left_recursive(alt, root_spec)]
    base_alts = [alt for alt in alternatives if not _is_left_recursive(alt, root_spec)]

    assert recursive_alts, "Expected at least one left-recursive alternative"
    assert base_alts, "Expected at least one non-left-recursive alternative"

    base_nodes = [_rehydrate(TestSyntax, alt) for alt in base_alts]
    base_syntax = base_nodes[0] if len(base_nodes) == 1 else _or_all(base_nodes)

    suffix_nodes = [
        _rehydrate(TestSyntax, _strip_left_recursion(alt, root_spec)) for alt in recursive_alts
    ]
    suffix_choice = suffix_nodes[0] if len(suffix_nodes) == 1 else _or_all(suffix_nodes)

    transformed = base_syntax + suffix_choice.many().optional()

    original_ast, _ = parse_word(Expr, "n + n + n")
    transformed_ast, _ = parse_word(transformed, "n + n + n")

    assert _flatten_token_text(original_ast) == ["n", "+", "n", "+", "n"]
    assert _flatten_token_text(transformed_ast) == ["n", "+", "n", "+", "n"]
    assert not _grammar_is_left_recursive(transformed.spec)