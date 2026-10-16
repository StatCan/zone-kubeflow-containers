target "base" {
    args = {
        # The CI-built Python 3.14 datascience-notebook chain (see the
        # upstream-datascience job in .github/workflows/docker.yaml, which
        # produces this exact tag), so local builds start from the same base
        # as CI and skip rebuilding the upstream chain. Requires `az acr login
        # --name stcthezoneacr` first. Keep the tag in lockstep with that
        # job's PYTHON_VERSION and DOCKER_STACKS_REF.
        BASE_IMAGE="stcthezoneacr.azurecr.io/datascience-notebook:python3.14.5-d7c65738a271"
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
