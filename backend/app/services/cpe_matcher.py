"""Version-aware CPE→CVE matcher (Month 3, Phase 2).

Given a piece of installed software ``(vendor, product, version)`` this service
finds the CVEs that affect it, using the per-CVE affected-version ranges Phase 1
persists into ``cve_cpe_match``. Each match carries a confidence tier:

* ``high``        — the asset's own CPE URI matched, or an exact
                    vendor/product/version equality against a concrete CPE.
* ``medium``      — normalized name matched and the version falls inside a
                    published version range (the CPE was inferred).
* ``low``         — name-only match: the asset has no version, or the criterion
                    is version-agnostic (``cpe:...:*``) with no range bounds.
* ``needs_review``— the version could not be parsed / compared. We never guess
                    here: a false ``high`` erodes trust permanently, so an
                    unparseable comparison is surfaced for a human instead.

The pure helpers (``parse_version``, ``compare_versions``,
``version_in_range``, ``evaluate_criterion``, ``assign_confidence``) hold all
the comparison logic and are unit-tested without a database; ``CpeMatcher`` is
the thin DB-backed pipeline that reuses ``vendor_aliases`` for normalization,
reads ``cve_cpe_match``, and writes resolved CPEs back to ``cpe_match_cache``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.cpe_match_cache import CpeMatchCache
from app.db.cve_cpe_match import CveCpeMatch
from app.db.engine import get_session
from app.repositories.vendor_aliases import SqlVendorAliasRepository

logger = logging.getLogger(__name__)

Confidence = Literal["high", "medium", "low", "needs_review"]

# Numeric stand-ins so the cache (which stores a float confidence) and the
# matcher tiers stay aligned in one place.
_CONFIDENCE_SCORE: dict[Confidence, float] = {
    "high": 1.0,
    "medium": 0.7,
    "low": 0.4,
    "needs_review": 0.2,
}

# Values NVD uses in a version field / bound that mean "no concrete version".
_VERSION_WILDCARDS = {"", "*", "-"}

# Pre-release ranking: lower sorts before a final release. ``dev``/``snapshot``
# sit below ``alpha``; a final release outranks all of them.
_PRE_RANK: dict[str, int] = {
    "dev": -1,
    "snapshot": -1,
    "alpha": 0,
    "a": 0,
    "beta": 1,
    "b": 1,
    "pre": 2,
    "preview": 2,
    "rc": 3,
    "c": 3,
}

# Fully-anchored loose-semver parser. Anything that does not match end-to-end is
# treated as unparseable (→ needs_review) rather than coerced, so we never
# silently equate two genuinely different versions.
_VERSION_RE = re.compile(
    r"^(?:(?P<epoch>\d+):)?"
    r"(?P<release>\d+(?:\.\d+)*)"
    r"(?P<letter>[a-z])?"  # OpenSSL-style trailing release letter, e.g. 1.0.1f
    r"(?:[-_~.](?P<pre>(?:alpha|beta|preview|pre|rc|dev|snapshot)\d*))?"
    r"$"
)


@dataclass(frozen=True)
class _Version:
    """Comparable representation of a parsed version string."""

    epoch: int
    release: tuple[int, ...]
    letter: str
    # (1,) for a final release; (0, rank, prenum) for a pre-release so that any
    # final release outranks any pre-release during tuple comparison.
    pre: tuple[int, ...]


@dataclass(frozen=True)
class CpeMatch:
    """One asset-software ↔ CVE match with its confidence tier."""

    cve_id: str
    cpe_uri: str
    confidence: Confidence
    version_in_range: bool | None
    reason: str


def parse_version(raw: str | None) -> _Version | None:
    """Parse a messy real-world version string into a comparable form.

    Handles epochs (``1:2.3``), trailing release letters (``1.0.1f``), and
    common pre-release suffixes (``-rc1``, ``beta2``). Returns ``None`` when the
    string cannot be confidently parsed, so callers default to ``needs_review``.
    """
    if not raw:
        return None
    text = raw.strip().lower()
    if not text:
        return None
    if text.startswith("v"):
        text = text[1:]
    # Drop build metadata; it never affects precedence.
    text = text.split("+", 1)[0]

    match = _VERSION_RE.match(text)
    if match is None:
        return None

    epoch = int(match.group("epoch")) if match.group("epoch") else 0
    release = tuple(int(part) for part in match.group("release").split("."))
    letter = match.group("letter") or ""

    pre_raw = match.group("pre")
    if not pre_raw:
        pre: tuple[int, ...] = (1,)
    else:
        word_match = re.match(r"([a-z]+)(\d*)", pre_raw)
        # word_match always succeeds given the regex alternation above.
        word = word_match.group(1)  # type: ignore[union-attr]
        num = int(word_match.group(2)) if word_match.group(2) else 0  # type: ignore[union-attr]
        pre = (0, _PRE_RANK.get(word, 0), num)

    return _Version(epoch=epoch, release=release, letter=letter, pre=pre)


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


def compare_versions(a: str | None, b: str | None) -> int | None:
    """Compare two version strings.

    Returns ``-1``/``0``/``1`` like ``cmp``, or ``None`` if either version is
    unparseable (the caller should then treat the comparison as unknown).
    """
    pa = parse_version(a)
    pb = parse_version(b)
    if pa is None or pb is None:
        return None

    if pa.epoch != pb.epoch:
        return _sign(pa.epoch - pb.epoch)

    # Pad the shorter release tuple with zeros so 1.2 == 1.2.0.
    length = max(len(pa.release), len(pb.release))
    ra = pa.release + (0,) * (length - len(pa.release))
    rb = pb.release + (0,) * (length - len(pb.release))
    if ra != rb:
        return -1 if ra < rb else 1

    if pa.letter != pb.letter:
        return -1 if pa.letter < pb.letter else 1

    if pa.pre != pb.pre:
        return -1 if pa.pre < pb.pre else 1

    return 0


def _clean_bound(value: str | None) -> str | None:
    """Normalize a range bound, treating wildcards/blanks as 'no bound'."""
    if value is None:
        return None
    stripped = value.strip()
    return None if stripped in _VERSION_WILDCARDS else stripped


def version_in_range(
    version: str | None,
    *,
    start_including: str | None = None,
    start_excluding: str | None = None,
    end_including: str | None = None,
    end_excluding: str | None = None,
) -> bool | None:
    """Return whether ``version`` falls within the given bounds.

    ``None`` is returned when any required comparison is indeterminate (an
    unparseable bound or version), so the caller can fall back to
    ``needs_review`` rather than risk a false match.
    """
    checks: list[tuple[str | None, str]] = [
        (_clean_bound(start_including), ">="),
        (_clean_bound(start_excluding), ">"),
        (_clean_bound(end_including), "<="),
        (_clean_bound(end_excluding), "<"),
    ]
    for bound, op in checks:
        if bound is None:
            continue
        cmp = compare_versions(version, bound)
        if cmp is None:
            return None
        if op == ">=" and cmp < 0:
            return False
        if op == ">" and cmp <= 0:
            return False
        if op == "<=" and cmp > 0:
            return False
        if op == "<" and cmp >= 0:
            return False
    return True


def cpe_version_field(cpe_uri: str | None) -> str | None:
    """Extract the version component (index 5) from a CPE 2.3 URI."""
    if not cpe_uri:
        return None
    parts = cpe_uri.split(":")
    return parts[5] if len(parts) > 5 else None


def _cpe_core(cpe_uri: str | None) -> str | None:
    """Lowercased vendor:product:version core of a CPE URI for equality checks."""
    if not cpe_uri:
        return None
    parts = cpe_uri.lower().split(":")
    if len(parts) <= 5:
        return None
    return ":".join(parts[3:6])


def _cpe_version_concrete(cpe_uri: str | None) -> bool:
    """True only when the CPE pins a real version (not ``*``/``-``/empty)."""
    version = cpe_version_field(cpe_uri)
    return version is not None and version.strip().lower() not in _VERSION_WILDCARDS


def evaluate_criterion(
    asset_version: str | None,
    *,
    cpe_uri: str,
    start_including: str | None = None,
    start_excluding: str | None = None,
    end_including: str | None = None,
    end_excluding: str | None = None,
) -> bool | None:
    """Decide whether ``asset_version`` is affected by a single CPE criterion.

    Returns ``True`` (affected), ``False`` (not affected), or ``None`` when the
    version is needed but cannot be compared.
    """
    has_range = any(
        _clean_bound(b) is not None
        for b in (start_including, start_excluding, end_including, end_excluding)
    )
    cpe_version = cpe_version_field(cpe_uri)
    concrete = cpe_version is not None and cpe_version.strip().lower() not in _VERSION_WILDCARDS

    # Version-agnostic criterion (cpe:...:*:... with no bounds): every version
    # of this product is listed as vulnerable.
    if not has_range and not concrete:
        return True

    if not asset_version or not asset_version.strip():
        # A version is required to decide, but none was supplied.
        return None

    if has_range:
        return version_in_range(
            asset_version,
            start_including=start_including,
            start_excluding=start_excluding,
            end_including=end_including,
            end_excluding=end_excluding,
        )

    cmp = compare_versions(asset_version, cpe_version)
    if cmp is None:
        return None
    return cmp == 0


def assign_confidence(
    *,
    verdict: bool | None,
    asset_version: str | None,
    asset_cpe_uri: str | None,
    criterion_cpe_uri: str,
    has_range: bool,
    cpe_version_concrete: bool,
) -> Confidence | None:
    """Map an evaluated criterion to a confidence tier.

    Returns ``None`` when the criterion does not produce a finding (the version
    is confirmed outside every affected range).
    """
    if verdict is False:
        return None
    if verdict is None:
        return "needs_review"

    # verdict is True from here on.
    # An exact-CPE match only earns ``high`` when BOTH sides pin a concrete
    # version. Two wildcard-version CPEs (e.g. ``...:log4j:*:...``) share a core
    # but only agree on vendor/product — granting ``high`` there would be the
    # version-blind false positive the roadmap forbids; fall through to the
    # range/concrete logic, which yields ``medium``/``low`` as appropriate.
    if (
        asset_cpe_uri
        and _cpe_core(asset_cpe_uri) == _cpe_core(criterion_cpe_uri)
        and _cpe_version_concrete(asset_cpe_uri)
        and _cpe_version_concrete(criterion_cpe_uri)
    ):
        return "high"
    if not asset_version or not asset_version.strip():
        return "low"
    if has_range:
        return "medium"
    if cpe_version_concrete:
        return "high"
    return "low"


def normalize_cpe_token(value: str | None) -> str:
    """Normalize a vendor/product name to a CPE-style token.

    Lowercases, trims, and collapses runs of whitespace/separators into the
    single underscore CPE uses (e.g. ``"Apache Software"`` → ``"apache_software"``).
    """
    if not value:
        return ""
    token = value.strip().lower()
    token = re.sub(r"[\s\-]+", "_", token)
    token = re.sub(r"_+", "_", token)
    return token.strip("_")


class CpeMatcher:
    """DB-backed pipeline that matches asset software to affected CVEs."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        alias_repo: SqlVendorAliasRepository | None = None,
    ) -> None:
        self._session = session
        self._aliases = alias_repo or SqlVendorAliasRepository(session)

    async def match(
        self,
        *,
        vendor: str,
        product: str,
        version: str | None = None,
        cpe_uri: str | None = None,
        write_back: bool = True,
    ) -> list[CpeMatch]:
        """Return the CVE matches for one piece of installed software.

        Names are normalized through ``vendor_aliases``; affected-version ranges
        come from ``cve_cpe_match``. Each match is assigned a confidence tier and,
        when ``write_back`` is set, the resolved CPE is cached for next time.
        """
        canonical_vendor = await self._aliases.resolve(vendor)
        norm_vendor = normalize_cpe_token(canonical_vendor)
        norm_product = normalize_cpe_token(product)
        if not norm_vendor or not norm_product:
            return []

        rows = await self._fetch_criteria(norm_vendor, norm_product)

        matches: list[CpeMatch] = []
        for row in rows:
            if not row.vulnerable:
                continue

            verdict = evaluate_criterion(
                version,
                cpe_uri=row.cpe_uri,
                start_including=row.version_start_including,
                start_excluding=row.version_start_excluding,
                end_including=row.version_end_including,
                end_excluding=row.version_end_excluding,
            )
            has_range = any(
                _clean_bound(b) is not None
                for b in (
                    row.version_start_including,
                    row.version_start_excluding,
                    row.version_end_including,
                    row.version_end_excluding,
                )
            )
            cpe_ver = cpe_version_field(row.cpe_uri)
            concrete = cpe_ver is not None and cpe_ver.strip().lower() not in _VERSION_WILDCARDS

            confidence = assign_confidence(
                verdict=verdict,
                asset_version=version,
                asset_cpe_uri=cpe_uri,
                criterion_cpe_uri=row.cpe_uri,
                has_range=has_range,
                cpe_version_concrete=concrete,
            )
            if confidence is None:
                continue

            matches.append(
                CpeMatch(
                    cve_id=row.cve_id,
                    cpe_uri=row.cpe_uri,
                    confidence=confidence,
                    version_in_range=verdict,
                    reason=self._reason(
                        confidence,
                        has_range=has_range,
                        concrete=concrete,
                        version=version,
                    ),
                )
            )

        if write_back and matches:
            await self._write_back_cache(norm_vendor, norm_product, version, matches)

        return matches

    @staticmethod
    def _reason(
        confidence: Confidence,
        *,
        has_range: bool,
        concrete: bool,
        version: str | None,
    ) -> str:
        if confidence == "needs_review":
            return "version could not be parsed or compared"
        if confidence == "high":
            return "exact CPE / vendor-product-version match"
        if confidence == "medium":
            return "normalized name match; version within published range"
        if not version:
            return "name-only match (no version supplied)"
        if not has_range and not concrete:
            return "name match; criterion applies to all versions"
        return "name match"

    async def _fetch_criteria(self, norm_vendor: str, norm_product: str) -> list[CveCpeMatch]:
        """Load every CPE criterion for a normalized vendor/product pair."""
        stmt = select(CveCpeMatch).where(
            func.lower(CveCpeMatch.vendor) == norm_vendor,
            func.lower(CveCpeMatch.product) == norm_product,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _write_back_cache(
        self,
        norm_vendor: str,
        norm_product: str,
        version: str | None,
        matches: list[CpeMatch],
    ) -> None:
        """Record the resolved CPE for this software in ``cpe_match_cache``.

        Best-effort: a cache miss just means the next lookup recomputes. The
        highest-confidence match wins, mirroring the (vendor, product, version)
        unique key on the cache table.
        """
        best = max(matches, key=lambda m: _CONFIDENCE_SCORE[m.confidence])
        version_normalized = version.strip().lower() if version and version.strip() else None

        existing = await self._session.execute(
            select(CpeMatchCache).where(
                CpeMatchCache.vendor_normalized == norm_vendor,
                CpeMatchCache.product_normalized == norm_product,
                CpeMatchCache.version_normalized == version_normalized,
            )
        )
        row = existing.scalar_one_or_none()
        score = _CONFIDENCE_SCORE[best.confidence]
        if row is None:
            self._session.add(
                CpeMatchCache(
                    vendor_normalized=norm_vendor,
                    product_normalized=norm_product,
                    version_normalized=version_normalized,
                    cpe_uri=best.cpe_uri[:500],
                    confidence_score=score,
                )
            )
        else:
            row.cpe_uri = best.cpe_uri[:500]
            row.confidence_score = score
            row.last_verified_at = func.now()


def get_cpe_matcher(session: AsyncSession = Depends(get_session)) -> CpeMatcher:
    """Factory used as a FastAPI dependency."""
    return CpeMatcher(session)
