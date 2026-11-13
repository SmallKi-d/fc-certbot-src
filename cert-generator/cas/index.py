# -*- coding: utf-8 -*-
import random
import string

from pathlib import Path
from crypto_utils import load_rsa_private_key
from alibabacloud_cas20200407.client import Client as cas20200407Client
from alibabacloud_cas20200407 import models as cas_20200407_models
from darabonba.runtime import RuntimeOptions
from aliyun_config import get_config


def get_cert_name(domainName, certName):
    if certName is None:
        if domainName.startswith("*."):
            tokens = domainName.split(".")
            return (
                "devs-certbot-generated-w-"
                + str(len(tokens))
                + "-"
                + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
            )
        else:
            return "devs-certbot-generated-" + "".join(
                random.choices(string.ascii_lowercase + string.digits, k=8)
            )
    else:
        return certName


def upload_cert(certPath, keyPath, domainName, certName, certId):
    cert = Path(certPath).read_text()
    key = load_rsa_private_key(keyPath)
    if certId is not None:
        delete_cert(certId)
        print("delete old certificate first.")
    upload_user_certificate_request = cas_20200407_models.UploadUserCertificateRequest(
        name=get_cert_name(domainName, certName), cert=cert, key=key
    )
    newCert = get_client().upload_user_certificate_with_options(
        upload_user_certificate_request, runtime
    )
    return cert, key, newCert.body.cert_id


def get_cert_by_name(certName):
    client = get_client()
    current_page = 1
    show_size = 1000
    stop = False
    while not stop:
        out = client.list_user_certificate_order_with_options(
            cas_20200407_models.ListUserCertificateOrderRequest(
                order_type="UPLOAD", show_size=show_size, current_page=current_page
            ),
            runtime,
        )
        for cert in out.body.certificate_order_list or []:
            if cert.name == certName:
                certDetail = client.get_user_certificate_detail_with_options(
                    cas_20200407_models.GetUserCertificateDetailRequest(
                        cert_id=cert.certificate_id
                    ),
                    runtime,
                )
                return certDetail.body
        if out.body.total_count <= current_page * show_size:
            stop = True
        else:
            current_page += 1
    return None


def delete_cert(cert_id):
    get_client().delete_user_certificate_with_options(
        cas_20200407_models.DeleteUserCertificateRequest(cert_id=cert_id), runtime
    )


def get_cas_endpoint():
    return "cas.aliyuncs.com"


runtime = RuntimeOptions()

def get_client():
    return cas20200407Client(get_config(get_cas_endpoint()))
