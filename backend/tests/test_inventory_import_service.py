"""Unit tests for the CSV inventory parser (Month 2 Phase C)."""

from app.services.inventory_import import MAX_CSV_ROWS, parse_csv


def test_parse_csv_happy_path():
    text = (
        "hostname,ip_address,os_name,os_version,vendor,product,version,notes\n"
        "web-1,10.0.0.1,Ubuntu,22.04,nginx,nginx,1.24.0,prod\n"
        "web-1,10.0.0.1,Ubuntu,22.04,openssl,openssl,3.0.2,\n"
        "db-1,10.0.0.2,Ubuntu,22.04,PostgreSQL,postgresql,15.4,\n"
    )
    result = parse_csv(text)
    assert result.valid_rows == 3
    assert result.distinct_assets == 2
    assert result.distinct_software == 3
    assert result.invalid_rows == 0


def test_parse_csv_missing_required_column():
    text = "bogus_column\nvalue\n"
    result = parse_csv(text)
    assert result.valid_rows == 0
    assert "Missing required columns" in result.errors[0]["errors"][0]


def test_parse_csv_missing_hostname():
    text = "hostname,vendor,product\n,Microsoft,Windows\nweb-1,nginx,nginx\n"
    result = parse_csv(text)
    assert result.valid_rows == 1
    assert any("missing hostname" in e["errors"][0] for e in result.errors)


def test_parse_csv_dedup_within_upload():
    text = (
        "hostname,vendor,product,version\n"
        "web-1,nginx,nginx,1.24.0\n"
        "web-1,nginx,nginx,1.24.0\n"  # duplicate
        "web-1,nginx,nginx,1.25.0\n"  # different version → kept
    )
    result = parse_csv(text)
    assert result.valid_rows == 2
    assert any("duplicate" in e["errors"][0] for e in result.errors)


def test_parse_csv_invalid_ip_soft_warning():
    text = "hostname,ip_address,vendor,product\nweb-1,not-an-ip,nginx,nginx\n"
    result = parse_csv(text)
    # Row is kept (soft warning), error still recorded.
    assert result.valid_rows == 1
    assert any("invalid ip_address" in err for e in result.errors for err in e["errors"])


def test_parse_csv_vendor_without_product_rejected():
    text = "hostname,vendor,product\nweb-1,Microsoft,\n"
    result = parse_csv(text)
    assert result.valid_rows == 0
    assert any("vendor and product" in e["errors"][0] for e in result.errors)


def test_parse_csv_row_cap():
    rows = ["hostname,vendor,product"]
    for i in range(MAX_CSV_ROWS + 5):
        rows.append(f"host-{i},nginx,nginx")
    text = "\n".join(rows) + "\n"
    result = parse_csv(text)
    assert result.valid_rows == MAX_CSV_ROWS
    assert any(
        f"Exceeded maximum of {MAX_CSV_ROWS}" in err for e in result.errors for err in e["errors"]
    )


def test_parse_csv_whitespace_normalization():
    text = "hostname,vendor,product\n  web-1  ,  Microsoft  ,  Windows  \n"
    result = parse_csv(text)
    assert result.valid_rows == 1
    assert result.rows[0].hostname == "web-1"
    assert result.rows[0].vendor == "Microsoft"
    assert result.rows[0].product == "Windows"


def test_parse_csv_utf8_bom_handled_by_caller():
    # parse_csv expects already-decoded text; route handler strips BOM.
    text = "hostname,vendor,product\nweb-1,nginx,nginx\n"
    result = parse_csv(text)
    assert result.valid_rows == 1
