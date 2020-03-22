import ssl
import sys

import click
import httpx

from . import utils


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
            ca_cert, ca_path, client_cert, client_key, tls_skip_verify
        )
        self.client = httpx.Client(
            base_url=address, headers=headers, params=params, verify=verify
        )

    def ssl_context(
        self,
        ca_cert=None,
        ca_path=None,
        client_cert=None,
        client_key=None,
        tls_skip_verify=False,
    ):
        context = ssl.create_default_context(cafile=ca_cert, capath=ca_path)
        if tls_skip_verify:
            context.verify_mode = ssl.CERT_NONE
            context.check_hostname = False
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
