import requests
import subprocess
import json
import time
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

# Assuming config.py and discord.py are in the same package/directory or accessible via PYTHONPATH
from .config import get_rpc_urls, get_validator_identity, get_rpc_max_retries, get_rpc_retry_delay
#from .discord import format_and_send_status
from .discord import format_and_send_status

logger = logging.getLogger(__name__)

LAMPORTS_PER_SOL = 1_000_000_000

# --- RPC and CLI Call Functions ---

def _make_rpc_request(
    cluster_rpc_urls: List[str],
    method: str,
    params: Optional[List[Any]] = None,
    max_retries_override: Optional[int] = None,
    retry_delay_override: Optional[int] = None
) -> Dict[str, Any]:
    """
    Helper function to make a JSON-RPC request, iterating through URLs and retrying on failure.

    Args:
        cluster_rpc_urls: A list of RPC URLs for the target cluster.
        method: The RPC method name.
        params: Optional list of parameters for the RPC method.
        max_retries_override: Optional override for max_retries from config.
        retry_delay_override: Optional override for retry_delay from config.

    Returns:
        The 'result' field from the JSON-RPC response.

    Raises:
        RuntimeError: If the request fails for all URLs after all retry attempts.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or []
    }
    headers = {"Content-Type": "application/json"}

    max_attempts = (max_retries_override if max_retries_override is not None else get_rpc_max_retries()) + 1
    delay_seconds = retry_delay_override if retry_delay_override is not None else get_rpc_retry_delay()

    last_exception_per_url = {}

    for attempt in range(max_attempts):
        logger.debug(f"RPC call attempt {attempt + 1}/{max_attempts} for method '{method}'.")
        for rpc_url in cluster_rpc_urls:
            logger.debug(f"Attempting RPC method '{method}' on URL: {rpc_url}")
            try:
                response = requests.post(rpc_url, json=payload, headers=headers, timeout=20)
                response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
                result_json = response.json()
                if "error" in result_json:
                    err_msg = f"RPC error for method {method} on {rpc_url}: {result_json['error']}"
                    logger.warning(err_msg)
                    last_exception_per_url[rpc_url] = RuntimeError(err_msg)
                else:
                    logger.debug(f"Successfully fetched data for method '{method}' from {rpc_url}.")
                    return result_json.get("result")
            except requests.exceptions.Timeout as e:
                warn_msg = f"RPC request timeout for method {method} on {rpc_url}."
                logger.warning(warn_msg)
                last_exception_per_url[rpc_url] = e
            except requests.exceptions.HTTPError as e:
                warn_msg = f"HTTP error for method {method} on {rpc_url}: {e.response.status_code} {e.response.reason}."
                logger.warning(warn_msg)
                last_exception_per_url[rpc_url] = e
            except requests.exceptions.RequestException as e:
                warn_msg = f"RPC request failed for method {method} on {rpc_url}: {e}"
                logger.warning(warn_msg)
                last_exception_per_url[rpc_url] = e
            except json.JSONDecodeError as e:
                warn_msg = f"Failed to decode JSON response for method {method} on {rpc_url}: {e}"
                logger.warning(warn_msg)
                last_exception_per_url[rpc_url] = e

        if attempt < max_attempts - 1:
            logger.warning(
                f"All RPC URLs failed for method '{method}' on attempt {attempt + 1}. "
                f"Waiting {delay_seconds}s before next attempt."
            )
            time.sleep(delay_seconds)
        else: # Last attempt failed
            logger.error(
                f"All RPC URLs failed for method '{method}' after {max_attempts} attempts."
            )

    error_summary = [f"URL {url}: {err}" for url, err in last_exception_per_url.items()]
    final_error_message = (
        f"RPC method '{method}' failed for all URLs after {max_attempts} attempts. "
        f"Last errors: {'; '.join(error_summary)}"
    )
    raise RuntimeError(final_error_message)


def _execute_solana_cli_command(command_args: List[str], cluster_rpc_urls: List[str]) -> str:
    """
    Executes a Solana CLI command using the first available RPC URL for the given cluster.
    Retries with the next RPC URL if the command fails with that specific URL.
    """
    base_command = ["solana"]

    for rpc_url in cluster_rpc_urls:
        full_command = base_command + ["--url", rpc_url] + command_args
        try:
            process = subprocess.run(
                full_command,
                capture_output=True,
                text=True,
                check=True,
                timeout=60  # Timeout for the CLI command execution
            )
            return process.stdout
        except subprocess.CalledProcessError as e:
            logger.warning(f"CLI command '{' '.join(full_command)}' failed with error: {e.stderr}. Trying next RPC URL if available.")
        except subprocess.TimeoutExpired:
            logger.warning(f"CLI command '{' '.join(full_command)}' timed out. Trying next RPC URL if available.")
        except Exception as e:
            logger.warning(f"An unexpected error occurred with CLI command '{' '.join(full_command)}': {e}. Trying next RPC URL if available.")

    raise RuntimeError(f"Solana CLI command '{' '.join(command_args)}' failed for all provided RPC URLs.")


def get_vote_accounts_rpc(cluster_rpc_urls: List[str]) -> Dict[str, Any]:
    """Fetches vote accounts using JSON-RPC, utilizing the retry mechanism in _make_rpc_request."""
    return _make_rpc_request(cluster_rpc_urls, "getVoteAccounts")

def get_epoch_info_rpc(cluster_rpc_urls: List[str]) -> Dict[str, Any]:
    """Fetches epoch information using JSON-RPC, utilizing the retry mechanism in _make_rpc_request."""
    return _make_rpc_request(cluster_rpc_urls, "getEpochInfo")

def get_cluster_nodes_rpc(cluster_rpc_urls: List[str]) -> List[Dict[str, Any]]:
    """Fetches cluster node information using JSON-RPC, utilizing the retry mechanism in _make_rpc_request."""
    result = _make_rpc_request(cluster_rpc_urls, "getClusterNodes")
    if not isinstance(result, list):
        logger.error(f"getClusterNodes RPC call returned non-list type: {type(result)}. Value: {result}")
        raise RuntimeError(f"getClusterNodes RPC call returned unexpected type: {type(result)}")
    return result


def get_leader_schedule_rpc(cluster_rpc_urls: List[str]) -> Dict[str, Any]:
    """Fetches the leader schedule for the current epoch (all validators) using JSON-RPC."""
    result = _make_rpc_request(cluster_rpc_urls, "getLeaderSchedule", []) # No params needed for current epoch, all leaders
    if not isinstance(result, dict):
        logger.error(f"getLeaderSchedule RPC call returned non-dict type: {type(result)}. Value: {result}")
        raise RuntimeError(f"getLeaderSchedule RPC call returned unexpected type: {type(result)}")
    return result

def get_block_production_rpc(
    cluster_rpc_urls: List[str],
    identity_pubkey: str,
    first_slot: int,
    last_slot: int
) -> Dict[str, Any]:
    """Fetches block production data for a specific validator and slot range using JSON-RPC."""
    params = [{
        "identity": identity_pubkey,
        "range": {
            "firstSlot": first_slot,
            "lastSlot": last_slot
        }
    }]
    result = _make_rpc_request(cluster_rpc_urls, "getBlockProduction", params)
    if not isinstance(result, dict):
        logger.error(f"getBlockProduction RPC call returned non-dict type: {type(result)}. Value: {result}")
        raise RuntimeError(f"getBlockProduction RPC call returned unexpected type: {type(result)}")
    return result


def get_recent_performance_samples_rpc(cluster_rpc_urls: List[str], limit: int = 720) -> List[Dict[str, Any]]:
    """Fetches recent performance samples using JSON-RPC."""
    params = [limit]
    result = _make_rpc_request(cluster_rpc_urls, "getRecentPerformanceSamples", params)
    if not isinstance(result, list):
        logger.error(f"getRecentPerformanceSamples RPC call returned non-list type: {type(result)}. Value: {result}. Defaulting to empty list.")
        return [] # Default to empty list to prevent downstream errors on unexpected type
    return result

def get_balance_rpc(cluster_rpc_urls: List[str], pubkey: str) -> Optional[int]:
    """
    Fetches the balance for a given public key using JSON-RPC.
    Returns balance in lamports, or None if an error occurs after all retries.
    """
    if not pubkey:
        logger.warning("get_balance_rpc called with an empty pubkey.")
        return None

    params = [pubkey]
    try:
        result = _make_rpc_request(cluster_rpc_urls, "getBalance", params)
        # Expected result structure: {"context": {"slot": N}, "value": V}
        if result is not None and isinstance(result.get("value"), int):
            return result["value"]  # Balance is in lamports
        else:
            logger.warning(f"getBalance for {pubkey} returned unexpected result structure: {result}")
            return None
    except RuntimeError as e:
        logger.error(f"Failed to get balance for {pubkey} after all retries: {e}")
        return None

# --- CLI Wrappers ---
def get_validator_info_cli(cluster_rpc_urls: List[str]) -> List[Dict[str, Any]]:
    """Fetches validator information using Solana CLI's 'validator-info get' command."""
    output = _execute_solana_cli_command(
        ["validator-info", "get", "--output", "json"],
        cluster_rpc_urls
    )
    try:
        return json.loads(output)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON from validator-info CLI output: {e}\nOutput: {output}")

