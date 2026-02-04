# Integration Placeholders

This directory contains placeholders for external API integrations.

## Planned Integrations

- **CISA KEV** - CISA Known Exploited Vulnerabilities
- **NVD** - National Vulnerability Database  
- **Shodan** - Shodan API
- **Others** - Add more as needed

## Integration Template

Each integration should follow this structure:

```
app/integrations/my_integration/
├── __init__.py
├── client.py          # API client with async methods
├── parser.py          # Parse/normalize responses
└── models.py          # Integration-specific data models
```

### Example: CISA KEV Integration

```python
# app/integrations/cisa_kev/client.py
class CISAClient:
    async def fetch_vulnerabilities(self) -> list[dict]:
        """Fetch latest known exploited vulnerabilities."""
        pass

# app/integrations/cisa_kev/parser.py
class CISAParser:
    @staticmethod
    def parse_vulnerabilities(raw_data: dict) -> list[Vulnerability]:
        """Normalize CISA response."""
        pass
```

### Integration with Workers

Background workers in `app/workers/` will use these integrations:

```python
# app/workers/ingest_jobs.py
from app.integrations.cisa_kev import CISAClient

async def ingest_cisa_kev():
    client = CISAClient()
    data = await client.fetch_vulnerabilities()
    # Save to database via IngestRun model
```

## Adding a New Integration

1. Create a new folder: `app/integrations/my_source/`
2. Implement `client.py`, `parser.py`, optional `models.py`
3. Update `app/workers/ingest_jobs.py` to call the new integration
4. Add environment variables for credentials in `.env`
5. Add tests in `tests/integrations/`
