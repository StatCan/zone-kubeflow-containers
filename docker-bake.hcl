target "base" {
    context = "./images/base"
    args = {
        BASE_IMAGE="quay.io/jupyter/datascience-notebook:2025-03-05"
    }
    tags = ["base"]
}

target "mid" {
    context = "./images/mid"
    args = {
        BASE_IMAGE="base"
    }
    tags = ["mid"]
}

target "sas_kernel" {
    context = "./images/sas_kernel"
    args = {
        BASE_IMAGE="mid"
    }
    tags = ["sas_kernel"]
}

target "mid-jupyterlab" {
    context = "./images/jupyterlab"
    args = {
        BASE_IMAGE="sas_kernel"
    }
    tags = ["mid-jupyterlab"]
}

target "jupyterlab" {
    context = "./images/cmd"
    args = {
        BASE_IMAGE="mid-jupyterlab"
    }
    tags = ["jupyterlab-cpu"]
}

target "mid-sas" {
    context = "./images/sas"
    args = {
        BASE_IMAGE="sas_kernel"
    }
    tags = ["mid-sas"]
}

target "sas" {
    context = "./images/cmd"
    args = {
        BASE_IMAGE="mid-sas"
    }
    tags = ["sas"]
}