# Installing your own packages

Packages you install with `pip` now stay on your notebook server between
restarts. Everyday use does not change: `pip install polars` is still all you
need to type.

## Where your packages go

Your server has two layers of Python packages:

| Layer | Location | Who writes it | Survives a restart? |
| --- | --- | --- | --- |
| The image | `/opt/conda/lib/python3.13/site-packages` | the Zone team | yes, but you get whatever the new image ships |
| Yours | `~/.local/lib/python3.13/site-packages` | you, with `pip install` | yes — it is on your workspace volume |

Your layer is searched **first**, so installing a newer `pandas` shadows the one
in the image without touching it. To see the exact path on your server:

```bash
python -c "import site; print(site.getusersitepackages())"
```

## pip

Just install things. No flags, no virtual environment needed:

```bash
pip install polars
```

Restart your kernel and `import polars` works. Restart the whole notebook server
and it still works.

To see what you have added on top of the image:

```bash
pip list --user
```

To upgrade or remove:

```bash
pip install --upgrade polars
pip uninstall polars
```

### Recording what you installed

`pip list --user --format=freeze > requirements.txt` writes a manifest of just
your own packages, without the thousands that ship in the image. Commit it next
to your notebooks and anyone (including you, on a new server) can reproduce your
environment with `pip install -r requirements.txt`.

## Virtual environments and Conda environments

Virtual environments are unaffected — inside one, `pip install` puts packages in
the environment, exactly as it always has:

```bash
python -m venv ~/myenv
source ~/myenv/bin/activate
pip install polars      # goes to ~/myenv, not ~/.local
```

Named Conda environments already persist: `~/.condarc` sets
`envs_dirs: $HOME/.conda/envs`, which is on your workspace volume. `mamba` reads
the same setting, so either one works.

```bash
conda create -n myproject python=3.13 polars
conda activate myproject
```

`conda install` **into the base environment** (the `(base)` prompt, with no
environment activated) still does not persist — it writes into `/opt/conda` and
is lost on restart. Use a named environment, or `pip install`, for anything you
want to keep.

## When you need the old behaviour: `--no-user`

A few things must go into the base environment rather than your home directory.
Pass `--no-user`:

- **Jupyter *server* extensions** — the ones that run inside the notebook server
  itself. The server process deliberately ignores `~/.local`
  (see [Recovering](#recovering-from-a-broken-install)), so it cannot import an
  extension installed there.

  ```bash
  pip install --no-user jupyter-resource-usage
  ```

  This one does not persist: `/opt/conda` is part of the image, so the extension
  is gone when you next restart your notebook server. Anything you want
  permanently should be requested from the Zone team so it can be added to the
  image.

  JupyterLab *front-end* extensions are different — they are found on disk under
  `~/.local/share/jupyter/labextensions`, not imported, so a plain
  `pip install jupyterlab-git` works and persists. You still need to restart the
  notebook server once for the server to pick it up.

- **`pip install --target <dir>`**, which cannot be combined with a user
  install.

  ```bash
  pip install --no-user --target ./vendor requests
  ```

Similarly, `pip config set` needs an explicit scope now that the image ships a
read-only site-wide config. Use `pip config --user set ...`.

## Recovering from a broken install

A bad package cannot lock you out of your server. JupyterLab runs with `python
-s`, which means the server process itself never reads `~/.local`; only your
kernels and terminals do. If an install breaks your kernels, open a terminal and
undo it:

```bash
pip uninstall <package>
```

If you want a clean slate, delete your whole user layer. The image's packages
are untouched:

```bash
rm -rf ~/.local/lib/python3.13/site-packages
```

`pip uninstall` removes your copy first, so uninstalling a package you had
upgraded leaves the image's version in place — that is how you go back to the
default. Running it a *second* time deletes the image's copy too; restart the
notebook server to get that back.

## When the image is upgraded

The Zone team updates the notebook image regularly. Two things to know:

- **Your packages stay**, and they keep shadowing the image. If the new image
  ships a newer `pandas` but you installed your own, you still get yours. Run
  `pip list --user` occasionally and uninstall anything you no longer need to
  pin, so you pick up the image's updates.
- **A new Python version starts you fresh.** Your packages live under a
  version-specific path (`~/.local/lib/python3.13/...`). When the image moves to
  Python 3.14, that directory is simply not read any more, and you reinstall
  what you need. This is deliberate: packages with compiled C extensions —
  `numpy`, `pyarrow`, `psycopg2` and friends — are built against one Python
  version and crash if loaded into another. Your old directory is left in place
  — `ls ~/.local/lib/python3.13/site-packages` still tells you what you had —
  but keeping a `requirements.txt` makes the move one command instead.

## Packages that need system libraries

`pip install` cannot install `apt` packages. If a package fails to build with an
error about a missing header or library (`Python.h`, `libpq-dev`, a compiler),
that dependency has to go into the image — open a request with the Zone team.
Wheels that bundle their own libraries (most of PyPI, including `numpy`,
`pyarrow` and `duckdb`) install fine.
