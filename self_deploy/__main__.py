"""Module entrypoint for `python -m self_deploy`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
