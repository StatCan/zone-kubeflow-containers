variable "CACHE_REF" {
  default = "k8scc01covidacr.azurecr.io/build-cache"
}

variable "OUTPUT_TYPE" {
    # default = "docker"
    default = "registry"
}

target "base" {
    args = {
        BASE_IMAGE="quay.io/jupyter/datascience-notebook:2025-03-05"
    }
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
    context = "./images/base"
    output = [{ type = "${OUTPUT_TYPE}" }]
    tags = ["base"]
}

target "mid" {
    args = {
        BASE_IMAGE="base"
    }
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
    context = "./images/mid"
    output = [{ type = "${OUTPUT_TYPE}" }]
    tags = ["mid"]
}

target "sas-kernel" {
    args = {
        BASE_IMAGE="mid"
    }
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
    context = "./images/sas_kernel"
    output = [{ type = "${OUTPUT_TYPE}" }]
    tags = ["sas-kernel"]
}

target "mid-jupyterlab" {
    args = {
        BASE_IMAGE="sas-kernel"
    }
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
    context = "./images/jupyterlab"
    output = [{ type = "${OUTPUT_TYPE}" }]
    tags = ["mid-jupyterlab"]
}

target "jupyterlab-cpu" {
    args = {
        BASE_IMAGE="mid-jupyterlab"
    }
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
    context = "./images/cmd"
    output = [{ type = "${OUTPUT_TYPE}" }]
    tags = ["jupyterlab-cpu"]
}

target "mid-sas" {
    args = {
        BASE_IMAGE="sas-kernel"
    }
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
    context = "./images/sas"
    output = [{ type = "${OUTPUT_TYPE}" }]
    tags = ["mid-sas"]
}

target "sas" {
    args = {
        BASE_IMAGE="mid-sas"
    }
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
    context = "./images/cmd"
    output = [{ type = "${OUTPUT_TYPE}" }]
    tags = ["sas"]
}