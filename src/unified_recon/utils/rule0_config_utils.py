"""Configuration and tolerance utilities for Rule 0."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional


def load_normalizer_config(config_path: str) -> Optional[dict[str, Any]]:
    """Load normalizer configuration from file.

    Args:
        config_path: Path to normalizer config file

    Returns:
        Normalizer configuration or None if not found
    """
    path = Path(config_path)
    if path.exists():
        with open(path, "r") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else None
    return None


def extract_tolerances_from_config(
    normalizer_config: dict[str, Any],
) -> dict[str, float]:
    """Extract tolerance values from normalizer config.

    Args:
        normalizer_config: Normalizer configuration dictionary

    Returns:
        Dictionary of tolerance values
    """
    tolerance_dict: dict[str, float] = {}
    tolerances = normalizer_config.get("universal_tolerances", {})

    if tolerances:
        # Add any tolerance values found in config
        for key, value in tolerances.items():
            if key.startswith("tolerance"):
                tolerance_dict[key] = value

    return tolerance_dict


def determine_default_tolerance(tolerances: dict[str, Any]) -> Decimal:
    """Determine default tolerance from tolerance dictionary.

    Args:
        tolerances: Dictionary of tolerance values

    Returns:
        Default tolerance as Decimal
    """
    if not tolerances:
        return Decimal("0.01")

    # Priority order for default tolerance
    if "tolerance_default" in tolerances:
        return Decimal(str(tolerances["tolerance_default"]))
    elif "tolerance" in tolerances:
        return Decimal(str(tolerances["tolerance"]))
    elif "tolerance_mt" in tolerances:
        # Use MT tolerance as fallback default
        return Decimal(str(tolerances["tolerance_mt"]))
    else:
        # Use first tolerance value found
        for key, value in tolerances.items():
            if key.startswith("tolerance") and not key.endswith("description"):
                return Decimal(str(value))

    return Decimal("0.01")


def get_exchange_groups_for_exchange(
    exchange_name: str, exchange_mappings: dict[str, str]
) -> list[int]:
    """Get exchange group IDs for an exchange.

    Args:
        exchange_name: Exchange identifier (ice_match, sgx_match, etc.)
        exchange_mappings: Mapping of group IDs to exchange names

    Returns:
        List of exchange group IDs
    """
    exchange_groups = []
    for group_id, mapped_exchange in exchange_mappings.items():
        if mapped_exchange == exchange_name:
            exchange_groups.append(int(group_id))
    return exchange_groups


def get_active_exchange_groups(
    trades: list[dict[str, Any]], valid_groups: list[int]
) -> set[int]:
    """Get active exchange groups from trades.

    Args:
        trades: List of trades
        valid_groups: List of valid group IDs for the exchange

    Returns:
        Set of active group IDs
    """
    active_groups = set()

    for trade in trades:
        group = trade.get("exchangeGroupId", trade.get("exchangegroupid", 0))
        group_id = int(group) if group else 0

        if group_id in valid_groups:
            active_groups.add(group_id)

    return active_groups


def build_exchange_cli_map(rule0_config: dict[str, Any]) -> dict[str, str]:
    """Build mapping from CLI names to exchange names.

    Args:
        rule0_config: Rule 0 configuration dictionary

    Returns:
        Dictionary mapping CLI names to exchange names
    """
    exchange_map = {}
    for exchange_key in rule0_config.keys():
        cli_name = exchange_key.replace("_match", "")
        exchange_map[cli_name] = exchange_key
    return exchange_map


def get_available_exchanges(rule0_config: dict[str, Any]) -> list[str]:
    """Get list of available exchanges for CLI choices.

    Args:
        rule0_config: Rule 0 configuration dictionary

    Returns:
        List of CLI-friendly exchange names
    """
    return [key.replace("_match", "") for key in rule0_config.keys()]
