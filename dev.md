## Testing

Run the regex fuzz test:


```bash
pytest -q tests/test_regex.py -k test_fuzzing
```

To reproduce a fuzz failure, set a fixed seed:

```bash
SYNCRAFT_REGEX_FUZZ_SEED=12345 pytest -q tests/test_regex.py -k test_fuzzing
```

TODO
- [ ]  Interactive parse tree visualizer
- [ ]  Static analysis tool
