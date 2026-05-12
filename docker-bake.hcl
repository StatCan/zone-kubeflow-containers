target "base" {
    args = {
        BASE_IMAGE="quay.io/jupyter/datascience-notebook:2026-05-11"
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

target "rstudio" {
    args = {
        BASE_IMAGE="mid"
    }
    context = "./images/rstudio"
    tags = ["rstudio"]
}

target "sas-kernel" {
    args = {
        BASE_IMAGE="rstudio"
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
