import re
from syncraft import Syntax

grammar = (
    Syntax.rp(r'^\s*(\d+)\s*(?:,\s*(\d+)\s*)*$')
    .map(lambda s: tuple(map(int, re.findall(r'\d+', s))))
    .to(lambda t: ','.join(map(str, t)))
)
