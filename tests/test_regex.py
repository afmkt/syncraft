from __future__ import annotations
import pytest
from syncraft.regex import (
    parse, verify,
    literal, anchor, shorthand,atom, dot, quantifier, char_class, group, piece, branch, regex_syntax,
    LiteralAtom, AnchorAtom, AnchorKind, ShorthandAtom, ShorthandKind, DotAtom, Quantifier, 
    CharClassAtom, CharRange, GroupAtom, GroupKind, UnicodeCategoryAtom, Regex, Piece, Branch
)
from syncraft.algebra import Error
import random
import string
import re



    
def random_literal():
    chars = string.ascii_letters + string.digits + "_"
    return random.choice(chars)

def random_quantifier():
    return random.choice(["", "?", "*", "+", "{%d}" % random.randint(1, 5),
                          "{%d,%d}" % (random.randint(0, 2), random.randint(3, 6)),
                          "{%d,}" % random.randint(1, 4)])

def random_shorthand():
    return random.choice(["\\d", "\\D", "\\w", "\\W", "\\s", "\\S"])

def random_anchor():
    return random.choice(["^", "$", "\\b", "\\B", "\\A", "\\Z"])

def random_unicode_escape():
    return random.choice([
        "\\x%02X" % random.randint(0, 255),
        "\\u%04X" % random.randint(0, 0xFFFF),
        "\\U%08X" % random.randint(0, 0x10FFFF),
    ])

def random_class():
    content = "".join(random.choice(string.ascii_letters) for _ in range(random.randint(2, 5)))
    if random.random() < 0.3:
        content = "^" + content
    if random.random() < 0.5:
        content += random.choice(["\\d", "\\s", "\\w"])
    return f"[{content}]"

def random_group(depth=0):
    """Recursively generate nested group structure."""
    if depth > 2:
        return random_atom(depth)
    group_type = random.choice(["()", "(?:)", "(?=)", "(?!)", "(?<=)", "(?<!)"])
    inner = "".join(random_atom(depth + 1) for _ in range(random.randint(1, 3)))
    return group_type[:2] + inner + group_type[-1]

def random_atom(depth=0) -> str:
    atom_type = random.choice(["literal", "shorthand", "class", "unicode", "group", "anchor", "dot"])
    if atom_type == "literal":
        return random_literal() + random_quantifier()
    elif atom_type == "shorthand":
        return random_shorthand() + random_quantifier()
    elif atom_type == "class":
        return random_class() + random_quantifier()
    elif atom_type == "unicode":
        return random_unicode_escape() + random_quantifier()
    elif atom_type == "group":
        return random_group(depth)
    elif atom_type == "anchor":
        return random_anchor()
    elif atom_type == "dot":
        return "." + random_quantifier()
    raise ValueError("Unknown atom type")

def random_branch():
    return "".join(random_atom() for _ in range(random.randint(1, 4)))

def random_regex():
    branches = [random_branch() for _ in range(random.randint(1, 3))]
    return "|".join(branches)

def generate_random_regex_tests(n=100, seed=42) -> list[tuple[str, str, bool]]:
    random.seed(seed)
    tests = []
    for i in range(n):
        pattern = random_regex()
        tests.append((f"fuzz_valid_{i}", pattern, True))

    # Add a few random invalid ones
    invalids = [
        r"[abc", r"(?P<name>", r"{,3}", r"(?!)", r"\p{}", r"(?z)", r"(abc", r"\\",
        r"(?P<1bad>a)", r"\u12", r"{3,2}", r"(?i", r"(?:", r"[a-z", r"(?<=a", r"(?<!a"
    ]
    for i, pattern in enumerate(invalids):
        tests.append((f"fuzz_invalid_{i}", pattern, False))

    return tests



