from atx_anomaly.db import DDL


def test_ddl_defines_both_tables():
    assert "anomaly_flag" in DDL
    assert "metric_assessment_equity" in DDL


def test_anomaly_flag_has_review_state_default():
    assert "review_state text    NOT NULL DEFAULT 'unreviewed'" in DDL
    # uniqueness so a re-run upserts rather than duplicates
    assert "UNIQUE (detector, cluster_kind, cluster_id, roll_year)" in DDL


def test_detail_table_keyed_on_year_class_zip():
    assert "PRIMARY KEY (roll_year, class, zip)" in DDL
