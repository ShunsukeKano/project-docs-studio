# db-automation-apply

The DDL for the database, saved as numbered SQL files.

- `001_schema.sql`: tables, constraints, triggers and indexes.
- Apply the files in numeric order, with the owner (migration) role, never with the application role.
- Apply to the **development** or **test** database while working. Apply to production only through the deployment (the migration Job).
- Add a new numbered file for each schema change. Do not edit a file that has already been applied.
- Keep `docs/nextjs-fastapi-architecture.html` (section 7) in step with these files; if they disagree, the SQL here is the source of truth.
