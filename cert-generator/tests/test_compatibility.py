import datetime
import importlib.metadata
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

with mock.patch.dict(os.environ, {
    "ALIBABA_CLOUD_ACCESS_KEY_ID": "test-access-key",
    "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "test-secret",
}, clear=True):
    import alidns.index as dns
    import cas.index as cas
    import index as app

from crypto_utils import load_rsa_private_key
from aliyun_config import configure_credentials


class CredentialsTests(unittest.TestCase):
    def test_each_invocation_refreshes_clients_and_hook_environment(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            for token in ("first-token", "second-token"):
                context = SimpleNamespace(
                    credentials=SimpleNamespace(
                        access_key_id="role-key", access_key_secret="role-secret",
                        security_token=token,
                    ), region="ap-southeast-1",
                )
                configure_credentials(context)
                self.assertEqual(os.environ["ALIBABA_CLOUD_SECURITY_TOKEN"], token)
                self.assertEqual(cas.get_client()._credential.get_credential().security_token, token)
                self.assertEqual(dns.get_client()._endpoint, "alidns.ap-southeast-1.aliyuncs.com")

    def test_import_without_credentials(self):
        import subprocess
        with mock.patch.dict(os.environ, {}, clear=True):
            subprocess.run([
                sys.executable, "-S", "-c",
                "import sys; sys.path[:0] = " + repr(sys.path) + "; import index",
            ], check=True, capture_output=True)


class DependencyTests(unittest.TestCase):
    def test_requested_versions(self):
        for name, version in {
            "certbot": "5.10.0",
            "acme": "5.10.0",
            "alibabacloud-cas20200407": "3.9.5",
            "alibabacloud-alidns20150109": "4.6.1",
            "cryptography": "50.0.2",
            "PyOpenSSL": "26.4.0",
        }.items():
            with self.subTest(name=name):
                self.assertEqual(importlib.metadata.version(name), version)


class SdkTestCase(unittest.TestCase):
    def setUp(self):
        with mock.patch.dict(os.environ, {
            "ALIBABA_CLOUD_ACCESS_KEY_ID": "test-access-key",
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "test-secret",
        }):
            self.cas_client = cas.get_client()
            self.dns_client = dns.get_client()
        for module, client in ((cas, self.cas_client), (dns, self.dns_client)):
            patcher = mock.patch.object(module, "get_client", return_value=client)
            patcher.start()
            self.addCleanup(patcher.stop)


class CryptoTests(SdkTestCase):
    @classmethod
    def setUpClass(cls):
        cls.rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def test_pkcs8_and_pkcs1_keep_same_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "privkey.pem"
            for key_format in (
                serialization.PrivateFormat.PKCS8,
                serialization.PrivateFormat.TraditionalOpenSSL,
            ):
                with self.subTest(key_format=key_format):
                    path.write_bytes(self.rsa_key.private_bytes(
                        serialization.Encoding.PEM, key_format, serialization.NoEncryption()
                    ))
                    result = load_rsa_private_key(path)
                    self.assertTrue(result.startswith("-----BEGIN RSA PRIVATE KEY-----"))
                    restored = serialization.load_pem_private_key(result.encode(), None)
                    self.assertEqual(restored.private_numbers(), self.rsa_key.private_numbers())

    def test_invalid_or_ec_key_does_not_delete_existing_certificate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "cert.pem").write_text("test certificate")
            ec_key = ec.generate_private_key(ec.SECP256R1()).private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
            for contents in (b"invalid key", ec_key):
                (path / "key.pem").write_bytes(contents)
                with mock.patch.object(cas, "delete_cert") as delete:
                    with self.assertRaises(ValueError):
                        cas.upload_cert(path / "cert.pem", path / "key.pem", "example.com", "test", 1)
                    delete.assert_not_called()

    def test_upload_uses_new_sdk_response_and_converted_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "cert.pem").write_text("test full chain")
            (path / "key.pem").write_bytes(self.rsa_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ))
            response = {
                "body": {"CertId": 123, "RequestId": "test"},
            }
            with mock.patch.object(self.cas_client, "call_api", return_value=response) as upload:
                cert, key, cert_id = cas.upload_cert(
                    path / "cert.pem", path / "key.pem", "example.com", "test", None
                )
            self.assertEqual(cert_id, 123)
            params, request, runtime = upload.call_args.args
            self.assertEqual(params.action, "UploadUserCertificate")
            self.assertEqual(request.query["Name"], "test")
            self.assertEqual(request.query["Cert"], cert)
            self.assertEqual(request.query["Key"], key)
            self.assertIsInstance(runtime, cas.RuntimeOptions)
            self.assertTrue(key.startswith("-----BEGIN RSA PRIVATE KEY-----"))


