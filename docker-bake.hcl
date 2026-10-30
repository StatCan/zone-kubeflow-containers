# Jupyter Docker Stacks Upstream images
target "docker-stacks-foundation" {
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
