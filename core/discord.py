import requests
import json
import logging
from typing import List
from .config import get_discord_webhook_url

logger = logging.getLogger(__name__)

def send_discord_message(message_lines: List[str]) -> bool:
    """
    Sends a multi-line message to the configured Discord webhook, one line at a time.

    Args:
        message_lines (List[str]): A list of strings, where each string is a line of the message.

    Returns:
        bool: True if all lines were sent successfully, False otherwise.
    """
    webhook_url = get_discord_webhook_url()
    if not webhook_url:
        logger.error("Discord webhook URL is not configured.")
        return False

    # Join all lines into a single string with newline characters
    content = "\n".join(message_lines)
    payload = {"content": content}

    try:
        response = requests.post(webhook_url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        # logger.debug(f"Successfully sent to Discord: {content}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending to Discord: {e} (Payload: {content})")
        return False

def format_and_send_status(
    cluster_name: str,
    validator_name: str,
    active_stake_sol: float,
    current_epoch: int,
    epoch_percent_complete: float,
    time_left_in_epoch: str,
    rank: int,
    epoch_credits: int,
    missed_credits: int,
    identity_pubkey: str,
    vote_account_pubkey: str,
    identity_balance_sol: float,
    vote_account_balance_sol: float,
    total_active_stake_sol: float,
    total_delegated_stake_sol: float,
    stake_activating_sol: float,
    stake_deactivating_sol: float,
    net_stake_change_sol: float,
    validator_version: str,
    validator_ip: str,
    leader_slots_total: int,
    leader_slots_completed: int,
    leader_slots_upcoming: int,
    leader_slots_skipped: int,
    leader_skip_rate: float
) -> bool:
    """
    Formats the validator status information and sends it to Discord.

    Args:
        cluster_name (str): "Mainnet" or "Testnet" (derived from cluster id like 'um' or 'ut').
        validator_name (str): The name of the validator.
        active_stake_sol (float): This is the activated stake from the vote account info, in SOL.
        current_epoch (int):
        epoch_percent_complete (float):
        time_left_in_epoch (str):
        rank (int | str): The validator's rank based on epoch credits (e.g., 1, 2, or 'N/A').
        epoch_credits (int | str): Credits earned by the validator in the current epoch (or 'N/A').
        missed_credits (int | str): Difference in credits compared to the top-ranked validator (or 'N/A').
        identity_pubkey (str): The validator's identity public key.
        vote_account_pubkey (str): The validator's vote account public key.
        identity_balance_sol (float | str): Balance of the identity account in SOL (or 'N/A').
        vote_account_balance_sol (float | str): Balance of the vote account in SOL (or 'N/A').
        total_active_stake_sol (float): Total active stake from 'solana stakes' command, in SOL.
        total_delegated_stake_sol (float): Total delegated stake from 'solana stakes' command, in SOL.
        stake_activating_sol (float): Stake activating from 'solana stakes' command, in SOL.
        stake_deactivating_sol (float): Stake deactivating from 'solana stakes' command, in SOL.
        net_stake_change_sol (float): Net stake change from 'solana stakes' command, in SOL.
        validator_version (str): Client version of the validator (e.g., "1.14.17 solana-validator") or "N/A".
        validator_ip (str): IP address of the validator (or "N/A").
        leader_slots_total (int): Total leader slots assigned to the validator in the current epoch.
        leader_slots_completed (int): Number of completed leader slots for the validator in the current epoch.
        leader_slots_upcoming (int): Number of upcoming leader slots for the validator in the current epoch.
        leader_slots_skipped (int): Number of skipped leader slots among completed ones for the validator.
        leader_skip_rate (float): Percentage of completed slots that were skipped by the validator.

    Returns:
        bool: True if the message was sent successfully, False otherwise.
    """
    display_cluster_name = "Mainnet" if cluster_name.lower() == "um" else "Testnet" if cluster_name.lower() == "ut" else cluster_name.capitalize()

    message_lines = [
        f"========================================================",
        f"**                     🔥  __{display_cluster_name} Status: {validator_name}__  🔥**",
        f"========================================================",
        f"**__Validator Info__  🔍**",
        f"**Identity:**   `{identity_pubkey}`",
        f"**Vote:**         `{vote_account_pubkey}`",
        f"**Version:**    `{validator_version}`",
        f"**IP:**               `{validator_ip}`",
        f"========================================================",
        f"**__Account Balances__  💰**",
        f"**Identity Balance:**   `{identity_balance_sol:,.2f} ◎`",
        f"**Vote Balance:**          `{vote_account_balance_sol:,.2f} ◎`",
        f"========================================================",
        f"**__Stake Info__  🥩**",
        f"**Total Active:**           `{total_active_stake_sol:,.2f} ◎`",
        f"**Total Delegated:**    `{total_delegated_stake_sol:,.2f} ◎`",
        f"**Activating:**               `{stake_activating_sol:,.2f} ◎`",
        f"**Deactivating:**          `{stake_deactivating_sol:,.2f} ◎`",
        f"**Net Change:**            `{net_stake_change_sol:,.2f} ◎`",
        f"========================================================",
        f"**__Leader Info__  👑**",
        f"**Total Slots:**             `{leader_slots_total} slots`",
        f"**Completed:**             `{leader_slots_completed} slots`",
        f"**Upcoming:**               `{leader_slots_upcoming} slots`",
        f"**Skipped:**                   `{leader_slots_skipped} slots`",
        f"**Skip Rate:**                `{leader_skip_rate:.2f}%`",
        f"========================================================",
        f"**__Epoch Metrics__ ⌛️**",
        f"**Current Epoch:**      `{current_epoch}`",
        f"**Completed %:**         `{epoch_percent_complete:.2f}%`",
        f"**Time Left:**                `{time_left_in_epoch}`",
        f"========================================================",
        f"**__Vote Metrics__  📈**", 
        f"**TVC Rank:**               `{rank}`", 
        f"**Epoch Credits:**      `{epoch_credits:,}`",
        f"**Missed Credits:**    `{missed_credits:,}`",
        f"========================================================",
    ]
    return send_discord_message(message_lines) 