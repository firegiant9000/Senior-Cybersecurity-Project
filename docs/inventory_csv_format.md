# Inventory CSV Upload Format

The CSV inventory upload endpoint (`POST /api/v1/organizations/{org_id}/inventory/uploads/csv/import`)
accepts a UTF-8 CSV file with the following columns. A sample is downloadable
from the upload page or at [/sample-inventory.csv](../frontend/public/sample-inventory.csv).

## Columns

| Column        | Required | Notes                                                          |
|---------------|----------|----------------------------------------------------------------|
| `hostname`    | yes      | 1–255 chars. Uniquely identifies the asset within your org.    |
| `ip_address`  | no       | IPv4/IPv6 or empty.                                            |
| `os_name`     | no       | Free text (e.g. `Windows`, `Ubuntu`, `macOS`).                 |
| `os_version`  | no       | Free text.                                                     |
| `vendor`      | no*      | Software vendor name. *Required if `product` is set.*          |
| `product`     | no*      | Product name. *Required if `vendor` is set.*                   |
| `version`     | no       | Product version string.                                        |
| `notes`       | no       | Free-text annotation; preserved on the asset metadata.         |

Each row represents one `(asset, software)` pair. Multiple rows with the same
`hostname` are grouped into one asset with several software entries.

## Validation rules

- Header row required; columns may appear in any order.
- Max **10,000 rows** per upload (larger inventories: split or use the M365
  integration in Phase E).
- Duplicate `(hostname, vendor, product, version)` tuples within a single
  upload are skipped with a row-number warning.
- Re-uploading the same CSV is idempotent: matching assets get a refreshed
  `last_seen` rather than a new row.
- Invalid `ip_address` values are flagged in the preview response but do not
  block import — they are stored as-is and surfaced as warnings.

## Background matching

When an import commits, a background job cross-references every
`asset_software` row against the CISA KEV catalog by **literal vendor +
product match** (case-insensitive). Matches show up in the Assets page with
the `KEV` source badge. False positives are expected — the Month 3 CPE
matcher will refine these.

## Sample

```csv
hostname,ip_address,os_name,os_version,vendor,product,version,notes
web-prod-01,10.0.1.10,Ubuntu,22.04,nginx,nginx,1.24.0,public web tier
db-prod-01,10.0.2.20,Ubuntu,22.04,PostgreSQL,postgresql,15.4,primary OLTP
laptop-arlo,,macOS,14.2,Apple,macOS,14.2.1,
```
