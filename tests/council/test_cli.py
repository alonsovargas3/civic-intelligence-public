from atx_council.cli import build_parser


def test_cli_parses_build():
    assert build_parser().parse_args(["build"]).cmd == "build"


def test_cli_parses_stats():
    assert build_parser().parse_args(["stats"]).cmd == "stats"
