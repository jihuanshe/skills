---
name: using-logfire
description: 'Logfire MCP tools reference. Triggers: need to query traces, exceptions, or run SQL on Logfire.'
metadata:
  version: '1'
---

# Logfire Skill

## Available Tools

- `find_exceptions_in_file` - Get the details about the 10 most recent exceptions on the file.
- `arbitrary_query` - Run an arbitrary query on the Pydantic Logfire database. The SQL reference is available via the `sql_reference` tool.
- `logfire_link` - Creates a link to help the user to view the trace in the Logfire UI.
- `schema_reference` - The database schema for the Logfire DataFusion database.
