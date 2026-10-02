# Project Conventions & Naming Rules

## Naming Rules
- **Files, folders, functions, variables, and JSON/API fields**: Use `snake_case`.
- **Classes and React components**: Use `PascalCase`.
- **Statute files** in `data/laws/`: Named with lowercase snake_case and year, e.g. `indian_contract_act_1872.json`, `specific_relief_act_1963.json`.
- **short_name**: UPPERCASE with enactment year without separator, e.g. `ICA1872`, `ITA2000`, `ACA1996`, `CA2013`, `SRA1963`.
- **Section numbers**: Always strings (e.g. `"27"`, `"43A"`, `"Schedule II"`), never integers.
- **Citations**: Display format is `"{short_name} s.{section_number}"`, e.g. `"ICA1872 s.27"`, `"ACA1996 s.7"`.

## Statutory Corpus & Ingestion Rules
- Statutory texts must be verbatim from official sources (India Code).
- Any top-level JSON key starting with `_` (e.g. `_schema_notes`) is ignored by loaders.
- Supported statute status values: `in_force`, `amended`, `repealed`, `draft`, `verify_current_status`.
- Optional fields supported: `retrieved_on` (YYYY-MM-DD) on the act/source, and `notes` (string) on each section.
