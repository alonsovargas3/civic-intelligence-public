from atx_ownership.cli import build_parser


def test_cli_parses_build_crosswalk():
    assert build_parser().parse_args(["build-crosswalk"]).cmd == "build-crosswalk"


def test_cli_build_defaults():
    args = build_parser().parse_args(["build"])
    assert args.cmd == "build"
    assert args.roll_year == 2025
    assert args.roll_stage == "certified"
    assert args.top_n == 100


def test_cli_build_overrides():
    args = build_parser().parse_args(
        ["build", "--roll-year", "2024", "--stage", "supplement", "--top-n", "50"])
    assert args.roll_year == 2024
    assert args.roll_stage == "supplement"
    assert args.top_n == 50


def test_cli_parses_stats():
    assert build_parser().parse_args(["stats"]).cmd == "stats"


def test_cli_build_differential_defaults():
    args = build_parser().parse_args(["build-differential"])
    assert args.cmd == "build-differential"
    assert args.roll_year == 2025
    assert args.roll_stage == "certified"
    assert args.window_start == "2024-01-01"
    assert args.min_parcels == 30


def test_cli_build_differential_overrides():
    args = build_parser().parse_args(
        ["build-differential", "--roll-year", "2024", "--stage", "supplement",
         "--window-start", "2023-01-01", "--min-parcels", "10"])
    assert args.roll_year == 2024
    assert args.roll_stage == "supplement"
    assert args.window_start == "2023-01-01"
    assert args.min_parcels == 10
