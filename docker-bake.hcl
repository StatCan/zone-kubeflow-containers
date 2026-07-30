target "base" {
    args = {
        # Local-build default (Python 3.13). CI builds base from a custom
        # Python 3.14 scipy-notebook chain instead -- see the upstream-scipy
        # job in .github/workflows/docker.yaml.
        BASE_IMAGE="quay.io/jupyter/scipy-notebook:2025-08-15"
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
