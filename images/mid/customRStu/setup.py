import setuptools


setuptools.setup(
    name="jupyter-custom-rstudio-proxy",
    version="0.0.1",
    description="Jupyter server-proxy entry for custom RStudio startup",
    packages=setuptools.find_packages(),
    install_requires=[
        "jupyter-server-proxy>=4.0.0",
    ],
    entry_points={
        "jupyter_serverproxy_servers": [
            "rstudio = jupyter_custom_rstudio_proxy:setup_rstudio",
        ]
    },
)
