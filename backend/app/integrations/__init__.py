"""Integration placeholders for external data sources."""

# Placeholder: implement integrations as separate packages
#
# Structure:
# app/integrations/
#   cisa_kev/
#     __init__.py
#     client.py       # API client
#     parser.py       # Response parsing
#     models.py       # CISA-specific models
#   nvd/
#     __init__.py
#     client.py
#     parser.py
#     models.py
#   shodan/
#     __init__.py
#     client.py
#     parser.py
#     models.py
#
# Each integration should:
# 1. Fetch data from external source
# 2. Parse and normalize response
# 3. Store in IngestRun table
# 4. Handle errors gracefully
#
# Example usage in app/workers/:
#   from app.integrations.cisa_kev import CISAClient
#   client = CISAClient()
#   await client.fetch_vulnerabilities()