class DnsTests(SdkTestCase):
    def test_root_subdomain_and_wildcard(self):
        for zone in ("example.com", "ruituedu.com.cn", "example.co.uk"):
            for prefix, expected in {
                "": "_acme-challenge",
                "*.": "_acme-challenge",
                "www.": "_acme-challenge.www",
                "*.sub.": "_acme-challenge.sub",
            }.items():
                domain = prefix + zone
                with self.subTest(domain=domain), mock.patch.dict(os.environ, {"DEVS_DOMAIN": domain}, clear=True), mock.patch.object(
                    self.dns_client, "call_api", return_value={"body": {"DomainName": zone}}
                ) as api:
                    self.assertEqual(dns.get_domain_name(), zone)
                    self.assertEqual(dns.get_domain_rr(zone), expected)
                    self.assertEqual(api.call_count, 1)
                    self.assertEqual(api.call_args.args[0].action, "GetMainDomainName")
                    self.assertEqual(api.call_args.args[1].query["InputString"], domain.removeprefix("*."))

    def test_certbot_domain_takes_precedence(self):
        with mock.patch.dict(os.environ, {"CERTBOT_DOMAIN": "sub.example.com"}, clear=True):
            self.assertEqual(dns.get_domain_rr("example.com"), "_acme-challenge.sub")

    def test_domain_validation_uses_full_main_domain(self):
        with mock.patch.dict(os.environ, {"DEVS_DOMAIN": "ruituedu.com.cn"}, clear=True), mock.patch.object(
            self.dns_client, "call_api", side_effect=[
                {"body": {"DomainName": "ruituedu.com.cn"}},
                {"body": {"DomainName": "ruituedu.com.cn"}},
            ]
        ) as api:
            dns.check_if_valid_domain()
        self.assertEqual(api.call_args.args[0].action, "DescribeDomainInfo")
        self.assertEqual(api.call_args.args[1].query["DomainName"], "ruituedu.com.cn")

    def test_unrelated_zone_is_rejected(self):
        with mock.patch.dict(os.environ, {"DEVS_DOMAIN": "ruituedu.com.cn"}, clear=True):
            with self.assertRaisesRegex(ValueError, "does not belong"):
                dns.get_domain_rr("example.com")

    def test_txt_lookup_ignores_other_record_types(self):
        response = {
            "body": {"DomainRecords": {"Record": [
                {"RR": "_acme-challenge", "Type": "CNAME", "RecordId": "other"},
                {"RR": "_acme-challenge", "Type": "TXT", "RecordId": "txt-id"},
            ]}},
        }
        with mock.patch.object(self.dns_client, "call_api", return_value=response) as describe:
            self.assertEqual(dns.get_domain_record_id("example.com", "_acme-challenge"), "txt-id")
        params, request, runtime = describe.call_args.args
        self.assertEqual(params.action, "DescribeDomainRecords")
        self.assertEqual(request.query["RRKeyWord"], "_acme-challenge")
        self.assertIsInstance(runtime, dns.RuntimeOptions)

    def test_dns_mutations_use_new_sdk_runtime(self):
        with mock.patch.dict(os.environ, {"CERTBOT_VALIDATION": "test-value"}), mock.patch.object(
            self.dns_client, "call_api", return_value={"body": {"RecordId": "42"}}
        ) as api:
            dns.insert_rr("example.com", "_acme-challenge")
            dns.update_rr("42", "_acme-challenge")
            dns.delete_rr("42")
        self.assertEqual([call.args[0].action for call in api.call_args_list], [
            "AddDomainRecord", "UpdateDomainRecord", "DeleteDomainRecord",
        ])
        self.assertEqual(api.call_args_list[0].args[1].query["Value"], "test-value")