# @pytest.mark.xfail(reason="Comprehensive regex tests are disabled for now.")
def test_literal_quantifiers():
    TEST_CASES = [
        # 1. Basic literals and quantifiers
        ("literal_a", r"a", True),
        ("concat_abc", r"abc", True),
        ("quantifier_optional", r"a?", True),
        ("quantifier_star", r"a*", True),
        ("quantifier_plus", r"a+", True),
        ("quantifier_exact", r"a{3}", True),
        ("quantifier_range", r"a{2,5}", True),
        ("quantifier_minimum", r"a{2,}", True),
        ("quantifier_maximum_only", r"a{,5}", True),     # invalid in Python but valid stress test
        ("lazy_star", r"a*?", True),
        ("non_capturing_repeat", r"(?:ab)*", True),
    ] 

    for name, pattern, should_pass in TEST_CASES:
        vr = verify(pattern)
        assert vr.ok, f"Pattern failed to parse: {pattern}\nSyncraft Error: {vr.err_syncraft}\nRe Error: {vr.err_re}"


def test_alternation_grouping():
    TEST_CASES = [
        # 2. Alternation and grouping
        ("alternation_simple", r"a|b|c", True),
        ("alternation_in_group", r"(a|b)c", True),
        ("noncapturing_alt", r"(?:foo|bar)", True),
        ("nested_grouping", r"((ab)|(cd))+", True),
        ("named_group", r"(?P<word>[A-Za-z_]\w*)", True),
    ]

    for name, pattern, should_pass in TEST_CASES:
        vr = verify(pattern)
        assert vr.ok, f"Pattern failed to parse: {pattern}\nSyncraft Error: {vr.err_syncraft}\nRe Error: {vr.err_re}"


def test_character_classes():
    TEST_CASES = [

        # 3. Character classes
        ("class_basic", r"[abc]", True),
        ("class_negated", r"[^abc]", True),
        ("class_range", r"[a-z]", True),
        ("class_mixed_range", r"[A-Za-z0-9_]", True),
        ("class_shorthand", r"[\w\d]", True),
        ("class_meta_chars", r"[\^\]-]", True),
        ("class_square_brackets", r"[][]", True),
        ("class_leading_rsquare", r"[]a]", True),
        ("class_control_escapes", r"[\t\n\r\f\v]", True),
        ("class_unicode_range", r"[\u00A9-\u00B1]", True),
        ("class_unicode_category", r"[\p{Lu}\p{Ll}]", True),

    ]

    for name, pattern, should_pass in TEST_CASES:
        vr = verify(pattern)
        assert vr.ok, f"Pattern failed to parse: {pattern}\nSyncraft Error: {vr.err_syncraft}\nRe Error: {vr.err_re}"


def test_anchors_boundaries():
    TEST_CASES = [
        # 4. Anchors and boundaries
        ("anchor_line", r"^abc$", True),
        ("boundary_word", r"\bword\b", True),
        ("boundary_nonword", r"\Bfoo\B", True),
        ("anchor_absolute_start", r"\Astart", True),
        ("anchor_absolute_end", r"end\Z", True),
    ]
    for name, pattern, should_pass in TEST_CASES:
        vr = verify(pattern)
        assert vr.ok, f"Pattern failed to parse: {pattern}\nSyncraft Error: {vr.err_syncraft}\nRe Error: {vr.err_re}"

def test_shorthands_unicode_escape():
    TEST_CASES = [

        # 5. Shorthands and Unicode escapes
        ("shorthands_basic", r"\d+\s*\w*", True),
        ("shorthands_negated", r"\D\S\W", True),
        ("unicode_hex_pair", r"\x41", True),
        ("unicode_quad", r"\u03B1", True),
        ("unicode_octa", r"\U0001F600", True),
        ("unicode_named", r"\N{LATIN SMALL LETTER A}", True),
        ("unicode_category_upper", r"\p{Lu}", True),
        ("unicode_category_non_digit", r"\P{Nd}", True),
    ]
    for name, pattern, should_pass in TEST_CASES:
        vr = verify(pattern)
        assert vr.ok, f"Pattern failed to parse: {pattern}\nSyncraft Error: {vr.err_syncraft}\nRe Error: {vr.err_re}"

