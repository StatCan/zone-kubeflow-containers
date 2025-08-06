# build a custom notebook with a custom Python version
# https://jupyter-docker-stacks.readthedocs.io/en/latest/using/custom-images.html
# https://jupyter-docker-stacks.readthedocs.io/en/latest/using/selecting.html#jupyter-datascience-notebook


group "default" {
    targets = ["custom-notebook"]
}

target "foundation" {
    context = "https://github.com/jupyter/docker-stacks/tree/main/images/docker-stacks-foundation"
    args = {
        PYTHON_VERSION = "3.13"
    }
    tags = ["docker-stacks-foundation"]
}

target "base-notebook" {
    context = "https://github.com/jupyter/docker-stacks/tree/main/images/base-notebook"
    contexts = {
        docker-stacks-foundation = "target:foundation"
    }
    args = {
        BASE_IMAGE = "docker-stacks-foundation"
    }
    tags = ["base-notebook"]
}

target "minimal-notebook" {
    context = "https://github.com/jupyter/docker-stacks/tree/main/images/minimal-notebook"
    contexts = {
        base-notebook = "target:base-notebook"
    }
    args = {
        BASE_IMAGE = "base-notebook"
    }
    tags = ["minimal-notebook"]
}

target "scipy-notebook" {
    context = "https://github.com/jupyter/docker-stacks/tree/main/images/scipy-notebook"
    contexts = {
        minimal-notebook = "target:minimal-notebook"
    }
    args = {
        BASE_IMAGE = "minimal-notebook"
    }
    tags = ["scipy-notebook"]
}

target "datascience-notebook" {
    context = "https://github.com/jupyter/docker-stacks/tree/main/images/datascience-notebook"
    contexts = {
        scipy-notebook = "target:scipy-notebook"
    }
    args = {
        BASE_IMAGE = "scipy-notebook"
    }
    tags = ["datascience-notebook"]
}

target "custom-notebook" {
    context = "."
    contexts = {
        datascience-notebook = "target:datascience-notebook"
    }
    args = {
        BASE_IMAGE = "datascience-notebook"
    }
    tags = ["custom-base"]
}
