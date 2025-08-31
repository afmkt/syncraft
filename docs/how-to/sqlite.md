# SQLite parsing

```python
from syncraft import parse
from syncraft.sqlite3 import select_stmt

ast, _ = parse(select_stmt, "select a from t where a > 1", dialect="sqlite")
```

Use `sqlglot()` to map tokens to sqlglot expressions if needed.
