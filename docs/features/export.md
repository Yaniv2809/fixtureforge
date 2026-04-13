# Streaming & Export

## Export Formats

```python
from fixtureforge.core.exporter import DataExporter

users = forge.create_batch(User, count=100)

DataExporter.to_json(users, "users.json")
DataExporter.to_csv(users, "users.csv")
DataExporter.to_sql(users, "users.sql", table_name="users")
```

---

## Streaming

For datasets too large to hold in memory, use `create_stream()`:

```python
for user in forge.create_stream(User, count=1_000_000, filename="users.json"):
    pass  # one record at a time — constant memory usage
```

Each record is written to disk immediately. Memory usage stays flat regardless of count.

Supported formats: `.json`, `.csv`, `.sql`

---

## ForgeDataset

`ForgeDataset` wraps large results with automatic disk-spill:

- Results under 50,000 characters are kept in memory
- Larger results are written to a temp file; a 2,000-character preview is kept in memory

```python
dataset = forge.create_dataset(User, count=10_000)
print(dataset.preview())    # first 2K chars
full = dataset.load()       # load from disk
dataset.save("users.json")  # save to path
```

---

## Large Dataset Mode

```python
# seed_ratio=0.01 — AI generates 1% of records
# the rest are interpolated deterministically
# Cost: ~1,000 AI records. Delivered: 100,000 records.
forge.create_large(Order, count=100_000, seed_ratio=0.01)
```
