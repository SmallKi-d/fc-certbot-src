# -*- coding: utf-8 -*-
import os
import time

from alidns.index import (
    get_domain_record_id,
    update_rr,
    insert_rr,
    get_domain_rr,
    get_domain_name,
)

domainName = get_domain_name()
rr = get_domain_rr(domainName)

record_id = get_domain_record_id(domainName, rr)

if record_id:
    update_rr(record_id, rr)
    print("dns record updated.")
else:
    insert_rr(domainName, rr)
    print("dns record added.")

# Allow authoritative DNS updates to propagate before Certbot asks the CA to validate.
time.sleep(float(os.environ.get("CERTBOT_DNS_PROPAGATION_SECONDS", "30")))
