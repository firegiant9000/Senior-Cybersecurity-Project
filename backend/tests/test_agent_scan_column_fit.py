"""Every string the agent upload schema accepts fits the column it is stored in (issue #246).

A schema cap wider than its column lets a payload pass validation and then fail at insert
with a 500. The end-to-end upload is in tests/authz/tenancy/test_agent_upload_maximal_strings.py.
"""

import annotated_types
import pytest
from sqlalchemy import String

from app.db.asset import Asset
from app.db.asset_software import AssetSoftware
from app.db.cpe_match_cache import CpeMatchCache
from app.schemas.agent_scan import ScanHost, ScanSoftware


def _max_len(model, field: str) -> int:
    for item in model.model_fields[field].metadata:
        if isinstance(item, annotated_types.MaxLen):
            return item.max_length
    raise AssertionError(f"{model.__name__}.{field} has no MaxLen")


def _column_len(orm, column: str) -> int:
    col_type = orm.__table__.c[column].type
    assert isinstance(col_type, String), f"{orm.__tablename__}.{column} is not a String"
    assert col_type.length is not None, f"{orm.__tablename__}.{column} is unbounded"
    return col_type.length


@pytest.mark.parametrize(
    ("schema", "field", "orm", "column"),
    [
        (ScanHost, "hostname", Asset, "hostname"),
        (ScanHost, "ip_address", Asset, "ip_address"),
        (ScanHost, "os_name", Asset, "os_name"),
        (ScanHost, "os_version", Asset, "os_version"),
        (ScanSoftware, "vendor", AssetSoftware, "vendor"),
        (ScanSoftware, "product", AssetSoftware, "product"),
        (ScanSoftware, "version", AssetSoftware, "version"),
        # The CPE matcher caches the lowercased software version (and skips one that
        # lowercasing lengthened past the column: test_cpe_matcher.py).
        (ScanSoftware, "version", CpeMatchCache, "version_normalized"),
    ],
)
def test_schema_cap_fits_column(schema, field, orm, column):
    assert _max_len(schema, field) <= _column_len(orm, column)
