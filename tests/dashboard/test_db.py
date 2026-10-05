from atx_dashboard.db import DDL


def test_ddl_defines_all_objects():
    for obj in (
        "metric_incidents_by_district",
        "metric_district_breakdown",
        "metric_311_response",
        "district_boundary",
    ):
        assert obj in DDL


def test_ddl_district_is_smallint_pk():
    assert "council_district smallint" in DDL
    assert "PRIMARY KEY (dataset, council_district, period_month)" in DDL
