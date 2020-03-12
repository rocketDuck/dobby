job "[[ job_name ]]" {
  datacenters = ["dc1"]

  type = "service"


  group "api" {
    count = 1

    network {
      mode = "bridge"
    }
    service {
      name = "count-api"
      port = "9001"
      connect {
        sidecar_service {}
      }
    }

    task "web" {
      driver = "docker"

      config {
        image = "hashicorpnomad/counter-api:v1"
      }

      resources {
        cpu    = 500 # 500 MHz
        memory = 256 # 256MB
      }
    }
  }

[% include "dashboard_group.j2" %]
}
