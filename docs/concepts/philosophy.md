# Philosophy

## 1. One source of truth

Parsing, generation, and validation should come from a single grammar model.

If you define a language once, you should not need:
- a parser,
- a transformer,
- a serializer,
- and a separate validator.

A single definition should unify all directions.  
Roundtripping should fall out of the model, not be manually maintained.

---

## 2. Shape matters

A parsing library should deliver results in the shape the user actually wants.

Not:
- raw parse trees,
- intermediate ASTs that require post-processing,
- or mandatory visitor passes.

Transformation is not an afterthought — it is part of the grammar definition.  
Grammars describe both structure *and* meaning.

---

## 3. CFGs should feel like regex

Context-free grammars shouldn’t feel heavier than regular expressions.

If you can sketch a regex, you should be able to sketch a recursive grammar just as quickly.

`Syntax.rp` exists to make recursive grammar fragments feel as lightweight and composable as regex — without giving up context-free power.
