"""
Common functions and data for using the filers.
"""

import os
import re
import subprocess


FILER_ALIASES = {
    "fld3filersvm": [
        "assdnt2",
        "assdnt20",
        "assdntcad",
        "fld3file1",
        "fld3filer",
    ],
    "fld4filersvm": [
        "bop600",
        "imad3",
        "imad4",
        "imaddiskfarm",
        "meaddata",
        "pid6",
        "fld4filer",
    ],
    "fld5filersvm": [
        "agric",
        "btsapps",
        "btssce",
        "dtd1",
        "iofd1",
        "itd1lm",
        "itd3lm",
        "mced1nt",
        "mced2nt",
        "pipes1",
        "pricesfp01",
        "serv01",
        "serv02",
        "servtax",
        "sieid2",
        "fld5filer",
        "tranfs",
    ],
    "fld6filersvm": [
        "brd2",
        "brdfcdm",
        "geo",
        "geoapps",
        "geodepot2",
        "geoenterprise",
        "meth1",
        "meth4",
        "ottfifp03",
        "ottfifp04",
        "stds1",
        "fld6filer",
    ],
    "fld7filersvm": [
        "alpha",
        "eit-awsfs-dev1",
        "g-spec",
        "mtlfp01",
        "oidhome",
        "oidnt6",
        "oidnt7",
        "ordd1",
        "orddghost",
        "rob1",
        "rob3",
        "robweb",
        "yeti-awsfs-dev1",
        "fld7filer",
    ],
    "fld8filersvm": [
        "ccjsnt1",
        "co1",
        "codalg3",
        "codcola",
        "codfile",
        "csmp",
        "ctces01",
        "ctces02",
        "dem4",
        "eit-awsfs-stg1",
        "hfss3",
        "lhs1",
        "lhs2",
        "lhs3",
        "lhs4",
        "lhs5",
        "lhs6",
        "saad1",
        "sasd6",
        "fld8filer",
    ],
    "fld9filersvm": [
        "blmamwnt",
        "hamg1",
        "hlth",
        "hlth_apps",
        "hlth_projects",
        "hlth_users",
        "semg1",
        "fld9filer",
    ],
    "stcffb03svm": [
        "stcffb03",
        "eit-bwsfs-dev1",
        "f6stcffb01",
        "stcffb01",
        "yeti-bwsfs-dev1",
    ],
    "stdcflr_sasfs10svm": [
        "stdcflr-sasfs10",
    ],
    "stdcflr_sasfs20svm": [
        "sttcflr-sasfs20",
        "ibspdatatest",
    ],
    "stmcflr_sasfs61svm": [
        "stmcflr-sasfs61",
        "ibspdatamgmt",
    ],
    "stpcflr_sasfs50svm": [
        "stpcflr-sasfs50",
        "f8lad",
        "ibspdata",
    ],
    "stqcflr_sasfs40svm": [
        "stqcflr-sasfs40",
        "ibspdataqa",
    ],
    "sttcflr_sasfs10svm": [
        "ibspdatadev",
    ],
    "stucflr_sasfs30svm": [
        "stucflr-sasfs30",
        "ibspdatauat",
    ],
    "taxfilersvm": [
        "taxfiler",
        "taxadmin",
    ],
}


def process_filer_path(path: str) -> str:
    """
    Remove various leading prefixes from filer path.
    """
    path = re.sub(r"\\", "/", path)
    path = re.sub(r"^[\/\.]*home[\/]+", "", path, flags=re.IGNORECASE)
    path = re.sub(r"^[\/\.]*jovyan[\/]+", "", path, flags=re.IGNORECASE)
    path = re.sub(r"^[\/\.]*filers{0,1}[\/]+", "", path, flags=re.IGNORECASE)
    path = re.sub(r"^[\/\.]*", "", path)
    return path


def remap_filer_aliases(filer: str) -> str:
    """
    Remap aliases for filer.
    """
    filer = filer.lower()
    for k, v in FILER_ALIASES.items():
        if filer in v:
            return k
    return filer


