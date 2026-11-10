"""An agent upload with every host/software string at its schema cap is stored intact (issue #246).

Before migration 053 these values passed validation and then overflowed their columns at insert,
so the agent got a 500 instead of a 201. Runs against the real database.
"""

from sqlalchemy import select

from app.db.asset import Asset
from app.db.asset_software import AssetSoftware
from app.db.engine import AsyncSessionLocal
from app.schemas.agent_scan import ScanHost, ScanSoftware
from tests.authz.tenancy._agents import issue_agent, scan_payload
from tests.test_agent_scan_column_fit import _max_len

UPLOAD_URL = "/api/v1/inventory/scans"


def _fill(prefix: str, length: int) -> str:
    return (prefix + "x" * length)[:length]


async def test_upload_with_maximal_strings_is_stored(world, authz_client):
    client = await authz_client((await issue_agent(world.a)).raw_token)
    payload = scan_payload(world.a)
    host = {
        "hostname": _fill(f"{world.a.marker}-maxhost-", _max_len(ScanHost, "hostname")),
        "os_name": _fill("os-", _max_len(ScanHost, "os_name")),
        "os_version": _fill("osv-", _max_len(ScanHost, "os_version")),
        "arch": _fill("arch-", _max_len(ScanHost, "arch")),
        "ip_address": _fill("ip-", _max_len(ScanHost, "ip_address")),
    }
    software = {
        "vendor": _fill("vendor-", _max_len(ScanSoftware, "vendor")),
        "product": _fill("product-", _max_len(ScanSoftware, "product")),
        "version": _fill("1.0.0-", _max_len(ScanSoftware, "version")),
    }
    payload["host"] = host
    payload["software"] = [software]

    resp = await client.post(UPLOAD_URL, json=payload)

    assert resp.status_code == 201, resp.text
    async with AsyncSessionLocal() as session:
        asset = (
            await session.execute(
                select(Asset).where(
                    Asset.org_id == world.a.org_id, Asset.hostname == host["hostname"]
                )
            )
        ).scalar_one()
        stored = (
            (await session.execute(select(AssetSoftware).where(AssetSoftware.asset_id == asset.id)))
            .scalars()
            .all()
        )
    assert (asset.ip_address, asset.os_name, asset.os_version) == (
        host["ip_address"],
        host["os_name"],
        host["os_version"],
    )
    assert [(s.vendor, s.product, s.version) for s in stored] == [
        (software["vendor"], software["product"], software["version"])
    ]
