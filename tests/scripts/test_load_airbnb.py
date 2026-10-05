"""Offline tests for the Inside Airbnb CSV parser (no net, no DB)."""
import pytest

from scripts.load_airbnb import rows_from_csv, snapshot_date_from_path

CSV = (
    "id,name,host_id,neighbourhood,latitude,longitude,room_type,license\n"
    '900001,"Example listing, with comma",1,78702,30.26000,-97.74000,Entire home/apt,\n'
    "900002,Studio,2,78704,30.25000,-97.76000,Private room,2000-000001 OL\n"
    ",ghost row with no id,1,78701,30.0,-97.7,Entire home/apt,\n"
)


def test_rows_from_csv_maps_id_and_payload():
    rows = rows_from_csv(CSV)
    assert [lid for lid, _ in rows] == ["900001", "900002"]   # blank-id row skipped
    lid, payload = rows[0]
    assert payload["neighbourhood"] == "78702"
    assert payload["room_type"] == "Entire home/apt"
    assert payload["license"] == ""


def test_rows_from_csv_rejects_non_listings_csv():
    with pytest.raises(ValueError, match="'id' column"):
        rows_from_csv("foo,bar\n1,2\n")


def test_snapshot_date_from_path():
    assert snapshot_date_from_path("data/airbnb/2025-09-16/listings.csv") == "2025-09-16"


def test_snapshot_date_from_path_rejects_undated_dir():
    with pytest.raises(ValueError, match="snapshot date"):
        snapshot_date_from_path("data/airbnb/listings.csv")
