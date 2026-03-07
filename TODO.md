TODO

## Now (high value)
- [ ] Static analyzer for grammar/DX diagnostics
- [ ] Interactive parse tree visualizer for parse/debug experience
- [ ] Streaming parsing test/debug toolkit (tests + trace helpers + examples)
- [ ] Remove `rstr` dependency

## Next (clarify and de-risk)
- [ ] LSP-from-grammar feasibility spike (scope, architecture, minimal prototype)
- [ ] Grammar modularization design spike (module boundaries, imports, composition APIs)
- [ ] Document and test "parallel parsing" guarantees (thread/process safety matrix)

## Later (platform/ecosystem)
- [ ] Integrate `Tracer` performance profile into parse tree visualizer
- [ ] Export Grammar/Syntax to EBNF/BNF/Yacc
- [ ] AI assistant for writing grammar rules (web-based assistant, not a full editor)
- [ ] Bidirectional constraints mini-framework (generalize `Not` in `bimap.py`)

## Testing & Validation scope (clarification)
- Library development: correctness/performance/regression tests for Syncraft internals
- Grammar development with Syncraft: optional helper toolkit (roundtrip/property/fuzz checks for user grammars)
