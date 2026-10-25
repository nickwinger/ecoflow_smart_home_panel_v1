"""Constants for the EcoFlow Smart Home Panel v1 custom integration."""

DOMAIN = "ecoflow_smart_home_panel_v1"
NAME = "EcoFlow Smart Home Panel v1"
DEFAULT_POLL_INTERVAL_SECONDS = 60
MIN_POLL_INTERVAL_SECONDS = 30
MAX_POLL_INTERVAL_SECONDS = 900
CONF_ACCESS_KEY = "access_key"
CONF_SECRET_KEY = "secret_key"
CONF_SERIAL = "serial"
CONF_REGION = "region"
CONF_POLL_INTERVAL = "poll_interval"
CONF_CONFIRM_V1 = "confirm_v1"
HOSTS = {"eu": "https://api-e.ecoflow.com", "global": "https://api.ecoflow.com"}
