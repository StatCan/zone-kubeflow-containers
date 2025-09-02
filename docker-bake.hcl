target "base" {
    args = {
        BASE_IMAGE="quay.io/jupyter/datascience-notebook:2025-03-05"
    }
    context = "./images/base"
    tags = ["base"]
}

target "mid" {
    args = {
        BASE_IMAGE="base"
    }
    context = "./images/mid"
    tags = ["mid"]
}

target "sas-kernel" {
    args = {
        BASE_IMAGE="mid"
    }
    context = "./images/sas_kernel"
    tags = ["sas-kernel"]
}

target "mid-jupyterlab" {
    args = {
        BASE_IMAGE="sas-kernel"
    }
    context = "./images/jupyterlab"
    tags = ["mid-jupyterlab"]
}

target "jupyterlab-cpu" {
    args = {
        BASE_IMAGE="mid-jupyterlab"
    }
    context = "./images/cmd"
    tags = ["jupyterlab-cpu"]
}

target "mid-sas" {
    args = {
        BASE_IMAGE="sas-kernel"
    }
    context = "./images/sas"
    tags = ["mid-sas"]
}

target "sas" {
    args = {
        BASE_IMAGE="mid-sas"
    }
    context = "./images/cmd"
    tags = ["sas"]
}