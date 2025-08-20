# Syncraft

Syncraft is a parser/generator combinator library with full round-trip support:

- Parse source code into AST or dataclasses
- Generate source code from dataclasses
- Bidirectional transformations via lenses
- Convenience combinators: `all`, `first`, `last`, `named`
- SQLite syntax support included

## Installation

```bash
pip install syncraft
```


## TODO
- [ ] Add a collect method to AST to collect all named entries and pack them into a dict or a custom dataclass. This method will be called as the last step of my current bimap. So it shares the signature of bimap and can combine with the current bimap
- [ ] Amend all, first, last, and named helper functions to support bimap and named results.
- [ ] Try the parsing, generation, and data processing machinery on SQLite3 syntax. So that I can have direct feedback on the usability of this library and a fully functional SQLite3 library.
- [ ] Make the library as fast as possible and feasible.