from connectors.apify_linkedin import ApifyLinkedInConnector
from connectors.apify_upwork import UpworkConnector

CONNECTOR_REGISTRY = {
    "linkedin": ApifyLinkedInConnector,
    "upwork":   UpworkConnector,    
}

def get_connector(platform_name: str):
    cls = CONNECTOR_REGISTRY.get(platform_name)
    if not cls:
        raise ValueError(f"No connector found for platform: {platform_name}")
    return cls()