def _get_validator_stake_info_cli(cluster_rpc_urls: List[str], validator_pubkey: str) -> list:
    """
    Fetches stake account data for a given validator pubkey using the Solana CLI 'stakes' command.
    Returns a list of stake accounts or an empty list on error.
    """
    command_args = [
        "stakes",
        validator_pubkey,
        "--output",
        "json"
    ]
    try:
        output = _execute_solana_cli_command(command_args, cluster_rpc_urls)
        return json.loads(output)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON output from Solana CLI for stakes: {e}. Output: {output}")
        return []
    except RuntimeError as e:
        logger.error(f"Error executing Solana CLI command for stakes for {validator_pubkey}: {e}")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching stake data for {validator_pubkey}: {e}")
        return []

# --- Data Processing and Calculation Functions ---

def _calculate_stake_metrics_from_data(stake_data: list) -> dict:
    """
    Calculates various stake metrics from the raw stake data obtained from 'solana stakes'.
    All monetary values are returned in SOL.
    """
    total_active_stake_lamports = 0
    total_delegated_stake_lamports = 0
    total_activating_stake_lamports = 0
    total_deactivating_stake_lamports = 0

    if not stake_data:
        return {
            "total_active_stake_sol": 0.0,
            "total_delegated_stake_sol": 0.0,
            "stake_activating_sol": 0.0,
            "stake_deactivating_sol": 0.0,
            "net_stake_change_sol": 0.0,
        }

    for account in stake_data:
        active_stake = account.get("activeStake", 0)
        delegated_stake = account.get("delegatedStake", 0)
        deactivating_stake = account.get("deactivatingStake", 0)

        total_active_stake_lamports += active_stake
        total_delegated_stake_lamports += delegated_stake
        total_deactivating_stake_lamports += deactivating_stake

        # Activating stake is the portion of delegated stake that is not yet active.
        activating_for_this_account = delegated_stake - active_stake
        if activating_for_this_account > 0:
            total_activating_stake_lamports += activating_for_this_account

    net_stake_change_lamports = total_activating_stake_lamports - total_deactivating_stake_lamports

    return {
        "total_active_stake_sol": total_active_stake_lamports / LAMPORTS_PER_SOL,
        "total_delegated_stake_sol": total_delegated_stake_lamports / LAMPORTS_PER_SOL,
        "stake_activating_sol": total_activating_stake_lamports / LAMPORTS_PER_SOL,
        "stake_deactivating_sol": total_deactivating_stake_lamports / LAMPORTS_PER_SOL,
        "net_stake_change_sol": net_stake_change_lamports / LAMPORTS_PER_SOL,
    }

