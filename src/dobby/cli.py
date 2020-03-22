import sys
import time
from importlib.metadata import version

import click

from . import formatter, templates, utils
from .config import Config

CONTEXT_SETTINGS = {"help_option_names": ["-help"]}


class GlobalExceptionHandler(click.Group):
    def __call__(self, *args, **kwargs):
        try:
            return self.main(*args, **kwargs)
        except utils.ApiError as e:
            status, text = e.response.status_code, e.response.text
            click.secho(
                f"API call failed with status code {status} and message:\n\n{text}",
                fg="red",
                err=True,
            )
        else:
            raise
        sys.exit(1)


def common_args(f):
    path_type = click.Path(
        exists=True, allow_dash=True, file_okay=True, dir_okay=False, resolve_path=True
    )
    click.argument("input", type=path_type)(f)
    click.option("-var-file", "var_files", type=path_type, default=[], multiple=True,)(
        f
    )
    return f


@click.group(cls=GlobalExceptionHandler, context_settings=CONTEXT_SETTINGS)
@click.option(
    "-address",
    envvar="NOMAD_ADDR",
    default="http://127.0.0.1:4646",
    help="Nomad server to connect to.",
)
@click.option(
    "-region",
    envvar="NOMAD_REGION",
    help="The region of the Nomad servers to forward commands to.",
)
@click.option(
    "-namespace",
    envvar="NOMAD_NAMESPACE",
    help="The target namespace for queries and actions bound to a namespace.",
)
@click.option(
    "-ca-cert",
    envvar="NOMAD_CACERT",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to a PEM encoded CA cert file to use to verify the Nomad server SSL certificate.",
)
@click.option(
    "-ca-path",
    envvar="NOMAD_CAPATH",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to a directory of PEM encoded CA cert files to verify the Nomad server SSL certificate.",
)
@click.option(
    "-client-cert",
    envvar="NOMAD_CLIENT_CERT",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to a PEM encoded client certificate for TLS authentication to the Nomad server.",
)
@click.option(
    "-client-key",
    envvar="NOMAD_CLIENT_KEY",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to an unencrypted PEM encoded private key matching the client certificate from -client-cert.",
)
@click.option(
    "-token",
    envvar="NOMAD_TOKEN",
    help="The SecretID of an ACL token to use to authenticate API requests with.",
)
@click.option(
    "-tls-skip-verify",
    is_flag=True,
    envvar="NOMAD_SKIP_VERIFY",
    default=False,
    help="Do not verify TLS certificate. This is highly not recommended.",
)
@click.version_option(version("dobby"), "-version")
@click.pass_context
def cli(ctx, **kwargs):
    """Dobby deploys (Jinja-)templated jobs to nomad"""
    ctx.obj = Config(**kwargs)


@cli.command()
@click.option("-verbose", is_flag=True, default=False)
@click.option("-detach", is_flag=True, default=False)
@common_args
# @click.option("--strict", is_flag=True, default=False)
@click.pass_obj
@click.pass_context
def deploy(ctx, config, input, verbose, detach, var_files, strict=True):
    """Deploy a job"""
    job_spec = templates.render(input, var_files)
    job = config.parse_hcl_or_exit(job_spec)

    result = {"Job": job, "Diff": True}
    response = config.client.put(f"/v1/job/{job['ID']}/plan", json=result)

    if response.status_code != 200:
        raise utils.ApiError(response)

    data = response.json()
    diff = data["Diff"]
    if diff:
        click.secho("Planned changes:\n", bold=True)
        click.echo(formatter.format_job_diff(diff, verbose), nl=False)

    click.secho("Scheduler dry-run:", bold=True)
    click.echo(formatter.format_dry_run(data, job), nl=False)

    if data["FailedTGAllocs"] and strict:
        click.secho("\nAborting execution due to failed allocations.", fg="red")
        ctx.exit(1)

    response = config.client.put(
        "/v1/jobs",
        json={
            "Job": job,
            "JobModifyIndex": data["JobModifyIndex"],
            "EnforceIndex": True,
        },
    )
    if response.status_code != 200:
        raise utils.ApiError(response)

    if detach:
        click.secho("\nJob submitted to Nomad successfully.", fg="green", bold=True)
        ctx.exit()

    data = response.json()
    click.secho("\nJob Submission:", bold=True)
    if monitor_job(config, data["EvalID"]):
        click.secho("\nJob deployment finished succesfully.", fg="green", bold=True)
    else:
        click.secho("\nJob deployment failed.", fg="red", bold=True)
        click.exit(1)


@cli.command()
@common_args
@click.pass_obj
def validate(config, input, var_files):
    """Validate a job specification"""
    job_spec = templates.render(input, var_files)
    job = config.parse_hcl_or_exit(job_spec)

    response = config.client.post("/v1/validate/job", json={"Job": job})
    if response.status_code == 200:
        response = response.json()
        errors = response["Error"]
        warnings = response["Warnings"]
        separating_nl = "\n" if errors and warnings else ""
        if warnings:
            click.secho(f"{warnings}{separating_nl}", fg="yellow", err=True)
        if errors:
            click.secho(errors, fg="red", err=True)
            sys.exit(1)
        separating_nl = "\n" if warnings else ""
        click.secho(f"{separating_nl}Validated job spec successfully!", fg="green")
    else:
        raise utils.ApiError(response)


@cli.command()
@common_args
@click.pass_obj
def render(config, input, var_files):
    """Render a template to stdout"""
    print(templates.render(input, var_files))


def monitor_job(config, eval_id, deployment_id=None):
    click.echo(f"- Monitoring evaluation {repr(eval_id)}.")
    while deployment_id is None:
        response = config.client.get(f"/v1/evaluation/{eval_id}")
        if response.status_code != 200:
            raise utils.ApiError(response)
        eval = response.json()
        status = eval["Status"]

        if status in ("failed", "cancelled"):
            click.echo(f"Evaluation failed: {eval['StatusDescription']}")
            return False
        elif status == "complete":
            if eval.get("NextEval", None):
                eval_id = eval["NextEval"]
                click.echo(f"- Monitoring evaluation {repr(eval_id)}.")
            elif eval.get("DeploymentID", None):
                deployment_id = eval["DeploymentID"]
            else:
                click.echo(
                    "- Job has been scheduled, but there is no deployment to monitor.",
                )
                return True
        else:
            time.sleep(3)
            continue

    click.echo(f"- Evaluation {repr(eval_id)} completed successfully.")
    click.echo(f"- Monitoring deployment {repr(deployment_id)}.")
    while True:
        response = config.client.get(f"/v1/deployment/{deployment_id}")
        if response.status_code != 200:
            raise utils.ApiError(response)
        deployment = response.json()
        status = deployment["Status"]

        if status in ("failed", "cancelled"):
            click.echo(f"Deployment failed: {eval['StatusDescription']}")
            return False
        elif status == "successful":
            click.echo(f"- Deployment {repr(deployment_id)} completed successfully.")
            return True
        else:
            time.sleep(3)
            continue
