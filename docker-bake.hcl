# Jupyter Docker Stacks Upstream images
target "docker-stacks-foundation" {
    args = {
        ROOT_IMAGE="ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852"
        PYTHON_VERSION="3.14.5"
    }
    context = "./images/upstream/docker-stacks-foundation"
    tags = ["docker-stacks-foundation"]
}

target "base-notebook" {
    context = "./images/upstream/base-notebook"
    contexts = {
        docker-stacks-foundation = "target:docker-stacks-foundation"
    }
    tags = ["base-notebook"]
}

target "minimal-notebook" {
    context = "./images/upstream/minimal-notebook"
    contexts = {
        base-notebook = "target:base-notebook"
    }
    tags = ["minimal-notebook"]
}

target "scipy-notebook" {
    context = "./images/upstream/scipy-notebook"
    contexts = {
        minimal-notebook = "target:minimal-notebook"
    }
    tags = ["scypi-notebook"]
}

# The Zone images
target "base" {
    args = {
        BASE_IMAGE="scipy-notebook"
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
