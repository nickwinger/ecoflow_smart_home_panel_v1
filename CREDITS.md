# Credits and licenses

Project code: nickwinger, under the [MIT license](LICENSE).

The owner's [working Python implementation](https://github.com/nickwinger/homeassistant_config/tree/main/ecoflow)
is the reference for signing, quota reads, source/charge payloads and batch
semantics. Only the `ecoflow/` directory is authoritative. The separate
`pyscript/shp_mode.py` is obsolete and is not the switching reference.
The pinned unchanged script in `tests/reference/` is test-only and is never part
of the HACS-installed integration.

Home Assistant supplies native entities, configuration, scheduling, history and
notifications. HACS supplies installation and repository validation. Paho MQTT
is installed as a dependency; it is not vendored. Dependencies and test tools
retain their own licenses.

The supplied manufacturer HTML references and property supplement retain their
authors' copyrights. Community sources support attributed field facts and
interpretations; the project MIT license does not relicense those documents or
third-party projects. [Detailed sources and pinned revisions](docs/REFERENCE_SOURCES.md).

Local brand assets belong to this project's presentation. EcoFlow and Smart Home
Panel are their owners' trademarks; this project has no official affiliation.
