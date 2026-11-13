"""Use FC role credentials for each invocation and environment credentials for hooks."""

import os

from alibabacloud_tea_openapi.utils_models import Config


def configure_credentials(context):
    credentials = getattr(context, "credentials", None)
    if credentials is None:
        return
    for attribute, variable in (
        ("access_key_id", "ALIBABA_CLOUD_ACCESS_KEY_ID"),
        ("access_key_secret", "ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        ("security_token", "ALIBABA_CLOUD_SECURITY_TOKEN"),
    ):
        value = getattr(credentials, attribute, None)
        if value:
            os.environ[variable] = value
        elif attribute == "security_token":
            os.environ.pop(variable, None)
    region = getattr(context, "region", None)
    if region:
        os.environ["FC_REGION"] = region


def get_config(endpoint):
    return Config(
        access_key_id=os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"],
        access_key_secret=os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"],
        security_token=os.environ.get("ALIBABA_CLOUD_SECURITY_TOKEN"),
        endpoint=endpoint,
        read_timeout=1000000,
        connect_timeout=1000000,
    )
