from syncraft.fa import FABuilder, NFA, DFA
from syncraft.charset import CodeUniverse

def test_literal_builder():
    builder = FABuilder.literal("abc", tag="ID")
    assert builder.kind.name == "LITERAL"
    assert builder.text == "abc"
    assert builder.tag == "ID"

def test_oneof_builder():
    builder = FABuilder.oneof("xyz", tag="CHARSET")
    assert builder.kind.name == "ONEOF"
    assert builder.text == "xyz"
    assert builder.tag == "CHARSET"

def test_concat_union_and_subtract():
    a = FABuilder.literal("a")
    b = FABuilder.literal("b")
    concat = a + b
    union = a | b
    intersect = a & b
    diff = a - b
    assert concat.kind.name == "CONCAT"
    assert union.kind.name == "UNION"
    assert intersect.kind.name == "INTERSECT"
    assert diff.kind.name == "DIFF"

def test_star_plus_optional_many():
    a = FABuilder.literal("x")
    star = a.star
    plus = a.plus
    optional = ~a
    many = a.many(at_least=2, at_most=5)
    assert star.kind.name == "STAR"
    assert plus.kind.name == "CONCAT"  
    assert optional.kind.name == "OPTIONAL"
    assert many.kind.name == "MANY"
    assert many.at_least == 2
    assert many.at_most == 5

def test_tagging():
    a = FABuilder.literal("foo")
    tagged = a.tagged("FOO")
    assert tagged.tag == "FOO"

def test_compile_to_nfa():
    universe = CodeUniverse.ascii()
    builder = FABuilder.literal("abc", tag="ID")
    nfa = builder.compile(universe)
    # Should be an NFA and accept 'abc'
    assert isinstance(nfa, (NFA, DFA))  
    assert hasattr(nfa, 'runner')
    assert callable(getattr(nfa, 'runner', None))


def test_literal_values_detect_text_universe() -> None:
    builder: FABuilder[str] = FABuilder.lit("hi") + FABuilder.lit("bye")
    assert builder.payload_kind == "text"


def test_literal_values_detect_bytes_universe() -> None:
    builder: FABuilder[bytes] = FABuilder.lit(b"x") | FABuilder.lit(b"y")
    assert builder.payload_kind == "bytes"
