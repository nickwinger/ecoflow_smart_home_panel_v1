# Read-only batch reference

`shp_mode.py.txt` is the owner's unchanged working script from
[`nickwinger/homeassistant_config` at `3fa58b227ea5bd9e1a605ebb7177ab002a2a6e10`](https://github.com/nickwinger/homeassistant_config/blob/3fa58b227ea5bd9e1a605ebb7177ab002a2a6e10/ecoflow/shp_mode.py).
Git blob: `5b409c05f51ae15c3fe5f8c32826bf877894eadb`.

It contains code only, no credentials or device data. The reference repository
was not modified. This copy is used only by offline comparison tests and is not
installed with the integration. Original authorship remains with the owner.

Tests verify the blob hash and load selected function/constant AST nodes only.
Imports, logging configuration and the command-line entry point are never run.
GET, PUT, cache access, logging and sleep are injected memory-only substitutes.
The actual reference functions and native async controller then run against the
same synthetic scenarios; their complete GET/PUT/delay traces must match.
