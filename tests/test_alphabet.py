from syncraft.alphabet import Alphabet, CodepointError
from enum import Enum
def test_alphabet_codepoint_error():
    """Test that CodepointError is raised for invalid codepoints in Alphabet."""
    alphabet = Alphabet(str)
    invalid_codepoints = [-1, 0x110000, 'ab', None]

    for cp in invalid_codepoints:
        try:
            alphabet.encode(cp)
        except CodepointError as e:
            print(f"Correctly raised CodepointError for codepoint {cp}: {e}")
        else:
            assert False, f"CodepointError was not raised for invalid codepoint {cp}"


def test_alphabet_decode_error():
    """Test that CodepointError is raised for invalid codes in Alphabet."""
    alphabet = Alphabet(str)
    invalid_codes = [-1, 0xFFFFFFFF, None]

    for code in invalid_codes:
        try:
            alphabet.decode(code)
        except CodepointError as e:
            print(f"Correctly raised CodepointError for code {code}: {e}")
        else:
            assert False, f"CodepointError was not raised for invalid code {code}"


def test_finite_alphabet_codepoint_error():
    """Test that CodepointError is raised for invalid symbols in FiniteAlphabet."""
    symbols = ['a', 'b', 'c']
    alphabet = Alphabet.finite(symbols)

    invalid_symbols = ['d', 1, None]

    for sym in invalid_symbols:
        try:
            alphabet.encode(sym)
        except CodepointError as e:
            print(f"Correctly raised CodepointError for symbol {sym}: {e}")
        else:
            assert False, f"CodepointError was not raised for invalid symbol {sym}"


def test_finite_alphabet_decode_error():
    """Test that CodepointError is raised for invalid codes in FiniteAlphabet."""
    class MyEnum(Enum):
        A = 0
        B = 1
        
    alphabet = Alphabet.finite(MyEnum)

    invalid_codes = [-1, 3, 100]

    for code in invalid_codes:
        try:
            alphabet.decode(code)
        except CodepointError as e:
            print(f"Correctly raised CodepointError for code {code}: {e}")
        else:
            assert False, f"CodepointError was not raised for invalid code {code}"