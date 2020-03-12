Dobby
=====

Dobby deploys jobs to Nomad after templating them via Jinja2. This is currently still WIP.

Dobby is similar to [levant](https://github.com/jrasell/levant) but is written in Python and therefor using Jinja-Templates instead of go-templates. It supports all of Jinja, including template includes relative to the specified job template and recursive templating. Since nomad syntax would clash with Jinja templates, Jinja ist reconfigured to use `[[ ... ]]`, `[% ... %]` instead of the usual curly braces.

A small example is shown below (try on your own shell for more colors ;)):

```bash
$ dobby deploy --var-file examples/vars.yaml examples/redis.nomad
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

Supported variable interpolation formats
----------------------------------------

Dobby can (currently) interpret JSON, YAML and dotenv (.env) files as sources for template values. If `--var-file` is specified multiple times, the parsed variables are merged and variables specified later on the command line win.

Additionally the template context contains the environment variables of the calling system.
