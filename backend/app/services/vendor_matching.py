"""Shared vendor-name normalization for KEV matching.

Used by both the vendor-alerts service (full match pipeline) and the
org-vendor list query (KEV count badge) so the two stay consistent.
"""

# Common cloud/SaaS display names that don't appear in the KEV catalog
# under those names. Maps lowercase org-entered name -> canonical KEV vendor.
VENDOR_ALIASES: dict[str, str] = {
    "aws": "Amazon",
    "amazon aws": "Amazon",
    "azure": "Microsoft",
    "azure ad": "Microsoft",
    "microsoft azure": "Microsoft",
    "microsoft 365": "Microsoft",
    "office 365": "Microsoft",
    "ms 365": "Microsoft",
    "gcp": "Google",
    "google cloud": "Google",
    "google cloud platform": "Google",
    "google workspace": "Google",
    "g suite": "Google",
}
