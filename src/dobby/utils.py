import inspect
import sys
from functools import update_wrapper

import click
from httpx import NetworkError
from jinja2.exceptions import TemplateSyntaxError, UndefinedError

from .config import Config


class ApiError(Exception):
    def __init__(self, response):
        self.response = response


def hcl_to_json(config, hcl):
    response = config.client.post("/v1/jobs/parse", json={"JobHCL": hcl})

    if response.status_code == 200:
        return response.json()
    else:
        raise ApiError(response)


class ConnectivityOption(click.Option):
    pass


class Command(click.Command):
    def __init__(self, *args, **kwargs):
        kwargs["epilog"] = (
            "For convenience and similarity with the Nomad CLI it is possible to "
            "replace the initial double dash from options with a single dash."
        )
        super().__init__(*args, **kwargs)

    def format_options(self, ctx, formatter):
        conn_opts = []
        command_opts = []
        for param in self.get_params(ctx):
            rv = param.get_help_record(ctx)
            opts = conn_opts if isinstance(param, ConnectivityOption) else command_opts
            if rv is not None:
                opts.append(rv)

        if conn_opts:
            with formatter.section("Connectivity Options"):
                formatter.write_dl(conn_opts)

        if command_opts:
            with formatter.section("Command Options"):
                formatter.write_dl(command_opts)

    def make_parser(self, ctx):
        class Parser(click.OptionParser):
            def add_option(self, opts, *args, **kwargs):
                opts = list(opts)
                for opt in opts:
                    if opt.startswith("--"):
                        opts.append(opt[1:])
                super().add_option(opts, *args, **kwargs)

        parser = Parser(ctx)
        for param in self.get_params(ctx):
            param.add_to_parser(parser, ctx)
        return parser


class Group(click.Group):
    def main(self, *args, **kwargs):
        nl = "\n"
        try:
            return super().main(*args, **kwargs)
        except ApiError as e:
            status, text = e.response.status_code, e.response.text
            click.secho(
                f"API call failed with status code {status} and message:\n\n{text}",
                fg="red",
                err=True,
            )
        except NetworkError as e:
            click.secho(f"Network-error: {e.args[0]}", fg="red", err=True)
        except TemplateSyntaxError as e:
            click.secho(f"Template parsing failed: {e.message}{nl}", fg="red", err=True)
            raise
        except UndefinedError as e:
            click.secho(
                f"Template rendering failed: {e.message}{nl}", fg="red", err=True
            )
            raise

        sys.exit(1)

    def command(self, *args, **kwargs):
        kwargs["cls"] = Command
        return super().command(*args, **kwargs)

    def make_parser(self, ctx):
        return Command.make_parser(self, ctx)


def connectivity_options(f):
    shared = {
        "show_envvar": True,
        "cls": ConnectivityOption,
    }
    args = [
        click.option(
            "--address",
            envvar="NOMAD_ADDR",
            default="http://127.0.0.1:4646",
            help="Nomad server to connect to.",
            metavar="URL",
            show_default=True,
            **shared,
        ),
        click.option(
            "--region",
            envvar="NOMAD_REGION",
            help="The region of the Nomad servers to forward commands to.",
            **shared,
        ),
        click.option(
            "--namespace",
            envvar="NOMAD_NAMESPACE",
            help="The target namespace for queries and actions bound to a namespace.",
            **shared,
        ),
        click.option(
            "--ca-cert",
            envvar="NOMAD_CACERT",
            type=click.Path(exists=True, file_okay=True, dir_okay=False),
            help="Path to a PEM encoded CA cert file to use to verify the Nomad server SSL certificate.",
            **shared,
        ),
        click.option(
            "--ca-path",
            envvar="NOMAD_CAPATH",
            type=click.Path(exists=True, file_okay=False, dir_okay=True),
            help="Path to a directory of PEM encoded CA cert files to verify the Nomad server SSL certificate.",
            **shared,
        ),
        click.option(
            "--client-cert",
            envvar="NOMAD_CLIENT_CERT",
            type=click.Path(exists=True, file_okay=True, dir_okay=False),
            help="Path to a PEM encoded client certificate for TLS authentication to the Nomad server.",
            **shared,
        ),
        click.option(
            "--client-key",
            envvar="NOMAD_CLIENT_KEY",
            type=click.Path(exists=True, file_okay=True, dir_okay=False),
            help="Path to an unencrypted PEM encoded private key matching the client certificate from -client-cert.",
            **shared,
        ),
        click.option(
            "--tls-server-name",
            envvar="NOMAD_TLS_SERVER_NAME",
            help="The server name to use as the SNI host when connecting via TLS.",
            **shared,
        ),
        click.option(
            "--tls-skip-verify",
            is_flag=True,
            envvar="NOMAD_SKIP_VERIFY",
            default=False,
            help="Do not verify TLS certificate. This is highly not recommended.",
            **shared,
        ),
        click.option(
            "--token",
            envvar="NOMAD_TOKEN",
            help="The SecretID of an ACL token to use to authenticate API requests with.",
            **shared,
        ),
    ]
    for arg in args[::-1]:
        arg(f)
    return f


def template_options(f):
    path_type = click.Path(
        exists=True, allow_dash=False, file_okay=True, dir_okay=False, resolve_path=True
    )
    args = [
        click.option(
            "--var-file",
            "var_files",
            type=path_type,
            default=[],
            multiple=True,
            help="The variable file (.env/.json/.yaml) to render the template with. Can be specified multiple times.",
        ),
        click.argument("input", type=path_type),
    ]
    for arg in args[::-1]:
        arg(f)
    return f


def pass_config(f):
    config_initargs = inspect.signature(Config).parameters.keys()

    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        config_values = {}
        for arg in config_initargs:
            config_values[arg] = kwargs.pop(arg)
        client_cert = config_values["client_cert"]
        client_key = config_values["client_key"]
        if any([client_cert, client_key]) and not all([client_cert, client_key]):
            ctx.fail("-client-cert requires -client-key (and vice versa).")
        return f(Config(**config_values), *args, **kwargs)

    return update_wrapper(new_func, f)
