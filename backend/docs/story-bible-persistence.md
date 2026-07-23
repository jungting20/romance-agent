# Story Bible Persistence

## Snapshot schema compatibility

Story Bible JSON persistence reads the legacy schema version 1 and writes schema
version 2. Reading a v1 snapshot is compatibility-only and does not rewrite the
file. The next successful Story Bible persistence operation writes the complete
snapshot as v2 and increments the Story Bible revision according to that
operation's contract.

The v1 character shape contains `id`, `name`, `role`, `desire`, and
`hiddenFeeling`. Its `role` must remain exactly `protagonist`, preserving the v1
invariant. During decoding, v2 fields absent from v1 (`gender`, `age`,
`personality`, `proseStyle`, and `dialogueStyle`) become empty strings. Existing
v1 values are otherwise preserved.

The v2 encoder always writes every character field. The v2 decoder requires the
exact v2 envelope and nested object keys and applies the current Story Bible
domain invariants. Unsupported schema versions, malformed JSON, extra or missing
keys, invalid legacy roles, invalid field types, duplicate identifiers, and
other corrupt values are persistence errors. A corrupt or unsupported snapshot
must never be partially decoded, automatically repaired, or overwritten as a
side effect of reading it.
