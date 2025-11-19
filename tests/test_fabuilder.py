from syncraft.fa import Builder, NFA, DFA
from syncraft.alphabet import Alphabet

def test_literal_builder():
    builder = Builder.lit("abc", tag="ID")
    assert builder.kind.name == "LITERAL"
    assert builder.text == "abc"
    assert builder.tag == "ID"

def test_oneof_builder():
    builder = Builder.oneof("xyz", tag="CHARSET")
    assert builder.kind.name == "ONEOF"
    assert builder.text == "xyz"
    assert builder.tag == "CHARSET"

def test_concat_union_and_subtract():
    a = Builder.lit("a")
    b = Builder.lit("b")
    concat = a + b
    union = a | b
    intersect = a & b
    diff = a - b
    assert concat.kind.name == "CONCAT"
    assert union.kind.name == "UNION"
    assert intersect.kind.name == "INTERSECT"
    assert diff.kind.name == "DIFF"

def test_star_plus_optional_many():
    a = Builder.lit("x")
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
    a = Builder.lit("foo")
    tagged = a.tagged("FOO")
    assert tagged.tag == "FOO"

def test_compile_to_nfa():
    alphabet = Alphabet(str)
    builder = Builder.lit("abc", tag="ID")
    nfa = builder.compile(alphabet)
    # Should be an NFA and accept 'abc'
    assert isinstance(nfa, (NFA, DFA))  
    assert hasattr(nfa, 'runner')
    assert callable(getattr(nfa, 'runner', None))


def test_literal_values_detect_text_universe() -> None:
    builder: Builder[str] = Builder.lit("hi") + Builder.lit("bye")
    assert builder.alphabet == Alphabet(str)


def test_literal_values_detect_bytes_universe() -> None:
    builder: Builder[bytes] = Builder.lit(b"x") | Builder.lit(b"y")
    assert builder.alphabet == Alphabet(bytes)
