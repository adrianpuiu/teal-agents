import logging
import nest_asyncio

from fastapi import FastAPI
from pydantic_yaml import parse_yaml_file_as
from ska_utils import AppConfig, get_telemetry, initialize_telemetry

from sk_agents.appv1 import AppV1
from sk_agents.appv2 import AppV2
from sk_agents.configs import (
    TA_SERVICE_CONFIG,
    configs,
)
from sk_agents.middleware import TelemetryMiddleware
from sk_agents.ska_types import (
    BaseConfig,
)

logging.basicConfig(level=logging.INFO)

nest_asyncio.apply()
AppConfig.add_configs(configs)
app_config = AppConfig()

config_file = app_config.get(TA_SERVICE_CONFIG.env_name)
config: BaseConfig = parse_yaml_file_as(BaseConfig, config_file)

(root_handler, api_version) = config.apiVersion.split("/")

name: str | None = None
version = str(config.version)

is_v2 = False
if api_version == "v2alpha1":
    is_v2 = True
    name = config.name
else:
    name = config.service_name

if not name:
    raise ValueError("Service name is not defined in the configuration file.")
if not version:
    raise ValueError("Service version is not defined in the configuration file.")

initialize_telemetry(f"{name}-{version}", app_config)

app = FastAPI(
    openapi_url=f"/{name}/{version}/openapi.json",
    docs_url=f"/{name}/{version}/docs",
    redoc_url=f"/{name}/{version}/redoc",
)
# noinspection PyTypeChecker
app.add_middleware(TelemetryMiddleware, st=get_telemetry())

if is_v2:
    AppV2.run(name, version, app_config, config, app)
else:
    AppV1.run(name, version, app_config, config, app)
