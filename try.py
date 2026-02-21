from typing import Type

import pytest

from syncraft.regex import parse


def test():
    x = parse(r'\\d{2,}\\U000F44C9{2}\\U000AA4AB{1,5}[Av]*|(?b)|$')
    print(x)



if __name__ == "__main__":
    test()