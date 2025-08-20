from typing import Optional

def extract_base_product(crack_product: str) -> Optional[str]:
    """Extract base product name from crack product name."""
    crack_lower = crack_product.lower().strip()

    # Remove "crack" from the end
    if crack_lower.endswith(" crack"):
        return crack_lower[:-6].strip()
    elif crack_lower.endswith("crack"):
        return crack_lower[:-5].strip()

    return None
