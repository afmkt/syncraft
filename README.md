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
- [ ] simplify the result of then_left and then_right by bimap the result in syntax.
- [ ] simplify the result of sep_by and between by bimap the result in syntax
- [ ] Try the parsing, generation, and data processing machinery on SQLite3 syntax. So that I can have direct feedback on the usability of this library and a fully functional SQLite3 library.
- [ ] Make the library as fast as possible and feasible.