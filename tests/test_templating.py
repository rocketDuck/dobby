from pathlib import Path

import pytest

from dobby.templates import render


@pytest.fixture
def root():
    return Path(__file__).parent


@pytest.fixture
def simple_template(root):
    return root / "templates/simple.txt"


@pytest.fixture
def simple_vars(root):
    return root / "vars/simple.yml"


def test_simple_render(simple_template, simple_vars):
    data = render(simple_template, [simple_vars]).splitlines()

    assert data[0] == "job_name = test"
    assert data[1] == "database_url = testurl@yaml"


def test_env_override(simple_template, simple_vars):
    data = render(
        simple_template,
        [simple_vars],
        {"JOBNAME": "testenv", "ENV_PRODUCTION_DATABASEURL": "testurl@env"},
    ).splitlines()

    assert data[0] == "job_name = testenv"
    assert data[1] == "database_url = testurl@env"
