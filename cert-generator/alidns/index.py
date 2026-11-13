# -*- coding: utf-8 -*-

import os

from alibabacloud_alidns20150109.client import Client as Alidns20150109Client
from alibabacloud_alidns20150109 import models as alidns_20150109_models
from darabonba.runtime import RuntimeOptions
from aliyun_config import get_config


def get_challenge_domain():
    domain = os.environ.get("CERTBOT_DOMAIN") or os.environ["DEVS_DOMAIN"]
    return domain.lower().rstrip(".").removeprefix("*.")


def get_domain_rr(domain_name=None):
    domain = get_challenge_domain()
    zone = domain_name or get_domain_name()
    if domain == zone:
        return "_acme-challenge"
    if not domain.endswith("." + zone):
        raise ValueError("Challenge domain does not belong to the AliDNS zone")
    return "_acme-challenge." + domain[:-(len(zone) + 1)]


def get_domain_name():
    response = get_client().get_main_domain_name_with_options(
        alidns_20150109_models.GetMainDomainNameRequest(
            input_string=get_challenge_domain()
        ),
        runtime,
    )
    zone = response.body.domain_name
    if not zone:
        raise ValueError("AliDNS did not return a main domain name")
    return zone.lower().rstrip(".")


def check_if_valid_domain():
    get_client().describe_domain_info_with_options(
        alidns_20150109_models.DescribeDomainInfoRequest(domain_name=get_domain_name()),
        runtime,
    )


def insert_rr(domainName, rr):
    get_client().add_domain_record_with_options(
        alidns_20150109_models.AddDomainRecordRequest(
            domain_name=domainName,
            rr=rr,
            type="TXT",
            value=os.environ["CERTBOT_VALIDATION"],
        ),
        runtime,
    )


def delete_rr(record_id):
    get_client().delete_domain_record_with_options(
        alidns_20150109_models.DeleteDomainRecordRequest(record_id=record_id), runtime
    )


def update_rr(record_id, rr):
    get_client().update_domain_record_with_options(
        alidns_20150109_models.UpdateDomainRecordRequest(
            record_id=record_id,
            rr=rr,
            type="TXT",
            value=os.environ["CERTBOT_VALIDATION"],
        ),
        runtime,
    )


def get_domain_record_id(domainName, rr):
    records = get_client().describe_domain_records_with_options(
        alidns_20150109_models.DescribeDomainRecordsRequest(
            domain_name=domainName, type_key_word="TXT", rrkey_word=rr
        ),
        runtime,
    )
    record_id = None
    for record in records.body.domain_records.record or []:
        if record.rr == rr and record.type == "TXT":
            record_id = record.record_id
            break
    return record_id


def get_alidns_endpoint():
    if os.environ.get("FC_REGION") == "ap-southeast-1":
        return "alidns.ap-southeast-1.aliyuncs.com"
    else:
        return "alidns.cn-hangzhou.aliyuncs.com"


runtime = RuntimeOptions()

def get_client():
    return Alidns20150109Client(get_config(get_alidns_endpoint()))
