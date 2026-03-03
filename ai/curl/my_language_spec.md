Build a parser for: <LANGUAGE_NAME>

Goal:
- Parse source text into structured values using Syncraft regex++ grammar.
- Keep grammar deterministic and practical for roundtrip workflows.

Input model:
- Input is plain text (Unicode).
- Newlines are significant? <yes/no>
- Comments supported? <none | line | block | both>

Lexical rules:
- identifier: `[A-Za-z_][A-Za-z0-9_]*`
- integer: `[0-9]+`
- string: `"[^"\\]*(?:\\.[^"\\]*)*"`
- whitespace: `[ \t\r\n]+`

Keywords/operators (customize):
- keywords: `<kw1>`, `<kw2>`, `<kw3>`
- operators: `=`, `+`, `-`, `*`, `/`, `(`, `)`, `{`, `}`, `,`, `;`

Grammar requirements:
1. Start rule: `<start_rule_name>`
2. Statements:
   - `<stmt_form_1>`
   - `<stmt_form_2>`
3. Expressions:
   - precedence levels (high to low):
     - primary: literals, identifiers, parenthesized expr
     - unary: `+` / `-` (optional)
     - multiplicative: `*` `/`
     - additive: `+` `-`
4. Optional features:
   - trailing commas? <yes/no>
   - optional semicolons? <yes/no>

Transformation requirements:
- Parse identifiers as strings.
- Parse numeric literals to Python `int`.
- Preserve operator tokens as strings.
- Result shape for each nonterminal:
  - `<nonterminal_a>` -> `<expected_python_shape>`
  - `<nonterminal_b>` -> `<expected_python_shape>`

Error behavior:
- Reject invalid tokens.
- Reject malformed nesting.
- Reject missing required separators.

Examples (must pass):
1. Input:
   <example_1_input>
   Expected:
   <example_1_expected_python_repr>

2. Input:
   <example_2_input>
   Expected:
   <example_2_expected_python_repr>

3. Input:
   <example_3_input>
   Expected:
   <example_3_expected_python_repr>

Negative examples (must fail):
1. <bad_input_1>
2. <bad_input_2>

Output constraints for generated code:
- Return Python code only.
- Use `Syntax.rp` as primary style.
- Expose top-level variable: `grammar`.
- Keep rules modular and readable (`ident`, `number`, `expr`, etc.).
- Prefer explicit lambdas/functions for `.map(...)`.
