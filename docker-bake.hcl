variable "CACHE_REF" {
  default = "k8scc01covidacr.azurecr.io/build-cache"
}

target "base" {
    args = {
        BASE_IMAGE="quay.io/jupyter/datascience-notebook:2025-03-05"
    }
    context = "./images/base"
    cache-from = [
        {
            type = "registry"
            ref = "${CACHE_REF}:base"
        }
    ]
    cache-to = [
        {
            type = "registry"
            ref = "${CACHE_REF}:base"
            mode = "max"
        }
    ]
    output = [{ type = "docker" }]
    tags = ["base"]
}

target "mid" {
    context = "./images/mid"
    cache-from = [
        {
            type = "registry"
            ref = "${CACHE_REF}:mid"
        }
    ]
    cache-to = [
        {
            type = "registry"
            ref = "${CACHE_REF}:mid"
            mode = "max"
        }
    ]
    args = {
        BASE_IMAGE="base"
    }
    tags = ["mid"]
}

target "sas-kernel" {
    context = "./images/sas_kernel"
    cache-from = [
        {
            type = "registry"
            ref = "${CACHE_REF}:sas-kernel"
        }
    ]
    cache-to = [
        {
            type = "registry"
            ref = "${CACHE_REF}:sas-kernel"
            mode = "max"
        }
    ]
    args = {
        BASE_IMAGE="mid"
    }
    tags = ["sas-kernel"]
}

target "mid-jupyterlab" {
    context = "./images/jupyterlab"
    cache-from = [
        {
            type = "registry"
            ref = "${CACHE_REF}:mid-jupyterlab"
        }
    ]
    cache-to = [
        {
            type = "registry"
            ref = "${CACHE_REF}:mid-jupyterlab"
            mode = "max"
        }
    ]
    args = {
        BASE_IMAGE="sas-kernel"
    }
    tags = ["mid-jupyterlab"]
}

target "jupyterlab-cpu" {
    context = "./images/cmd"
    cache-from = [
        {
            type = "registry"
            ref = "${CACHE_REF}:jupyterlab-cpu"
        }
    ]
    cache-to = [
        {
            type = "registry"
            ref = "${CACHE_REF}:jupyterlab-cpu"
            mode = "max"
        }
    ]
    args = {
        BASE_IMAGE="mid-jupyterlab"
    }
    tags = ["jupyterlab-cpu"]
}

target "mid-sas" {
    context = "./images/sas"
    cache-from = [
        {
            type = "registry"
            ref = "${CACHE_REF}:mid-sas"
        }
    ]
    cache-to = [
        {
            type = "registry"
            ref = "${CACHE_REF}:mid-sas"
            mode = "max"
        }
    ]
    args = {
        BASE_IMAGE="sas-kernel"
    }
    tags = ["mid-sas"]
}

target "sas" {
    context = "./images/cmd"
    cache-from = [
        {
            type = "registry"
            ref = "${CACHE_REF}:sas"
        }
    ]
    cache-to = [
        {
            type = "registry"
            ref = "${CACHE_REF}:sas"
            mode = "max"
        }
    ]
    args = {
        BASE_IMAGE="mid-sas"
    }
    tags = ["sas"]
}