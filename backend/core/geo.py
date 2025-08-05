"""
Geographic utilities for IP-based location detection.
"""
import ipaddress
from typing import Optional, Dict, Any
from core.logger import get_logger

logger = get_logger(__name__)


async def get_country_from_ip(ip_address: str) -> Optional[str]:
    """
    Get country code from IP address.
    
    This is a stub implementation. In production, you would use:
    - MaxMind GeoIP2
    - IP2Location
    - ipapi.co
    - Or another geolocation service
    
    Args:
        ip_address: IP address to lookup
        
    Returns:
        Two-letter country code or None
    """
    try:
        # Check if it's a valid IP
        ip = ipaddress.ip_address(ip_address)
        
        # Local/private IPs
        if ip.is_private:
            return "XX"  # Unknown/Local
        
        # This is where you would call a real geo service
        # For now, return a default based on IP ranges (simplified)
        
        # Example: Simple mapping for demo purposes
        first_octet = int(str(ip).split('.')[0])
        
        # Very simplified mapping (not accurate!)
        if first_octet < 50:
            return "US"
        elif first_octet < 100:
            return "GB"
        elif first_octet < 150:
            return "DE"
        elif first_octet < 200:
            return "JP"
        else:
            return "AU"
            
    except Exception as e:
        logger.error(f"Failed to get country from IP {ip_address}: {e}")
        return None


async def get_location_details(ip_address: str) -> Dict[str, Any]:
    """
    Get detailed location information from IP.
    
    Returns:
        Dict with country, region, city, timezone, etc.
    """
    country = await get_country_from_ip(ip_address)
    
    return {
        "country_code": country,
        "country_name": get_country_name(country),
        "region": "Unknown",
        "city": "Unknown",
        "timezone": "UTC",
        "latitude": 0.0,
        "longitude": 0.0
    }


def get_country_name(country_code: Optional[str]) -> str:
    """Get country name from code."""
    country_names = {
        "US": "United States",
        "GB": "United Kingdom",
        "DE": "Germany",
        "FR": "France",
        "JP": "Japan",
        "CN": "China",
        "RU": "Russia",
        "AU": "Australia",
        "CA": "Canada",
        "BR": "Brazil",
        "IN": "India",
        "KR": "South Korea",
        "XX": "Unknown"
    }
    
    return country_names.get(country_code or "XX", "Unknown")