def test_lookaround():
    TEST_CASES = [

        # 6. Lookaround assertions
        ("lookahead_positive", r"(?=foo)", True),
        ("lookahead_negative", r"(?!bar)", True),
        ("lookbehind_positive", r"(?<=baz)", True),
        ("lookbehind_negative", r"(?<!qux)", True),
        ("nested_lookahead", r"(?:(?=a)b)*", True),
    ]
    for name, pattern, should_pass in TEST_CASES:
        vr = verify(pattern)
        assert vr.ok, f"Pattern failed to parse: {pattern}\nSyncraft Error: {vr.err_syncraft}\nRe Error: {vr.err_re}"

def test_inline_flags():
    TEST_CASES = [
        # 7. Inline flags
        ("flag_case_insensitive", r"(?i)abc", True),
        ("flag_multiple", r"(?imx)pattern", True),
        ("flag_scoped", r"(?i:abc)", True),
        ("flag_all", r"(?aLmsux)", True),
        ("flag_disable", r"(?-i)a", True),
    ]
    for name, pattern, should_pass in TEST_CASES:
        vr = verify(pattern)
        assert vr.ok, f"Pattern failed to parse: {pattern}\nSyncraft Error: {vr.err_syncraft}\nRe Error: {vr.err_re}"

def test_complex():
    TEST_CASES = [

        # 8. Complex real-world examples
        ("email_pattern", r"(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", True),
        ("float_pattern", r"(?:(?:\+|-)?\d+(?:\.\d+)?)(?:e[+-]?\d+)?", True),
        ("ssn_like", r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)", True),
        ("comment_line_multiline", r"(?m)^(?:#.*|$)", True),
        ("cli_flag", r"(?:(?<=\s)|^)-{1,2}[A-Za-z0-9_-]+", True),
        ("quoted_string", r"(?:(?P<quote>['\"])(?:(?!\1).)*\1)", True),
        ('fuzzing', r'.E?|\B\w?(?.{2,3}.)\s{1,5}', True),
        
    ]
    for name, pattern, should_pass in TEST_CASES:
        vr = verify(pattern)
        assert vr.ok, f"Pattern failed to parse: {pattern}\nSyncraft Error: {vr.err_syncraft}\nRe Error: {vr.err_re}"

def test_malform():
    TEST_CASES = [
        # 9. Malformed or edge cases (should fail)
        ("invalid_named_group", r"(?P<1name>a)", False),
        ("invalid_flag", r"(?z)", False),
        ("empty_unicode_category", r"\p{}", False),
        ("unclosed_group", r"(", False),
        ("unclosed_class", r"[abc", False),
        ("invalid_quantifier_range", r"{3,2}", False),
        ("incomplete_hex", r"\x4", False),
        ("unclosed_named_group", r"(?P<name>", False),
    ]

    for name, pattern, should_pass in TEST_CASES:
        vr = verify(pattern)
        assert vr.ok, f"Pattern failed to parse: {pattern}\nSyncraft Error: {vr.err_syncraft}\nRe Error: {vr.err_re}"

def test_fuzzing_collection():
    TEST_CASES = [
        ("fuzzing", r".{3}|\w{1}(?\ZH?)^\w", True),
    ]
    for name, pattern, should_pass in TEST_CASES:
        vr = verify(pattern)
        assert vr.ok, f"Pattern failed to parse: {pattern}\nSyncraft Error: {vr.err_syncraft}\nRe Error: {vr.err_re}"

def test_fuzzing():
    TEST_CASES = generate_random_regex_tests(200, seed=random.randint(0, 2**32 - 1))

    for name, pattern, should_pass in TEST_CASES:
        vr = verify(pattern)
        pattern = ("fuzzing",pattern, should_pass)
        assert vr.ok, f"Pattern failed to parse: {pattern}\nSyncraft Error: {vr.err_syncraft}\nRe Error: {vr.err_re}"




