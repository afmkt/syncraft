Build a parser for key/value pairs.

Rules:
- key: identifier `[A-Za-z_][A-Za-z0-9_]*`
- value: integer `[0-9]+` or quoted string `"[^"]*"`
- pair format: `key : value`
- optional whitespace around colon

Examples:
- `count:42`
- `name : "mike"`
