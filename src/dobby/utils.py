class ApiError(Exception):
    def __init__(self, response):
        self.response = response


def hcl_to_json(config, hcl):
    response = config.client.post("/v1/jobs/parse", json={"JobHCL": hcl})

    if response.status_code == 200:
        return response.json()
    else:
        raise ApiError(response)
