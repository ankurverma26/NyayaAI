# NyayaAI Project Rules & Conventions

## Naming Conventions
- **Files, folders, functions, variables, and JSON/API fields**: Use `snake_case`.
- **Classes and React components**: Use `PascalCase`.
- **Statute files** in `data/laws/`: Named like `indian_contract_act_1872.json`.
- **short_name**: UPPERCASE with enactment year without separator, e.g. `ICA1872`, `ITA2000`, `ACA1996`, `CA2013`, `SRA1963`.
- **Section numbers**: Always strings (`"27"`, `"43A"`), never integers.
- **Citations**: Display format is `"{short_name} s.{section_number}"`, e.g. `"ICA1872 s.27"`.

## Ingestion & Schema Rules
- Loader ignores any top-level key starting with `_` (e.g. `_schema_notes`).
- Files containing `"sample_format"` in their name are skipped by seed loaders.
- Supported statute statuses: `in_force`, `amended`, `repealed`, `draft`, `verify_current_status`.
- Optional fields: `retrieved_on` (YYYY-MM-DD) on legal source, `notes` (string) on sections.
- Idempotency: Section text is hash-checked; updated if modified, preserved if unchanged.
