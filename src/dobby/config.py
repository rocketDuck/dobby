import ssl
import sys
from pathlib import Path
from urllib.parse import urlparse

import click
import httpx
from httpx._config import DEFAULT_CIPHERS

from . import utils


class NomadSSLContext(ssl.SSLContext):
    def set_hostname(self, hostname):
        self._hostname = hostname

    def wrap_socket(self, *args, **kwargs):
        kwargs["server_hostname"] = self._hostname
        return super().wrap_socket(*args, **kwargs)


class Config:
    def __init__(
        self,
        address,
        region,
        namespace,
        ca_cert,
        ca_path,
        client_cert,
        client_key,
        tls_server_name,
        tls_skip_verify=False,
        token=None,
    ):
        headers = {}
        if token:
            headers["X-Nomad-Token"] = token

        params = {}
        if region:
            params["region"] = region
        if namespace:
            params["namespace"] = namespace

        verify = self.ssl_context(
            ca_cert or ca_path, client_cert, client_key, tls_skip_verify
        )
        verify.set_hostname(tls_server_name or urlparse(address).hostname)

        self.client = httpx.Client(
            base_url=address, headers=headers, params=params, verify=verify
        )

    def ssl_context(
        self, ca_bundle, client_cert=None, client_key=None, tls_skip_verify=False,
    ):
        context = NomadSSLContext(ssl.PROTOCOL_TLS)
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        context.options |= ssl.OP_NO_TLSv1
        context.options |= ssl.OP_NO_TLSv1_1
        context.options |= ssl.OP_NO_COMPRESSION
        context.set_ciphers(DEFAULT_CIPHERS)

        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True

        if ca_bundle:
            ca_bundle = Path(ca_bundle)
            if ca_bundle.is_file():
                context.load_verify_locations(cafile=str(ca_bundle))
            elif ca_bundle.is_dir():
                context.load_verify_locations(capath=str(ca_bundle))
        else:
            context.load_default_certs(ssl.Purpose.SERVER_AUTH)

        if tls_skip_verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        if client_cert and client_key:
            context.load_cert_chain(client_cert, client_key)
        return context

    def parse_hcl_or_exit(self, job_spec):
        try:
            return utils.hcl_to_json(self, job_spec)
        except utils.ApiError as e:
            if e.response.status_code == 400:
                click.secho(e.response.text, fg="red")
                sys.exit(1)
            else:
                raise
