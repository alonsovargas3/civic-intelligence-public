from atx_anomaly.cli import build_parser


def test_cli_run_d3a_defaults():
    args = build_parser().parse_args(["run-d3a"])
    assert args.cmd == "run-d3a"
    assert args.roll_year == 2025
    assert args.klass == "A1"
    assert args.min_parcels == 50
    assert args.z == 3.5
    assert args.roll_stage == "certified"


def test_cli_run_d3a_overrides():
    args = build_parser().parse_args(
        ["run-d3a", "--roll-year", "2024", "--class", "A4", "--min-parcels", "30",
         "--z", "3.0", "--stage", "supplement"])
    assert args.roll_year == 2024
    assert args.klass == "A4"
    assert args.min_parcels == 30
    assert args.z == 3.0
    assert args.roll_stage == "supplement"


def test_cli_parses_stats():
    assert build_parser().parse_args(["stats"]).cmd == "stats"


def test_cli_run_d7_defaults():
    args = build_parser().parse_args(["run-d7"])
    assert args.cmd == "run-d7"
    assert args.since is None
    assert args.window_year == 0
    assert args.min_cases == 200
    assert args.min_type_cases == 20
    assert args.high_ratio == 1.5


def test_cli_run_d4_defaults():
    args = build_parser().parse_args(["run-d4"])
    assert args.cmd == "run-d4"
    assert args.roll_year == 2025
    assert args.kind == "institutional"
    assert args.min_parcels == 20
    assert args.low_ratio == 0.7


def test_cli_run_d4_overrides():
    args = build_parser().parse_args(
        ["run-d4", "--kind", "government", "--min-parcels", "10", "--low-ratio", "0.6"])
    assert args.kind == "government"
    assert args.min_parcels == 10
    assert args.low_ratio == 0.6


def test_cli_run_assessment_cod_defaults():
    args = build_parser().parse_args(["run-assessment-cod"])
    assert args.cmd == "run-assessment-cod"
    assert args.roll_year == 2025
    assert args.roll_stage == "certified"
    assert args.min_parcels == 30


def test_cli_run_assessment_cod_overrides():
    args = build_parser().parse_args(
        ["run-assessment-cod", "--roll-year", "2024", "--stage", "supplement",
         "--min-parcels", "50"])
    assert args.roll_year == 2024
    assert args.roll_stage == "supplement"
    assert args.min_parcels == 50


def test_cli_run_d7_overrides():
    args = build_parser().parse_args(
        ["run-d7", "--since", "2020-01-01", "--window-year", "2024",
         "--min-cases", "50", "--min-type-cases", "10", "--high-ratio", "2.0"])
    assert args.since == "2020-01-01"
    assert args.window_year == 2024
    assert args.min_cases == 50
    assert args.min_type_cases == 10
    assert args.high_ratio == 2.0
