TODO

## Now (high value)
- [ ] Static analyzer for grammar/DX diagnostics
- [ ] Interactive parse tree visualizer for parse/debug experience

## Next (clarify and de-risk)
- [ ] LSP-from-grammar feasibility spike (scope, architecture, minimal prototype)
- [ ] Grammar modularization design spike (module boundaries, imports, composition APIs)

## Later (platform/ecosystem)
- [ ] Integrate `Tracer` performance profile into parse tree visualizer
- [ ] AI assistant for writing grammar rules (web-based assistant, not a full editor)
- [ ] Add Grammar.from_ebnf to load EBNF to Grammar with named Syntax as its fields

## Testing & Validation scope (clarification)
- Library development: correctness/performance/regression tests for Syncraft internals
- Grammar development with Syncraft: optional helper toolkit (roundtrip/property/fuzz checks for user grammars)
