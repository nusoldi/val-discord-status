#!/usr/bin/env python3
import argparse
import sys
import os
import logging

# Project root is /home/sol/val_discord_status/ (or similar)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# For `from core.fetch_data...` to work,
# PROJECT_ROOT itself needs to be in sys.path because 'core' is a directory (package) under it.
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import get_log_level from core.config after potentially adding PROJECT_ROOT to sys.path
from core.config import get_log_level 

# --- Logging Setup ---
# When run via systemd, logs will go to journald by default if stdout/stderr are journal.
# This basic config is for console output if run directly and for modules to pick up.
# Determine log level from config file
LOG_LEVEL_STR = get_log_level() # Get from config
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO) # Convert string to logging level object, default to INFO

logging.basicConfig(
    level=LOG_LEVEL, # Use level from config
    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout) # Ensure logs go to stdout for systemd to capture if needed
    ]
)
logger = logging.getLogger(__name__)
# --- End Logging Setup ---

try:
    # Now Python can find the 'core' package within PROJECT_ROOT
    from core.fetch_data import report_validator_status
    # We need to import get_log_level earlier to set up logging, so no need to re-import here.
    # from core.config import get_log_level # Already imported above
except ImportError as e:
    # If core.config itself fails to import, get_log_level won't be available.
    # In such critical import failures, logger might not be fully set up with config level.
    # The initial logger.critical calls will use default logging level until basicConfig is effective.
    print(f"CRITICAL: Error importing 'report_validator_status' or 'get_log_level': {e}") # Fallback print for very early error
    print(f"CRITICAL: PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"CRITICAL: Current sys.path: {sys.path}")
    sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Validator Discord Status.") # Updated description
    parser.add_argument(
        "--cluster",
        required=True,
        choices=['um', 'ut'],
        help="Specify which cluster to report ('um' for mainnet, 'ut' for testnet)."
    )
    args = parser.parse_args()
    
    logger.info(f"Validator Discord Status script initiated for cluster: {args.cluster.upper()}") # Changed to logger
    try:
        report_validator_status(args.cluster)
    except Exception as e:
        logger.error(f"An error occurred while running Validator Discord Status for cluster {args.cluster.upper()}: {e}", exc_info=True) # Changed to logger, added exc_info
        # import traceback # No longer needed
        # traceback.print_exc()
        sys.exit(1)
    logger.info(f"Validator Discord Status script finished for cluster: {args.cluster.upper()}") # Changed to logger 