# -*- coding: utf-8 -*-
import json
import certbot.main
import os
import datetime
import shlex
import sys
from pathlib import Path
from cas.index import upload_cert, get_cert_by_name
from alidns.index import check_if_valid_domain
from aliyun_config import configure_credentials


def check_if_less_than_seven_days(x):
    d = datetime.datetime.strptime(x, "%Y-%m-%d")
    now = datetime.datetime.now()
    return (d - now).days < 7


def handler(event, context):
    configure_credentials(context)
    evt = event if isinstance(event, dict) else json.loads(event)
    domainName = evt.get("domainName")
    if domainName is not None:
        if domainName.startswith("https://") or domainName.startswith("http://"):
            domainName = domainName.split("://")[1]
        os.environ["DEVS_DOMAIN"] = domainName
    certName = evt.get("certName")
    certificate_id = None
    if certName is not None:
        cert = get_cert_by_name(certName)
        if cert is not None:
            if cert.common != domainName:
                raise Exception("domainName and cert common name do not match")
            if check_if_less_than_seven_days(cert.end_date):
                certificate_id = cert.id
            else:
                print("Cert will not expire in 7 days")
                return cert.id
    if domainName is None:
        raise Exception("no domainName provided")
    email = os.environ.get("CERTBOT_EMAIL")
    if not email:
        raise ValueError("Set CERTBOT_EMAIL to your ACME account email")
    check_if_valid_domain()
    project_dir = Path(__file__).resolve().parent
    config_dir = Path(os.environ.get("CERTBOT_CONFIG_DIR", "/tmp/letsencrypt/config"))
    hook_pythonpath = os.pathsep.join(
        [str(project_dir / "python"), str(project_dir), os.environ.get("PYTHONPATH", "")]
    )

    def hook_command(script):
        return shlex.join(
            ["env", "PYTHONPATH=" + hook_pythonpath, sys.executable, str(project_dir / script)]
        )

    certbot_args = [
        "certonly",
        "--manual",
        "--quiet",
        "--non-interactive",
        "--agree-tos",
        "--manual-auth-hook",
        hook_command("authenticator.py"),
        "--manual-cleanup-hook",
        hook_command("cleanup.py"),
        "--config-dir",
        str(config_dir),
        "--work-dir",
        os.environ.get("CERTBOT_WORK_DIR", "/tmp/letsencrypt/work"),
        "--logs-dir",
        os.environ.get("CERTBOT_LOGS_DIR", "/tmp/letsencrypt/logs"),
        "--preferred-challenges",
        "dns",
        "--key-type",
        "rsa",
        "--cert-name",
        domainName,
        "--email",
        email,
        "--server",
        os.environ.get("CERTBOT_SERVER", "https://acme-v02.api.letsencrypt.org/directory"),
        "--domains",
        domainName,
    ]
    result = certbot.main.main(certbot_args)
    if result not in (None, 0):
        raise RuntimeError("Certbot failed: {}".format(result))
    print("cert generated")
    cert_dir = config_dir / "live" / domainName
    cert, key, cert_id = upload_cert(
        cert_dir / "fullchain.pem",
        cert_dir / "privkey.pem",
        domainName,
        certName,
        certificate_id,
    )
    print("cert uploaded to cas successfully")
    return cert_id