class CasTests(SdkTestCase):
    def test_paginated_search_uses_certificate_id_for_detail(self):
        responses = [{
            "body": {"TotalCount": 1001, "CertificateOrderList": records},
        } for records in (
            [{"Name": "other", "CertificateId": 1}],
            [{"Name": "wanted", "CertificateId": 42}],
        )]
        detail_response = {
            "body": {"Id": 42, "Common": "example.com", "EndDate": "2026-01-01"},
        }
        with mock.patch.object(self.cas_client, "call_api", side_effect=responses + [detail_response]) as api:
            self.assertEqual(cas.get_cert_by_name("wanted").id, 42)
        self.assertEqual([call.args[1].query["CurrentPage"] for call in api.call_args_list[:2]], ["1", "2"])
        self.assertEqual(api.call_args.args[0].action, "GetUserCertificateDetail")
        self.assertEqual(api.call_args.args[1].query["CertId"], "42")


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {
            "CERTBOT_EMAIL": "admin@example.com",
            "CERTBOT_CONFIG_DIR": "/tmp/certbot test/config",
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_success_uses_current_interpreter_and_direct_pem_paths(self):
        with mock.patch.object(app, "check_if_valid_domain"), mock.patch.object(
            app.certbot.main, "main", return_value=None
        ) as certbot, mock.patch.object(app, "upload_cert", return_value=("cert", "key", 123)) as upload:
            self.assertEqual(app.handler(json.dumps({"domainName": "example.com"}).encode(), None), 123)
        args = certbot.call_args.args[0]
        hook = shlex.split(args[args.index("--manual-auth-hook") + 1])
        self.assertEqual(hook[2], sys.executable)
        self.assertTrue(Path(hook[3]).is_file())
        self.assertEqual(args[args.index("--email") + 1], "admin@example.com")
        self.assertEqual(upload.call_args.args[:2], (
            Path("/tmp/certbot test/config/live/example.com/fullchain.pem"),
            Path("/tmp/certbot test/config/live/example.com/privkey.pem"),
        ))

    def test_certbot_failure_never_uploads_stale_certificate(self):
        for result in (1, "issuance failed"):
            with self.subTest(result=result), mock.patch.object(app, "check_if_valid_domain"), mock.patch.object(
                app.certbot.main, "main", return_value=result
            ), mock.patch.object(app, "upload_cert") as upload:
                with self.assertRaisesRegex(RuntimeError, "Certbot failed"):
                    app.handler({"domainName": "example.com"}, None)
                upload.assert_not_called()

    def test_missing_email_is_reported_before_dns_or_acme_calls(self):
        os.environ.pop("CERTBOT_EMAIL")
        with mock.patch.object(app, "check_if_valid_domain") as dns_check, mock.patch.object(
            app.certbot.main, "main"
        ) as certbot:
            with self.assertRaisesRegex(ValueError, "CERTBOT_EMAIL"):
                app.handler({"domainName": "example.com"}, None)
            dns_check.assert_not_called()
            certbot.assert_not_called()

    def test_non_expiring_certificate_is_reused(self):
        cert = cas.cas_20200407_models.GetUserCertificateDetailResponseBody(
            common="example.com", id=42,
            end_date=(datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
        )
        with mock.patch.object(app, "get_cert_by_name", return_value=cert), mock.patch.object(
            app.certbot.main, "main"
        ) as certbot:
            self.assertEqual(app.handler({"domainName": "example.com", "certName": "test"}, None), 42)
            certbot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
