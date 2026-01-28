target "base" {
    args = {
        BASE_IMAGE="quay.io/jupyter/datascience-notebook:2025-03-05"
    }
    context = "./images/base"
    tags = ["base"]
}

target "slim" {
    args = {
        BASE_IMAGE="base"
    }
    context = "./images/slim"
    tags = ["slim"]
}

target "sas-kernel" {
    args = {
        BASE_IMAGE="slim"
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