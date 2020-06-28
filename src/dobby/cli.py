import sys
import time

import click

from . import formatter, templates, utils

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(cls=utils.Group, context_settings=CONTEXT_SETTINGS)
@click.version_option(None, "--version", "-v")
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

    data = plan_job(ctx, config, job, verbose)

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
    success, deployment_id = monitor_evaluation(config, data["EvalID"])
    if success and deployment_id:
        success = monitor_deployment(config, deployment_id)
    if success:
        click.secho("\nJob deployment finished succesfully.", fg="green", bold=True)
    else:
        click.secho("\nJob deployment failed.", fg="red", bold=True)
        click.exit(1)


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
@utils.pass_config
@click.pass_context
def plan(ctx, config, input, var_files, verbose):
    job_spec = templates.render(input, var_files)
    job = config.parse_hcl_or_exit(job_spec)

    plan_job(ctx, config, job, verbose)


@cli.command()
@utils.connectivity_options
@utils.template_options
@click.option(
    "--purge",
    "-p",
    is_flag=True,
    default=False,
    help="Purge is used to stop the job and purge it from the system.",
)
@utils.pass_config
def stop(config, input, var_files, purge):
    job_spec = templates.render(input, var_files)
    job = config.parse_hcl_or_exit(job_spec)
    params = {"purge": "true" if purge else "false"}
    response = config.client.delete(f"/v1/job/{job['ID']}", params=params)
    if response.status_code != 200:
        raise utils.ApiError(response)
    data = response.json()
    click.secho("Job Deletion:", bold=True)
    success, _ = monitor_evaluation(config, data["EvalID"])

    if success:
        click.secho("\nJob deletion finished succesfully.", fg="green", bold=True)
    else:
        click.secho("\nJob deletion failed.", fg="red", bold=True)
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


def plan_job(ctx, config, job, verbose):
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

    return data


def monitor_evaluation(config, eval_id):
    click.echo(f"- Monitoring evaluation {repr(eval_id)}.")
    deployment_id = None
    while True:
        response = config.client.get(f"/v1/evaluation/{eval_id}")
        if response.status_code != 200:
            raise utils.ApiError(response)
        eval = response.json()
        status = eval["Status"]

        if status in ("failed", "cancelled"):
            click.echo(f"Evaluation failed: {eval['StatusDescription']}")
            return False, deployment_id
        elif status == "complete":
            if eval.get("NextEval", None):
                eval_id = eval["NextEval"]
                click.echo(f"- Evaluation {repr(eval_id)} completed successfully.")
                click.echo(f"- Monitoring evaluation {repr(eval_id)}.")
            else:
                deployment_id = eval.get("DeploymentID", None)
                break
        else:
            time.sleep(3)

    click.echo(f"- Evaluation {repr(eval_id)} completed successfully.")

    return True, deployment_id


def monitor_deployment(config, deployment_id):
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
