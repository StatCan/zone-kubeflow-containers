target "base" {
    args = {
        BASE_IMAGE="quay.io/jupyter/datascience-notebook:2025-03-05"
    }
    context = "./images/base"
    tags = ["base"]
}

target "jupyterlab-slim" {
    args = {
        BASE_IMAGE="base"
    }
    context = "./images/jupyterlab-slim"
    tags = ["jupyterlab-slim"]
}

target "sas-kernel" {
    args = {
        BASE_IMAGE="jupyterlab-slim"
    }
    context = "./images/sas_kernel"
    tags = ["sas-kernel"]
}

target "jupyterlab-cpu" {
    args = {
        BASE_IMAGE="sas-kernel"
    }
    context = "./images/jupyterlab"
    tags = ["jupyterlab-cpu"]
}

target "sas" {
    args = {
        BASE_IMAGE="sas-kernel"
    }
    context = "./images/sas"
    tags = ["sas"]
}