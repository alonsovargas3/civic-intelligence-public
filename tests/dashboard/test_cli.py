from atx_dashboard.cli import build_parser


def test_cli_parses_refresh():
    assert build_parser().parse_args(["refresh"]).cmd == "refresh"


def test_cli_parses_load_boundaries():
    assert build_parser().parse_args(["load-boundaries"]).cmd == "load-boundaries"


def test_cli_serve_has_port_default():
    args = build_parser().parse_args(["serve"])
    assert args.cmd == "serve"
    assert args.port == 8000
