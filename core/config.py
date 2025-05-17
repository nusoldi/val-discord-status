import tomli
import os
from typing import List

CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.toml') # Assumes config.toml is in the parent directory of this file's directory

_config = None

def _load_config():
    """Loads the configuration from config.toml if not already loaded."""
    global _config
    if _config is None:
        try:
            with open(CONFIG_FILE_PATH, "rb") as f:
                _config = tomli.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found at {CONFIG_FILE_PATH}")
        except tomli.TOMLDecodeError:
            raise ValueError(f"Error decoding TOML from {CONFIG_FILE_PATH}")

def get_discord_webhook_url() -> str:
    """Returns the Discord webhook URL from the config."""
    _load_config()
    try:
        return _config["discord"]["webhook_url"]
    except KeyError:
        raise KeyError("Discord webhook URL not found in config.toml under [discord].webhook_url")

def get_validator_identity(cluster: str) -> str:
    """
    Returns the validator identity for the specified cluster.
    Args:
        cluster (str): The cluster identifier (e.g., "um" for mainnet, "ut" for testnet).
    Returns:
        str: The validator identity public key.
    """
    _load_config()
    key = f"identity_{cluster}"
    try:
        return _config["validator"][key]
    except KeyError:
        raise KeyError(f"Validator identity for cluster '{cluster}' not found in config.toml under [validator].{key}")

def get_rpc_urls(cluster: str) -> List[str]:
    """
    Returns the list of RPC URLs for the specified cluster.
    Args:
        cluster (str): The cluster identifier (e.g., "um" for mainnet, "ut" for testnet).
    Returns:
        List[str]: A list of RPC URLs.
    """
    _load_config()
    key = f"urls_{cluster}"
    try:
        return _config["rpc_urls"][key]
    except KeyError:
        raise KeyError(f"RPC URLs for cluster '{cluster}' not found in config.toml under [rpc_urls].{key}")

def get_log_level() -> str:
    """Returns the desired logging level from the config, defaulting to INFO."""
    _load_config()
    try:
        level = _config.get("logging", {}).get("log_level", "INFO").upper()
        # Validate the level string
        if level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            # Log a warning or raise an error, for now, default to INFO
            # This part might need a logger instance if we want to log from here, 
            # but config is loaded before logger might be fully set up by main.
            # print(f"Warning: Invalid log_level '{level}' in config.toml. Defaulting to INFO.")
            return "INFO"
        return level
    except Exception: # Catch any other unexpected error during config access
        # print(f"Warning: Could not read log_level from config.toml. Defaulting to INFO.")
        return "INFO"

def get_rpc_max_retries() -> int:
    """Returns the maximum number of RPC retry passes, defaulting to 1."""
    _load_config()
    try:
        retries = _config.get("rpc_settings", {}).get("rpc_max_retries", 1) # Default to 1 retry pass
        return int(retries)
    except ValueError:
        # print("Warning: Invalid rpc_max_retries in config.toml. Defaulting to 1.")
        return 1 # Default if conversion fails

def get_rpc_retry_delay() -> int:
    """Returns the RPC retry delay in seconds, defaulting to 5."""
    _load_config()
    try:
        delay = _config.get("rpc_settings", {}).get("rpc_retry_delay_seconds", 5) # Default to 5 seconds
        return int(delay)
    except ValueError:
        # print("Warning: Invalid rpc_retry_delay_seconds in config.toml. Defaulting to 5.")
        return 5 # Default if conversion fails

if __name__ == '__main__':
    # Example usage:
    print(f"Discord Webhook URL: {get_discord_webhook_url()}")
    print(f"Mainnet Validator Identity: {get_validator_identity('um')}")
    print(f"Testnet Validator Identity: {get_validator_identity('ut')}")
    print(f"Mainnet RPC URLs: {get_rpc_urls('um')}")
    print(f"Testnet RPC URLs: {get_rpc_urls('ut')}")
    print(f"Configured Log Level: {get_log_level()}")
    print(f"RPC Max Retries: {get_rpc_max_retries()}")
    print(f"RPC Retry Delay (seconds): {get_rpc_retry_delay()}") 