# json-formatter

Compact-friendly JSON formatter. Short values stay on one line; large structures expand. No dependencies.

```bash
# format in place
python3 format-json.py file.json

# write to a new file
python3 format-json.py file.json -o out.json

# stdin → stdout
cat file.json | python3 format-json.py

# load options from a config file (CLI args override)
python3 format-json.py -c fmt.toml file.json

# custom indent and line length
python3 format-json.py --indent 4 --max-line 80 file.json

# always inline a specific nested array
python3 format-json.py --always-inline '$.entities[*].ruleIds' file.json
```

## Options

| Option | Default | Values | Description |
|---|---|---|---|
| `--indent N` | `2` | integer | Indent spaces |
| `--max-line N` | `120` | integer | Max line length before expanding |
| `--array-items MODE` | `uniform` | `uniform` | All items expand if any single item doesn't fit |
| | | `smart` | Each item decides independently |
| | | `expand` | Always expand |
| | | `inline` | Always try one line |
| `--always-inline PATH` | — | JSONPath | Force-inline this array (repeat for multiple) |
| `--always-expand PATH` | — | JSONPath | Force-expand this array (repeat for multiple) |
| `-c / --config FILE` | — | `.json` `.toml` | Load defaults from file; CLI args override |


## Config file

```toml
# fmt.toml — requires Python 3.11+ or: pip install tomli
indent = 2
max_line = 120
array_items = "uniform"
always_inline = ["$.entities[*].ruleIds"]
always_expand = ["$.content.entities"]
```

## JSONPath patterns

| Segment | Meaning |
|---|---|
| `$` | root of the document |
| `.key` | object property named `key` |
| `[*]` | every element of an array |

`$.entities[*].ruleIds` — the `ruleIds` array inside every element of the top-level `entities` array.  
`$.content.rules` — the `rules` object/array directly under `content` at the root.

## License

MIT

## Tests

```bash
pip install pytest
python3 -m pytest tests/
```
