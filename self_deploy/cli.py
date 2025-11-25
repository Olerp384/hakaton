"""Command line entrypoints for self-deploy."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="self-deploy",
        description="Generate CI/CD pipelines and Dockerfiles based on repository analysis.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate",
        help="Generate CI/CD pipeline and Dockerfile assets.",
    )
    generate.add_argument(
        "--repo",
        required=True,
        help="Git repository URL to analyze.",
    )
    generate.add_argument(
        "--branch",
        default=None,
        help="Optional branch to check out.",
    )
    generate.add_argument(
        "--ci",
        default="gitlab",
        choices=["gitlab"],
        help="Target CI provider.",
    )
    generate.add_argument(
        "--output",
        default=None,
        help="Path to write generated artifacts.",
    )
    generate.add_argument(
        "--config",
        default=None,
        help="Path to optional configuration file.",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """Parse arguments and print them."""
    parser = build_parser()
    args = parser.parse_args(argv)
    print(args)


if __name__ == "__main__":
    main()
