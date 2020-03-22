# Dobby

Dobby is a [Jinja](https://jinja.palletsprojects.com/)-powered opensource templating and deployment tool for [HashiCorp Nomad](https://www.nomadproject.io/) inspired by [Levant](https://github.com/jrasell/levant).

## Features

* **Deployment monitoring**: Dobby waits for a deployment to finish, making it ideal for CI/CD usage.
* **Jinja2 templating**: Templates are based on the powerful Jinja2 templating language, which allows for recursive template inclusions etc...
* **Variable file formats**: Dobby currently supports `.json`, `.yaml` and `.env` file formats for template variables as well as operating system environment variables (more below).

## Download & Install

TODO :) Currently not packaged at all.

## Example

A small example is shown below (try on your own shell for more colors ;)):

```bash
$ dobby deploy -var-file examples/vars.yaml examples/redis.nomad
Planned changes:

+ Job: "redis"
+ Task Group: "redis" (1 create)
  + Task: "redis" (forces create)

Scheduler dry-run:
- All tasks successfully allocated.

Job Submission:
- Monitoring evaluation '4bd2eb5f-36ab-4a0d-6355-91c17e8ec205'.
- Evaluation '4bd2eb5f-36ab-4a0d-6355-91c17e8ec205' completed successfully.
- Monitoring deployment 'cb857ab3-db31-cd4f-a3b3-a5175be15ad0'.
- Deployment 'cb857ab3-db31-cd4f-a3b3-a5175be15ad0' completed successfully.

Job deployment finished succesfully.

```

## Templating

Dobby reads template variables from a variety of files (`.json/.yaml/.env`) and is able to merge multiple variable files before passing them on to Jinja2. To prevent conflicts with Nomad-Templates, Jinja is configured to use square instead of curly brackets (ie `[[ job.name ]]` instead of `{{ job.name }}`).

Additionally Dobby takes environment variables into account since it can be annoying to create a variable file in CI/CD just to override one variable (the job name could be a common example). Environment variables are supported by upper-casing variable names, removing underscores and hyphens as well as replacing dots with underscores. This means a variable file ala:

```yaml
job:
    name: test
    dc: dc22
    db_url: postgresql://host/db
```

can be also specified via the following environment variables:

```
JOB_NAME=test
JOB_DC=dc22
JOB_DBURL=postgresql://host/db
```

For people solely relying on environment variables the Jinja template context also contains them directly (ie they can be accessed via `[[ JOB_DBURL ]]`). In general dotted notation is prefered as it allows support for environment variables as well as variable files.
