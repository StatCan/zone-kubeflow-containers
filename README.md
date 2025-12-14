# Zone-kubeflow-containers

Container images to be used with [The Zone](https://zone.statcan.ca).
User documentation can be found at https://zone.pages.cloud.statcan.ca/docs/en/

## Table of Contents
<!-- toc -->
- [Introduction](#introduction)
- [List of maintained images in this github repository](#list-of-maintained-images-in-this-github-repository)
- [Usage](#usage)
  - [Building and Tagging Docker Images](#building-and-tagging-docker-images)
  - [Pulling and Pushing Docker Images](#pulling-and-pushing-docker-images)
  - [Testing Images](#testing-images)
    - [Running and Connecting to Images Locally/Interactively](#running-and-connecting-to-images-locallyinteractively)
    - [Automated Testing](#automated-testing)
- [General Development Workflow](#general-development-workflow)
  - [Overview of Images](#overview-of-images)
  - [Running A Zone Container Locally](#running-a-zone-container-locally)
  - [Testing locally](#testing-locally)
  - [Testing On-Platform](#testing-on-platform)
  - [Adding new software](#adding-new-software)
  - [Adding new Images](#adding-new-images)
  - [Modifying and Testing CI](#modifying-and-testing-ci)
- [Beta Process](#beta-process)
- [Other Development Notes](#other-development-notes)
  - [Github CI](#github-ci)
  - [The `v2` and `latest` tags for the master branch](#the-v2-and-latest-tags-for-the-master-branch)
  - [Set User File Permissions](#set-user-file-permissions)
  - [Troubleshooting](#troubleshooting)
- [Structure](#structure)
<!-- tocstop -->

## Introduction

Our Container images are based on the community driven [jupyter/docker-stacks](https://github.com/jupyter/docker-stacks).
We chose those images because they are continuously updated and install the most common utilities.
This enables us to focus only on the additional toolsets that we require to enable our data scientists.
These customized images are maintained by the Zone team and are the default images available on The Zone.

## Overview of Images

Each directory in the images folder makes up one stage of the build process.
They each contain the Dockerfile that directs the build, and all related files.

The relationship between the stages and the final product is as shown below.
```mermaid
graph TD
  upstream_nb["(upstream) datascience-notebook"]
  upstream_nb --> base
  base --> mid
  mid --> sas_kernel
  upstream_sas["(upstream) sas4c"] --> |copy|sas_kernel
  sas_kernel --> jupyterlab["jupyterlab (jupyterlab-cpu)"]
  sas_kernel --> sas
```

### Base Images

These images are chained together to perform the multi-staged build for our final images

Image | Notes
--- | ---
[base](./images/base) | Base Image pulling from docker-stacks
[mid](./images/mid) | Installs various tools on top of the base image
[sas-kernel](./images/sas_kernel) | Installs the SAS kernel on our mid image

### Zone Images

These are the final images from our build process and are intended to be used on Kubeflow Notebooks

Image | Notes | Installations
--- | --- | ---
[jupyterlab-cpu](./images/jupyterlab) | The base experience. A jupyterlab notebook with various | Jupyter, VsCode, R, Python, Julia, Sas kernel
[sas](./images/sas) | Similar to our jupyterlab-cpu image, except with SAS Studios | Sas Studios

## Usage

### Building Images

We have setup [Docker Bake](https://docs.docker.com/build/bake/) to help with building our images. Docker Bake lets us define our build configuration for our images through a file instead of CLI instructions.

To build an image, you can use either `make bake/IMAGE` or `docker buildx bake IMAGE`. `docker build` commands can still work if desired.

`make bake` accepts overrides for BASE_IMAGE, REPO and TAGS to adjust these values for the build.

To review any parameters for the image builds, you can review and edit the [docker-bake.hcl](./docker-bake.hcl) file. 
This file is currently setup for local development. We use parameter overrides for our github workflows to adjust the docker bake file for our CI/CD process.

**Note:** Our workflows save all our images in our Azure Container Registry. To pull and push to our ACR locally, 
you will first have to login using `az acr login -n k8scc01covidacr`

**Note:** `make push` by default does `docker push --all-tags` in order to push the SHA, SHORT_SHA, etc., tags.  

### Testing Images

#### Running and Connecting to Images Locally/Interactively

To test an image interactively, use `make dev/IMAGENAME`.
This calls `docker run` on a built image,
automatically forwarding ports to your local machine and providing a link to connect to.
Once the docker container is running, it will serve a localhost url to connect to the notebook.

#### Automated Testing

Automated tests are included for the generated Docker images using `pytest`.
This testing suite is modified from the [docker-stacks](https://github.com/jupyter/docker-stacks) test suite.
Image testing is invoked through various `make test-*` commands:

- `make test/IMAGENAME` - Run full test suite for a specific image
- `make test-smoke/IMAGENAME` - Run critical path tests only (fast)
- `make test-fast/IMAGENAME` - Run all tests except slow/integration tests
- `make test-coverage/IMAGENAME` - Run tests and generate coverage reports

Testing of a given image consists of general and image-specific tests:

```
└── tests
    ├── general/                            # General tests applied to all images
    │   ├── wait_utils.py                   # Polling utilities with exponential backoff
    │   ├── test_health.py                  # Server health and readiness checks
    │   ├── test_kernel_execution.py        # Kernel functionality tests
    │   ├── test_environment.py             # Environment variable configuration
    │   ├── test_notebook.py                # Notebook server functionality
    │   ├── test_packages.py                # Package import verification
    │   ├── test_r_functionality.py         # R language functionality
    │   ├── test_code_server.py             # Code-server functionality
    │   ├── test_python_data_science.py     # Python data science stack
    │   ├── test_rstudio_web.py             # RStudio integration tests
    │   ├── test_negative_scenarios.py      # Error handling and failure tests
    │   └── README.md                       # Test suite documentation
    └── IMAGENAME/                          # Test applied to a specific image
        └── some_image_specific_test.py
```

Where `tests/general` tests are applied to all images,
and `tests/IMAGENAME` are applied only to a specific image.
Pytest will start the image locally and then run the provided tests to determine if JupyterLab is running, Python packages are working properly, etc.
Tests are formatted using typical pytest formats
(python files with `def test_SOMETHING()` functions).
`conftest.py` defines some standard scaffolding for image management, etc.

---

## General Development Workflow

### Running A Zone Container Locally

1. Clone the repository with `git clone https://github.com/StatCan/zone-kubeflow-containers`.
2. Run `make install-python-dev-venv` to build a development Python virtual environment.
2.5 Add back from statements in Dockerfiles.
3. Build your image using `make bake/IMAGENAME`,
e.g. run `make bake/base`.
4. Test your image using automated tests through `make test/IMAGENAME`,
e.g. run `make test/sas`.
Remember that tests are designed for the final stage of a build.
5. View your images with `docker images`.
You should see a table printed in the console with your images.
For example you may see:

```
username@hostname:~$ docker images
REPOSITORY                                  TAG        IMAGE ID       CREATED          SIZE
k8scc01covidacr.azurecr.io/jupyterlab-cpu   v2         13f8dc0e4f7a   26 minutes ago   14.6GB
k8scc01covidacr.azurecr.io/sas              v2         2b9acb795079   19 hours ago     15.5GB
```

7. Run your image with `docker run -p 8888:8888 REPO/IMAGENAME:TAG`, e.g. `docker run -p 8888:8888 k8scc01covidacr.azurecr.io/sas:v2`.
8. Open [http://localhost:8888](http://localhost:8888) or `<ip-address-of-server>:8888`.

### Testing locally

1. Clone the repo
2. Edit an image via the [image stages](/images) that are used to create it.
3. Build your edited stages and any dependencies using `make bake/IMAGENAME`
    * (optional) Run `docker pull REPO/IMAGENAME:TAG` to pull an existing version of the image you are working on 
    (this could be useful as a build cache to reduce development time below)
    * (optional) If the BASE_IMAGE is not build locally for the image stage you want to build, you will have to either run `make bake/BASE_IMAGE` to build it locally, 
    or you will have to pull the image.
4. Test your image:
    * using automated tests through `make test/IMAGENAME`
    * manually by `docker run -it -p 8888:8888 REPO/IMAGENAME:TAG`,
     then opening it in [http://localhost:8888](http://localhost:8888)

### Testing On-Platform

GitHub Actions CI is enabled to do building, scanning, automated testing, pushing of our images to ACR.
The workflows will trigger on the following:

- any push to master or beta
- any push to an open PR that edits files in `.github/workflows/` or `/images/`

This allows for easy scanning and automated testing for images.

[![Code Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/bryan/coverage-badge-endpoint/main/coverage.json)](https://github.com/StatCan/zone-kubeflow-containers)

### Testing Strategies

Our test suite employs multiple strategies to ensure reliability and comprehensive coverage:

**Unit Tests**: Individual component verification for packages and binaries
**Integration Tests**: End-to-end functionality verification across components
**Performance Tests**: Timing verification and resource usage validation
**Negative Tests**: Error handling and failure scenario testing
**Smoke Tests**: Critical path verification for quick validation

### Test Categories

The test suite is organized into these categories:

| Category | Purpose | Location |
|----------|---------|----------|
| Core Health Tests | Server availability and responsiveness | `test_health.py` |
| Kernel Execution Tests | Python, R, and Julia kernel functionality | `test_kernel_execution.py` |
| Data Science Tests | Package verification and workflow testing | `test_python_data_science.py` |
| Language Support Tests | R, Python, Julia functionality | `test_r_functionality.py` |
| Code Editor Tests | Code-server functionality | `test_code_server.py` |
| Negative Scenario Tests | Error handling and failure conditions | `test_negative_scenarios.py` |

### Reliable Timing

Tests now use intelligent polling mechanisms instead of fixed sleep times:

- **Exponential Backoff**: Adaptive waiting with increasing intervals
- **Jitter**: Randomization to prevent synchronized polling
- **Timeout Handling**: Graceful failure when conditions aren't met
- **Readiness Checks**: Proper server/container readiness verification

This approach eliminates flaky tests caused by timing issues across different environments.

After the workflow is complete,
the images will be available on artifactory.cloud.statcan.ca/das-aaw-docker.
You can access these images on https://zone.statcan.ca using any of the following:

- artifactory.cloud.statcan.ca/das-aaw-docker/IMAGENAME:BRANCH_NAME
- artifactory.cloud.statcan.ca/das-aaw-docker/IMAGENAME:SHA
- artifactory.cloud.statcan.ca/das-aaw-docker/IMAGENAME:SHORT_SHA

Pushes to master will also have the following tags:

- artifactory.cloud.statcan.ca/das-aaw-docker/IMAGENAME:latest
- artifactory.cloud.statcan.ca/das-aaw-docker/IMAGENAME:v2

### Adding new software

Software needs to be added by modifying the relevant image stage,
then following the normal build instructions starting with the Generate Dockerfiles step.

Be selective with software installation as image sizes are already quite big (16Gb plus),
and increasing that size would negatively impact the time it takes up for a workspace server to come up
(as well as first time image pulls to a node).
In such cases it may be more relevant to make an image under [aaw-contrib-containers](https://github.com/StatCan/aaw-contrib-containers) as mentioned earlier.

### Adding new Images

1. Identify where the new stage will be placed in the build order
2. Create a new subdirectory in the `/images/` directory for the stage
3. Add a new target to the `docker-bake.hcl` file for the new stage.
    ```
    # general format for a bake target
    target "stage-name" {
      args = {
        BASE_IMAGE="BASE_IMAGE"         # ARGS values from the dockerfile
      }
      context = "./images/stage-name"   # points to the location of the dockerfile
      tags = ["stage-name"]             # name given to the built docker image
    }
    ```
4. Add a new job to the `./github/workflows/docker.yaml` for the new stage.

    ```yaml
    # yaml to create an image
    stage-name:                                                         # The name of the stage, will be shown in the CICD workflow
      needs: [vars, parent]                                             # All stages need vars, any stages with a parent must link their direct parent
      uses: ./.github/workflows/docker-steps.yaml
      with:
        image: "stage-name"                                             # The name of the current stage/image
        directory: "directory-name"                                     # The name of the directory in the /images/ folder. /images/base would be "base"
        base-image: "quay.io/jupyter/datascience-notebook:2024-06-17"   # used if the stage is built from an upsteam image. Omit if stage has a local parent
        parent-image: "parent"                                          # The name of the parent stage/image. Omit if stage uses an upsteam image
        parent-image-is-diff: "${{ needs.parent.outputs.is-diff }}"     # Checks if the parent image had changes. Omit if stage uses an upsteam image
        # The following values are static between differnt stages
        registry-name: "${{ needs.vars.outputs.REGISTRY_NAME }}"
        branch-name: "${{ needs.vars.outputs.branch-name }}"
      secrets:
        REGISTRY_USERNAME: ${{ secrets.REGISTRY_USERNAME }}
        REGISTRY_PASSWORD: ${{ secrets.REGISTRY_PASSWORD }}
    ```

5. If this stage was inserted between two existing stages,
update the parent values of any children of this stage
6. If this stage creates an image that will be deployed to users.
A job must be added to test the image in `./github/workflows/docker.yaml`,
and the image name must be added to the matrix in `./github/workflows/docker-nightly.yaml`

    ```yaml
    # yaml to create a test
    imagename-test:                                       # The name of the test job, usually  imagename-test
      needs: [vars, imagename]                            # Must contain vars and the image that will be tested
      uses: ./.github/workflows/docker-pull-test.yaml
      with:
        image: "imagename"                                # The name of the image that will be tested
        # The following values are static between differnt tests
        registry-name: "${{ needs.vars.outputs.REGISTRY_NAME }}"
        tag: "${{ needs.vars.outputs.branch-name }}"
      secrets:
        REGISTRY_USERNAME: ${{ secrets.REGISTRY_USERNAME }}
        REGISTRY_PASSWORD: ${{ secrets.REGISTRY_PASSWORD }}
        CVE_ALLOWLIST: ${{ secrets.CVE_ALLOWLIST}}
    ```

7. Update the documentation for the new stage.
This is generally updating `images-stages.png` and `image-stages.drawio` in the `docs/images` folder using draw.io.

### Custom scripts

To manage our custom scripts that we want to execute after a container starts up, we use the [s6-overlay](https://github.com/just-containers/s6-overlay). Kubeflow upstream also uses this tool with their [example notebook servers](https://github.com/kubeflow/kubeflow/blob/master/components/example-notebook-servers/README.md#configure-s6-overlay)


Scripts that need to run during the startup of the container can be placed in `/etc/cont-init.d/`, and are executed in ascending alphanumeric order.

Scripts like our [start-custom](./images/mid/s6/cont-init.d/02-start-custom) use the with-contenv helper so that environment variables (passed to container) are available in the script.

Extra services to be monitored by s6-overlay should be placed in their own folder under `/etc/services.d/` containing a script called `run` and optionally a finishing script `finish`.

An example of a long-running service can be found in our [main run script](./images/mid/s6/services.d/jupyter/run) which is used to start JupyterLab itself.

#### Note on setting environment variables in startup scripts

When using both a startup script and a service script, environment variables declared in the startup script (using `export VAR=value` for example) will not be available in the service script.

To circumvent this limitation, if you need to declare new environment variables from a custom script, you can first create a custom environment location, like `/run/s6-env`. Then, you can store your new environment variables in that new location, using for example `echo ${TEST_ENV_VAR} > /run/s6-env/TEST_ENV_VAR`. 
Then, when executing the long-running service, you can use `s6-envdir /run/s6-env` to point to your custom environment location in the `exec` command.

### Testing Quick Reference

To help users quickly understand the available testing commands:

#### Running Tests

```bash
# Install dev dependencies first
make install-python-dev-venv

# Run tests for a specific image
make test/jupyterlab-cpu
make test/base
make test/sas

# Run smoke tests (fast, critical path only)
make test-smoke/jupyterlab-cpu

# Run fast tests (skip slow/integration tests)
make test-fast/jupyterlab-cpu

# Run tests with coverage reporting
make test-coverage/jupyterlab-cpu

# Run all tests automatically
make test
```

#### Test Markers

Tests are categorized with markers for selective execution:

| Marker | Purpose | Example |
|--------|---------|---------|
| `@pytest.mark.smoke` | Critical path tests only | Fast validation |
| `@pytest.mark.integration` | Tests requiring Docker | Container execution |
| `@pytest.mark.slow` | Long-running tests | Skip with `-m "not slow"` |
| `@pytest.mark.info` | Informational/diagnostic tests | Skip by default |

#### Running Selective Tests

```bash
# Run only smoke tests
pytest -m smoke

# Run all except slow tests
pytest -m "not slow"

# Run integration tests only
pytest -m integration
```

### Modifying and Testing CI

If making changes to CI that cannot be done on a branch (eg: changes to issue_comment triggers), you can:

1. fork the 'kubeflow-containers' repo
2. Modify the CI with

- REGISTRY: (your own dockerhub repo, eg: "j-smith" (no need for the full url))
- Change
  ```
  - uses: azure/docker-login@v1
    with:
      login-server: ${{ env.REGISTRY_NAME }}.azurecr.io
      username: ${{ secrets.REGISTRY_USERNAME }}
      password: ${{ secrets.REGISTRY_PASSWORD }}
  ```
  to
  ```
  - uses: docker/login-action@v1
    with:
      username: ${{ secrets.REGISTRY_USERNAME }}
      password: ${{ secrets.REGISTRY_PASSWORD }}
  ```

3. In your forked repo, define secrets for REGISTRY_USERNAME and REGISTRY_PASSWORD with your dockerhub credentials (you should use an API token, not your actual dockerhub password)

---

## Beta Process

![Flowchart of the beta release process](./docs/images/beta_process_v2.drawio.png)

To reduce unexpected changes getting added into the images used by our users, 
we implemented a beta process that should be followed when introducing changes to the codebase.

When a change needs to be done, new feature branches should be created from the `beta` branch. 
Following this, new pull requests should target the `beta` branch, unless absolutely necessary to target `master` directly.

Once a pull request has been approved, if the target branch is `beta`, it will automatically be set with the `ready for beta` label.
This label will help us track which new additions are heading into beta. 
With this, the pull request should not be merged manually as an automated process will handle that.

We have in place a workflow(`beta-auto-merge`) which runs on a schedule and handles merging all the `ready for beta` labelled pull requests into `beta`.
This workflow runs every two weeks, and helps us manage the frequency of updates to the `beta` branch.

Once merged into the beta branch, a workflow will build and tag our container images with the `beta` tag instead of `v2`.
Users will then be able to use those `beta` tagged images for their notebook servers if they wish to get early access to new features and fixes.

We also have a second workflow(`beta-promote`) running on a schedule that handles creating a new pull request to promote the beta branch to master.
It also runs every two weeks, but on alternating weeks from the `beta-auto-merge` workflow.
This means that new features and fixes should live for about one week on the beta branch before they are made official in master.

Once we have this new pull request created, someone can manually review it, fix any potential problems, and then finally merge it.
After this pull request is merged, we have a third workflow(`master-release.yaml`) that will handle creating a Github release for `master`.
This release can help us communicate what changes have been done to our container images.

## Other Development Notes

### Github CI

The Github workflow is set up to build the images and their dependant stages.
See below for a flowchart of this build.

The main workflow is `docker.yaml`,
it controls the stage build order, and what triggers the CI.
(Pushes to master, pushes to an open pull-request, and nightly builds)

The building of a stage is controled by `docker-steps.yaml`.
It checks if there are changes to the stage or dependant stages.
Builds a new image if there are changes, 
or pulls a copy of the existing image if not.
Testing will be performed if this is the final stage in the build of an image.

![A flowchart of the Github CI workflow](./docs/images/Workflows.png)

### The `v2` and `latest` tags for the master branch


These tags are intended to be `long-lived` in that they will not change.
Subsequent pushes will clobber the previous `IMAGENAME:v2` image.
This means that `IMAGENAME:v2` will be updated automatically as changes are made,
so updates to the tag are not needed.

A new `v3` tag will be created for adding these breaking changes.

**Note**:
The `latest` tag is shared with [aaw-kubeflow-containers](https://github.com/StatCan/aaw-kubeflow-containers),
So isn't reliable

---
### Set User File Permissions

The Dockerfiles in this repo are intended to construct compute environments for a non-root user **jovyan**
to ensure the end user has the least privileges required for their task,
but installation of some of the software needed by the user must be done as the **root** user.
This means that installation of anything that should be user editable
(eg: `pip` and `conda` installs, additional files in `/home/$NB_USER`, etc.)
will by default be owned by **root** and not modifiable by **jovyan**.
**Therefore we must change the permissions of these files to allow the user specific access for modification.**

For example, most pip install/conda install commands occur as the root user
and result in new files in the $CONDA_DIR directory that will be owned by **root**.
This will cause issues if user **jovyan** tried to update or uninstall these packages
(as they by default will not have permission to change/remove these files).

To fix this issue, end any `RUN` command that edits any user-editable files with:

```
fix-permissions $CONDA_DIR && \
fix-permissions /home/$NB_USER
```

This fix edits the permissions of files in these locations to allow user access.
Note that if these are not applied **in the same layer as when the new files were added**
it will result in a duplication of data in the layer
because the act of changing permissions on a file from a previous layer requires a copy of that file into the current layer.
So something like:

```
RUN add_1GB_file_with_wrong_permissions_to_NB_USER.sh && \
	fix-permissions /home/$NB_USER
```

would add a single layer of about 1GB, whereas

```
RUN add_1GB_file_with_wrong_permissions_to_NB_USER.sh

RUN fix-permissions /home/$NB_USER
```

would add two layers, each about 1GB (2GB total).

### Troubleshooting

If running using a VM and RStudio image was built successfully but is not opening correctly on localhost (error 5000 page),
change your CPU allocation in your Linux VM settings to >= 3.
You can also use your VM's system monitor to examine if all CPUs are 100% being used as your container is running.
If so, increase CPU allocation.
This was tested on Linux Ubuntu 20.04 virtual machine.

## Structure

```
.
├── .github/workflow                        # Github CI. Controls the stage build order
│
├── Makefile                                # Controls the interactions with docker commands
│
├── make_helpers                            # Scripts used by makefile
│   ├── get_branch_name.sh
│   ├── get-nvidia-stuff.sh
│   └── post-build-hook.sh
│
├── images                                  # Dockerfile and required resources for stage builds
│   ├── base                                # Common base of the images
│   ├── jupyterlab                          # Jupyterlab specific Dockerfile
│   ├── mid                                 # Common mid point for all images
│   ├── sas                                 # SAS specific Dockerfile
│   └── sas_kernel                          # Dockerfile for installation of sas_kernel
│
├── docs                                    # files/images used in documentation (ex. Readme's)
│
└── tests
    ├── general/                            # General tests applied to all images
    │   ├── wait_utils.py                   # Polling utilities with exponential backoff
    │   ├── test_health.py                  # Server health and readiness checks
    │   ├── test_kernel_execution.py        # Kernel functionality tests
    │   ├── test_environment.py             # Environment variable configuration
    │   ├── test_notebook.py                # Notebook server functionality
    │   ├── test_packages.py                # Package import verification
    │   ├── test_r_functionality.py         # R language functionality
    │   ├── test_code_server.py             # Code-server functionality
    │   ├── test_python_data_science.py     # Python data science stack
    │   ├── test_rstudio_web.py             # RStudio integration tests
    │   ├── test_negative_scenarios.py      # Error handling and failure tests
    │   └── README.md                       # Test suite documentation
    ├── jupyterlab-cpu/                     # Test applied to a specific image
    ├── sas/                                # Test applied to a specific image
    └── sas-kernel/                         # Test applied to a specific image
```