def get_components(path: str) -> str:
    "Get name of filer, share, and object key, from path."

    # First need to cleanup the path.
    path = process_filer_path(path)

    # Now can get the filer, share name, and object name.
    components = path.split("/", maxsplit=2)

    if len(components) == 0:
        # Root directory after preprocessing, filer unknown.
        return None, None, None

    # Filer name is known.
    filer = remap_filer_aliases(components[0])

    if len(components) == 1:
        # Missing share name.
        return filer, None, None

    # Share name is known.
    share = components[1]

    if len(components) == 2:
        # Missing object key.
        return filer, share, None

    # Remove leading slashes from object key.
    object_key = components[2].lstrip("/")
    return filer, share, object_key


def get_filer_env_config(path: str):
    "Get configuration from environment variables for specified filer."

    filer_name, share_name, object_key = get_components(path)

    url = os.environ[f"{filer_name}_url"] if filer_name is not None else None
    access_key = os.environ[f"{filer_name}_access"] if filer_name is not None else None
    secret_key = os.environ[f"{filer_name}_secret"] if filer_name is not None else None
    bucket_name = (
        os.environ[f"{filer_name}_{share_name}"] if share_name is not None else None
    )

    return url, access_key, secret_key, bucket_name, object_key


def get_all_filers() -> list:
    """
    Get list of all filers from environment variables.
    For each filer, get dictionary with:
    * base
    * url
    * access_key
    * secret_key
    """

    # Get list of filer bases.
    url_keys = filter(lambda s: re.match(r"^(.*filersvm|st.*svm)_url$", s), os.environ)
    all_bases = [re.sub(r"_url$", "", url) for url in url_keys]

    # Return dictionary for each filer base.
    return [
        {
            "base": base,
            "url": os.getenv(f"{base}_url"),
            "access_key": os.getenv(f"{base}_access"),
            "secret_key": os.getenv(f"{base}_secret"),
        }
        for base in all_bases
    ]


def init_all_filers(
    debug_print: bool = True,
    indicate_done_file: str = "/tmp/_filer_minio_client_init.done",
):
    """
    Sets the MinIO client alias for each filer.
    """

    if debug_print:
        print("Set MinIO client alias for each filer...")
    filers = get_all_filers()
    nf = len(filers)
    if debug_print:
        print(f"Found {nf} filers to initialize.")

    for filer in filers:
        alias_name = filer["base"]
        url = filer["url"]
        if debug_print:
            print(f"Add filer {alias_name} with url {url}.")

        r = subprocess.run(
            [
                "mc",
                "alias",
                "set",
                alias_name,
                url,
                filer["access_key"],
                filer["secret_key"],
            ],
            check=False,
            stdout=None if debug_print else subprocess.DEVNULL,
            stderr=None if debug_print else subprocess.DEVNULL,
        )

        if debug_print:
            if r.returncode == 0:
                print(f"Successfully added filer {alias_name}.")
            else:
                print(
                    f"Failed to add filer {alias_name}, command return status {r.returncode}."
                )

    try:
        if debug_print:
            print(
                "Create MinIO client initialization done indicator file:",
                indicate_done_file,
            )
        with open(indicate_done_file, "wb") as f:
            f.write(b"Done mc init.")
        if debug_print:
            print("Successfully created the indicator file.")
    except OSError as e:
        if debug_print:
            print("Error in create done indicator file:", e)


def get_mc_path(path: str) -> str:
    """
    Return the MinIO client path for input path as a string.
    """
    # Get the filer, share name, and object name.
    components = get_components(path)
    filer_name = components[0]
    share_name = components[1]
    object_key = components[2]

    # Some validations.
    if filer_name is None or len(filer_name) == 0:
        raise OSError("Missing filer name.")
    if share_name is None or len(share_name) == 0:
        raise OSError("Missing share name.")

    # Get necessary processing.
    bucket = os.getenv(f"{filer_name}_{share_name}")
    if bucket is None:
        raise OSError("Bucket for share not found.")

    if object_key is None:
        object_key = ""

    # Format is: filer_name/bucket/object_key
    return f"{filer_name}/{bucket}/{object_key}"


def check_filer_path(path: str) -> bool:
    """
    Return boolean indicating if path is to filer.
    True if filer path, False if local path.
    """

    # Use UNIX path separator.
    path = re.sub(r"\\", "/", path)

    # If UNC path, is to filer.
    if re.match(r"^\/\/", path):
        return True

    # Filer paths are those in /home/jovyan/filers/.
    path = os.path.abspath(path)
    return bool(re.match(r"^\/home\/jovyan\/filers\/", path))
