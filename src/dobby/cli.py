import sys
import time

import click

from . import formatter, templates, utils

try:
    from importlib.metadata import version
except ModuleNotFoundError:
    from importlib_metadata import version


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(cls=utils.Group, context_settings=CONTEXT_SETTINGS)
@click.version_option(version("dobby"), "--version", "-v")
def cli():
    """Dobby deploys (Jinja-)templated jobs to nomad"""


@cli.command()
@utils.connectivity_options
@utils.template_options
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Provide a verbose output of the planned changes.",
)
@click.option(
    "--detach",
    "-d",
    is_flag=True,
    default=False,
    help="Do not wait for the deployment to finish and quit after submission.",
)
@utils.pass_config
@click.pass_context
def deploy(ctx, config, input, verbose, detach, var_files, strict=True):
    """Deploy a job to Nomad after templating it."""
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
@utils.connectivity_options
@utils.template_options
@utils.pass_config
def validate(config, input, var_files):
    """Validate a job specification."""
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
@utils.template_options
def render(input, var_files):
    """Render a template to stdout."""
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


def main():
    return cli.main(prog_name="dobby", max_content_width=220)