def _calculate_epoch_progress(epoch_info: Dict[str, Any], cluster_rpc_urls: List[str]) -> Tuple[float, str]:
    """
    Calculates epoch percentage complete and estimated time left in the current epoch.
    Uses getRecentPerformanceSamples for a more accurate average slot time.
    """
    slot_index = epoch_info.get("slotIndex")
    slots_in_epoch = epoch_info.get("slotsInEpoch")

    if slot_index is None or slots_in_epoch is None or slots_in_epoch == 0:
        logger.warning("slotIndex or slotsInEpoch missing/invalid in epoch_info. Cannot calculate progress accurately.")
        return 0.0, "Unknown"

    percent_complete = (slot_index / slots_in_epoch) * 100

    avg_slot_time_seconds = 0.4  # Default: Solana's target slot time (fallback)
    performance_samples = get_recent_performance_samples_rpc(cluster_rpc_urls, limit=720)

    if performance_samples:
        valid_samples = [s for s in performance_samples if s.get("numSlots", 0) > 0 and s.get("samplePeriodSecs") is not None]
        if valid_samples:
            total_slots = sum(sample["numSlots"] for sample in valid_samples)
            total_time_secs = sum(sample["samplePeriodSecs"] for sample in valid_samples)
            if total_slots > 0:
                avg_slot_time_seconds = total_time_secs / total_slots
                logger.debug(f"Calculated average slot time: {avg_slot_time_seconds:.4f}s from {len(valid_samples)} samples.")
            else:
                logger.warning("No slots found in valid performance samples; using default slot time.")
        else:
            logger.warning("No valid performance samples found; using default slot time.")
    else:
        logger.warning("Failed to fetch performance samples; using default slot time.")

    remaining_slots = slots_in_epoch - slot_index
    time_remaining_seconds = remaining_slots * avg_slot_time_seconds

    # Format time_remaining_seconds into a human-readable string
    days, remainder = divmod(time_remaining_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{int(days)} day{'s' if int(days) != 1 else ''}")
    if hours > 0:
        parts.append(f"{int(hours)} hour{'s' if int(hours) != 1 else ''}")
    if minutes > 0:
        parts.append(f"{int(minutes)} min{'s' if int(minutes) != 1 else ''}")
    if not parts and seconds > 0: # Show seconds only if no larger units are present
         parts.append(f"{int(seconds)} sec{'s' if int(seconds) != 1 else ''}")

    if not parts: # If remaining time is very short or zero
        time_left_str = "Nearly complete" if percent_complete > 99.9 else "Calculating..."
    else:
        time_left_str = ", ".join(parts)

    return percent_complete, time_left_str


def process_validator_data(cluster_shorthand: str) -> Optional[Dict[str, Any]]:
    """
    Fetches, processes, and prepares all validator data for a given cluster.

    This is the main data aggregation function. It calls various RPC and CLI helper
    functions, processes the data, and compiles it into a dictionary.

    Args:
        cluster_shorthand (str): 'um' for mainnet, 'ut' for testnet.

    Returns:
        A dictionary with formatted data ready for Discord, or None on critical failure.
    """
    logger.info(f"Starting data processing for cluster: {cluster_shorthand}...")

    try:
        rpc_urls = get_rpc_urls(cluster_shorthand)
        validator_identity_pubkey = get_validator_identity(cluster_shorthand)
    except KeyError as e:
        logger.error(f"Configuration missing for cluster {cluster_shorthand}: {e}")
        return None

    if not rpc_urls:
        logger.error(f"Error: No RPC URLs configured for cluster {cluster_shorthand}.")
        return None

    logger.info(f"Using RPC URLs: {rpc_urls} for cluster {cluster_shorthand}")
    logger.info(f"Target Validator ID: {validator_identity_pubkey}")

    try:
        # 1. Fetch core data concurrently (or sequentially if easier to manage)
        logger.info("Fetching vote accounts...")
        vote_accounts_data = get_vote_accounts_rpc(rpc_urls)
        # Example `getVoteAccounts` structure:
        # { "current": [{"identityPubkey": "...", "epochCredits": [[epoch, credits, prev_credits], ...], ...}],
        #   "delinquent": [...] }

        logger.info("Fetching validator info (CLI)...")
        validator_infos_list = get_validator_info_cli(rpc_urls)
        # Example `validator-info get` (list of dicts):
        # [{ "identityPubkey": "...", "info": {"name": "ValidatorName"}, ...}]

        logger.info("Fetching epoch info...")
        epoch_info_data = get_epoch_info_rpc(rpc_urls)
        # Example `getEpochInfo` structure:
        # { "epoch": N, "slotIndex": X, "slotsInEpoch": Y, "absoluteSlot": Z, ... }

        logger.info(f"Fetching stake data for validator: {validator_identity_pubkey}...")
        stake_raw_data = _get_validator_stake_info_cli(rpc_urls, validator_identity_pubkey)
        stake_metrics = _calculate_stake_metrics_from_data(stake_raw_data)

        # Unpack stake_metrics into local variables for consistent return statement
        total_active_stake_sol_val = stake_metrics["total_active_stake_sol"]
        total_delegated_stake_sol_val = stake_metrics["total_delegated_stake_sol"]
        stake_activating_sol_val = stake_metrics["stake_activating_sol"]
        stake_deactivating_sol_val = stake_metrics["stake_deactivating_sol"]
        net_stake_change_sol_val = stake_metrics["net_stake_change_sol"]

        logger.info("Fetching cluster nodes info...")
        cluster_nodes_data = get_cluster_nodes_rpc(rpc_urls)
        # Example `getClusterNodes` result is a list of objects:
        # [ { "pubkey": "...", "gossip": "IP:PORT", "tpu": "IP:PORT", "rpc": "IP:PORT",
        #     "version": "1.x.y ...", ... }, ... ]

        # 2. Process validator list from vote_accounts_data
        all_validators = vote_accounts_data.get("current", []) + vote_accounts_data.get("delinquent", [])

        if not all_validators:
            logger.error("No validators found in vote_accounts_data.")
            # Depending on requirements, this might be a critical failure or recoverable
            # For now, we'll let it proceed, and our_validator_data might not be found.
            # return None # Consider if this is fatal

        current_epoch_from_rpc = epoch_info_data.get("epoch")
        processed_validators = []
        for val in all_validators:
            current_credits_cumulative = 0
            previous_credits_cumulative = 0
            credits_in_current_epoch = 0

            # epochCredits is a list of [epoch, credits_cumulative_at_epoch_end, prev_credits_cumulative_at_epoch_end]
            for ep_credits_tuple in val.get("epochCredits", []):
                if len(ep_credits_tuple) == 3 and ep_credits_tuple[0] == current_epoch_from_rpc:
                    current_credits_cumulative = ep_credits_tuple[1]
                    previous_credits_cumulative = ep_credits_tuple[2]
                    # Credits earned in this specific epoch entry
                    credits_in_current_epoch = current_credits_cumulative - previous_credits_cumulative
                    break
            val["currentEpochCreditsCumulative"] = current_credits_cumulative
            val["currentEpochCreditsEarned"] = credits_in_current_epoch
            processed_validators.append(val)

        # Filter out validators with zero or negative current epoch credits earned for ranking purposes
        ranked_validators = sorted(
            [v for v in processed_validators if v.get("currentEpochCreditsEarned", 0) > 0],
            key=lambda x: x.get("currentEpochCreditsEarned", 0),
            reverse=True
        )

        if not ranked_validators:
            logger.warning("No validators with positive epoch credits earned found for ranking.")

        # Assign rank
        for i, val in enumerate(ranked_validators):
            val["rank"] = i + 1

        our_validator_data = None
        # Try to find in ranked list first
        if ranked_validators:
            for val_ranked in ranked_validators:
                if val_ranked.get("nodePubkey") == validator_identity_pubkey:
                    our_validator_data = val_ranked
                    break

        if not our_validator_data: # If not in ranked, search in all processed validators
            logger.warning(f"Validator {validator_identity_pubkey} not found in the ranked list (or list was empty). Searching unranked list.")
            found_in_all_validators = False
            for val_orig in processed_validators: # Use processed_validators which has 'currentEpochCreditsEarned'
                if val_orig.get("nodePubkey") == validator_identity_pubkey:
                    logger.info(f"Validator {validator_identity_pubkey} found in the unranked list (likely 0 or negative earned credits).")
                    logger.info(f"Data for {validator_identity_pubkey}: epochCredits={val_orig.get('epochCredits')}, currentEpochCreditsEarned={val_orig.get('currentEpochCreditsEarned', 'N/A')}")
                    our_validator_data = val_orig
                    our_validator_data['rank'] = 'N/A' # Explicitly set rank to N/A
                    found_in_all_validators = True
                    break
            if not found_in_all_validators:
                logger.error(f"Validator {validator_identity_pubkey} not found in any validator list from getVoteAccounts.")
                # This is a critical point. If our validator isn't found, many metrics will be missing.
                # Consider returning None or having default "N/A" values for all validator-specific fields.
                # For now, we'll attempt to provide "N/A" for fields that depend on our_validator_data.
                # Create a placeholder to avoid KeyErrors later, but log this problem.
                our_validator_data = {"nodePubkey": validator_identity_pubkey, "votePubkey": "N/A", "activatedStake": 0, "currentEpochCreditsEarned": 0, "rank": "N/A"}


        # 3. Extract details for our validator
        rank = our_validator_data.get("rank", "N/A")
        identity = our_validator_data.get("nodePubkey", validator_identity_pubkey) # Fallback to config identity
        vote_account = our_validator_data.get("votePubkey", "N/A")
        epoch_credits_earned = our_validator_data.get("currentEpochCreditsEarned", 0 if rank != "N/A" else "N/A")

        # Extract validator version and IP from cluster_nodes_data
        validator_client_version = "N/A"
        validator_ip_address = "N/A"
        if cluster_nodes_data: # Ensure cluster_nodes_data is not None (e.g. if RPC failed)
            for node_info in cluster_nodes_data:
                if node_info.get("pubkey") == identity: # Use the identity we confirmed for our validator
                    validator_client_version = node_info.get("version", "N/A")
                    gossip_address = node_info.get("gossip")
                    if gossip_address:
                        validator_ip_address = gossip_address.split(":")[0] # Remove port
                    else:
                        validator_ip_address = "N/A" # Explicit N/A if gossip is None
                    logger.info(f"Found node info for {identity}: Version='{validator_client_version}', Gossip='{gossip_address}', IP='{validator_ip_address}'")
                    break
            else:
                logger.warning(f"Could not find node info for {identity} in getClusterNodes output.")
        else:
            logger.warning("cluster_nodes_data was empty or None; version/IP will be N/A.")


        # Fetch balances
        identity_balance_lamports = get_balance_rpc(rpc_urls, identity) if identity != "N/A" else None
        vote_account_balance_lamports = get_balance_rpc(rpc_urls, vote_account) if vote_account != "N/A" else None

        identity_balance_sol = identity_balance_lamports / LAMPORTS_PER_SOL if identity_balance_lamports is not None else "N/A"
        vote_account_balance_sol = vote_account_balance_lamports / LAMPORTS_PER_SOL if vote_account_balance_lamports is not None else "N/A"

        logger.info(f"Validator Identity Account ({identity}) Balance: {identity_balance_sol} SOL")
        logger.info(f"Validator Vote Account ({vote_account}) Balance: {vote_account_balance_sol} SOL")

        active_stake_lamports = our_validator_data.get("activatedStake", 0)
        active_stake_sol = active_stake_lamports / LAMPORTS_PER_SOL

        # Get validator name from validator_infos_list (CLI data)
        validator_name = "Unknown"
        if validator_infos_list: # Ensure CLI data was fetched
            for vi_entry in validator_infos_list:
                if vi_entry.get("identityPubkey") == identity:
                    validator_name = vi_entry.get("info", {}).get("name", "Unknown")
                    if validator_name == "null" or not validator_name: # Handle literal "null" or empty name
                        validator_name = identity[:12] + "..." # Fallback to shortened pubkey if name is invalid/missing
                    break
            else: # Validator not found in CLI info list
                 validator_name = identity[:12] + "..." # Fallback name
        else: # CLI data fetch failed
            validator_name = identity[:12] + "..." # Fallback name


        # 4. Calculate missed credits relative to rank 1 (if rank 1 exists and has credits)
        credits_earned_rank_1 = 0
        if ranked_validators and ranked_validators[0].get("currentEpochCreditsEarned", 0) > 0:
            credits_earned_rank_1 = ranked_validators[0].get("currentEpochCreditsEarned", 0)

        missed_credits = "N/A"
        if isinstance(epoch_credits_earned, (int, float)) and isinstance(credits_earned_rank_1, (int, float)) and credits_earned_rank_1 > 0:
            missed_credits = credits_earned_rank_1 - epoch_credits_earned
        elif credits_earned_rank_1 == 0 and isinstance(epoch_credits_earned, (int, float)) and epoch_credits_earned >= 0 : # If rank 1 has 0, we missed 0
            missed_credits = 0
        elif rank == "N/A": # If our validator is unranked
             missed_credits = "N/A"


        # 5. Epoch details
        current_epoch = epoch_info_data.get("epoch", "N/A") # Fallback if epoch_info_data is problematic
        epoch_percent_complete, time_left_in_epoch = _calculate_epoch_progress(epoch_info_data, rpc_urls)


        # 6. Leader Slot Metrics
        leader_slots_total = 0
        leader_slots_completed_count = 0
        leader_slots_upcoming_count = 0
        leader_slots_skipped = 0
        leader_skip_rate = 0.0

        if identity != "N/A": # Only proceed if we have a valid validator identity
            logger.info(f"Fetching leader schedule for epoch {current_epoch}...")
            try:
                leader_schedule_data = get_leader_schedule_rpc(rpc_urls)
                # Example: { "<pubkey>": [slot_idx1, slot_idx2,...], ... }

                validator_slots_in_epoch = leader_schedule_data.get(identity, [])
                leader_slots_total = len(validator_slots_in_epoch)

                if leader_slots_total > 0:
                    current_slot_in_epoch = epoch_info_data.get("slotIndex", 0) # Default to 0 if not found

                    completed_slots_this_epoch = [s for s in validator_slots_in_epoch if s <= current_slot_in_epoch]
                    leader_slots_completed_count = len(completed_slots_this_epoch)
                    leader_slots_upcoming_count = leader_slots_total - leader_slots_completed_count

                    # For blockProduction, Solana RPC expects absolute slot numbers.
                    # epoch_info_data["absoluteSlot"] is the current absolute slot.
                    # epoch_info_data["slotIndex"] is slots processed in current epoch.
                    # So, first slot of current epoch = absoluteSlot - slotIndex
                    epoch_start_absolute_slot = epoch_info_data.get("absoluteSlot", 0) - current_slot_in_epoch
                    current_absolute_slot = epoch_info_data.get("absoluteSlot", 0)

                    # Only fetch block production if there are completed slots and a valid slot range
                    if leader_slots_completed_count > 0 and epoch_start_absolute_slot < current_absolute_slot:
                        logger.info(f"Fetching block production for {identity} in epoch {current_epoch} (slots {epoch_start_absolute_slot} to {current_absolute_slot})...")
                        try:
                            block_production_info = get_block_production_rpc(
                                rpc_urls,
                                identity,
                                epoch_start_absolute_slot,
                                current_absolute_slot
                            )
                            # Expected structure: {"value": {"byIdentity": {<identity>: [assigned_slots, produced_blocks]}}}
                            validator_bp_stats = block_production_info.get("value", {}).get("byIdentity", {}).get(identity)
                            if validator_bp_stats and len(validator_bp_stats) == 2:
                                assigned_slots_in_bp_range = validator_bp_stats[0]
                                blocks_produced_in_bp_range = validator_bp_stats[1]

                                # For skip rate, the denominator should be the number of *expected* leader slots
                                # that have passed within the block production query range.
                                # This 'assigned_slots_in_bp_range' from getBlockProduction is the most direct measure.
                                if assigned_slots_in_bp_range > 0:
                                    leader_slots_skipped = assigned_slots_in_bp_range - blocks_produced_in_bp_range
                                    leader_skip_rate = (leader_slots_skipped / assigned_slots_in_bp_range) * 100.0 if assigned_slots_in_bp_range > 0 else 0.0
                                else: # No slots assigned in the block production range as per getBlockProduction
                                    leader_slots_skipped = 0
                                    leader_skip_rate = 0.0
                                logger.info(f"Block production for {identity}: AssignedInBP={assigned_slots_in_bp_range}, ProducedInBP={blocks_produced_in_bp_range}, CalculatedSkipped={leader_slots_skipped}")
                            else:
                                logger.warning(f"Block production data for {identity} was missing or not in expected format: {validator_bp_stats}. Skipped/rate will be 0.")
                        except RuntimeError as e:
                            logger.error(f"Could not fetch block production for {identity}: {e}. Skipped/rate will be 0.")
                    else:
                         logger.info(f"Skipping block production check for {identity} as no completed leader slots yet, or invalid slot range.")
                else:
                    logger.info(f"Validator {identity} has no leader slots in the current epoch {current_epoch}.")
            except RuntimeError as e:
                 logger.error(f"Could not fetch leader schedule: {e}. Leader slot metrics will be 0.")
        else: # identity was N/A
            logger.warning("Skipping leader slot metrics calculation as validator identity is N/A.")


        logger.info(f"Successfully processed data for {validator_name} ({identity}) on cluster {cluster_shorthand}.")

        return {
            "cluster_shorthand": cluster_shorthand,
            "validator_name": validator_name,
            "active_stake_sol": active_stake_sol, # From vote account
            "current_epoch": current_epoch,
            "epoch_percent_complete": epoch_percent_complete,
            "time_left_in_epoch": time_left_in_epoch,
            "rank": rank,
            "epoch_credits": epoch_credits_earned,
            "missed_credits": missed_credits,
            "identity_pubkey": identity,
            "vote_account_pubkey": vote_account,
            "identity_balance_sol": identity_balance_sol,
            "vote_account_balance_sol": vote_account_balance_sol,
            "validator_version": validator_client_version,
            "validator_ip": validator_ip_address,
            "total_active_stake_sol": total_active_stake_sol_val,
            "total_delegated_stake_sol": total_delegated_stake_sol_val,
            "stake_activating_sol": stake_activating_sol_val,
            "stake_deactivating_sol": stake_deactivating_sol_val,
            "net_stake_change_sol": net_stake_change_sol_val,
            "leader_slots_total": leader_slots_total,
            "leader_slots_completed": leader_slots_completed_count,
            "leader_slots_upcoming": leader_slots_upcoming_count,
            "leader_slots_skipped": leader_slots_skipped,
            "leader_skip_rate": leader_skip_rate,
        }

    except RuntimeError as e: # Catch RuntimeErrors from RPC/CLI calls if they exhausted retries
        logger.error(f"Critical Runtime Error during data processing for cluster {cluster_shorthand}: {e}")
        return None # Indicates a failure to fetch critical data
    except Exception as e:
        logger.error(f"Unexpected error during data processing for cluster {cluster_shorthand}: {e}", exc_info=True)
        return None

# --- Main Execution ---

def report_validator_status(cluster_shorthand: str):
    """
    Main function to fetch validator status for a cluster and send it to Discord.

    Args:
        cluster_shorthand (str): 'um' for mainnet or 'ut' for testnet.
    """
    # Fallback logging config if no handlers are set (e.g. if module is used unexpectedly)
    # main.py should already configure logging based on config.toml.
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    logger.info(f"Reporting validator status for cluster: {cluster_shorthand.upper()}")

    data_to_report = process_validator_data(cluster_shorthand)

    if data_to_report:
        success = format_and_send_status(
            cluster_name=data_to_report["cluster_shorthand"],
            validator_name=data_to_report["validator_name"],
            active_stake_sol=data_to_report["active_stake_sol"],
            current_epoch=data_to_report["current_epoch"],
            epoch_percent_complete=data_to_report["epoch_percent_complete"],
            time_left_in_epoch=data_to_report["time_left_in_epoch"],
            rank=data_to_report["rank"],
            epoch_credits=data_to_report["epoch_credits"],
            missed_credits=data_to_report["missed_credits"],
            identity_pubkey=data_to_report["identity_pubkey"],
            vote_account_pubkey=data_to_report["vote_account_pubkey"],
            identity_balance_sol=data_to_report["identity_balance_sol"],
            vote_account_balance_sol=data_to_report["vote_account_balance_sol"],
            total_active_stake_sol=data_to_report["total_active_stake_sol"],
            total_delegated_stake_sol=data_to_report["total_delegated_stake_sol"],
            stake_activating_sol=data_to_report["stake_activating_sol"],
            stake_deactivating_sol=data_to_report["stake_deactivating_sol"],
            net_stake_change_sol=data_to_report["net_stake_change_sol"],
            validator_version=data_to_report["validator_version"],
            validator_ip=data_to_report["validator_ip"],
            leader_slots_total=data_to_report["leader_slots_total"],
            leader_slots_completed=data_to_report["leader_slots_completed"],
            leader_slots_upcoming=data_to_report["leader_slots_upcoming"],
            leader_slots_skipped=data_to_report["leader_slots_skipped"],
            leader_skip_rate=data_to_report["leader_skip_rate"]
        )
        if success:
            logger.info(f"Successfully sent Discord notification for cluster {cluster_shorthand.upper()}.")
        else:
            logger.error(f"Failed to send Discord notification for cluster {cluster_shorthand.upper()}.")
    else:
        logger.warning(f"No data to report for cluster {cluster_shorthand.upper()}. Notification not sent.")

# The __main__ block below is for direct execution and testing of this module.
# It is not used when the application is run via main.py.
if __name__ == '__main__':
    # Example of how this script could be run directly for testing.
    # In a real scenario, this would be called by your scheduling mechanism (e.g., cron, systemd timer) via main.py.

    # Basic logging setup for direct script execution.
    # This allows seeing debug logs from this module when run standalone.
    # Note: main.py configures logging for the whole application based on config.toml.
    logging.basicConfig(
        level=logging.DEBUG, # Set to DEBUG to see all logs from this module during testing
        format='%(asctime)s - %(levelname)s - %(name)s - %(module)s.%(funcName)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    logger.info("--- Starting Validator Status Reporting (Direct Execution Example) ---")

    # --- Test Configuration ---
    # Select the cluster to test with:
    # cluster_to_test = "um"  # Mainnet - ensure config.toml has `identity_um` and `urls_um`
    cluster_to_test = "ut"  # Testnet - ensure config.toml has `identity_ut` and `urls_ut`
    # --- End Test Configuration ---

    logger.info(f"Attempting to report status for cluster: {cluster_to_test.upper()}")
    try:
        report_validator_status(cluster_to_test)
    except Exception as e_main:
        logger.critical(f"Critical error during direct execution example for {cluster_to_test.upper()}: {e_main}", exc_info=True)
        # For direct testing, it might be useful to see the full traceback.
        # import traceback
        # traceback.print_exc()

    logger.info(f"--- Validator Status Reporting Complete (Direct Execution Example for {cluster_to_test.upper()}) ---")
    logger.info("Review logs above for details. If successful, a Discord message should have been sent.")
    logger.info("To test with a different cluster, modify 'cluster_to_test' in this __main__ block.") 