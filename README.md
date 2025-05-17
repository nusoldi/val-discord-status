# Solana Validator Discord Status

Simple Python package that fetches comprehensive status and performance metrics for a Solana validator and sends a formatted report to a Discord channel via a webhook. It can be configured to monitor validators on different clusters (e.g., Mainnet, Testnet) and can be automated using systemd services.

![image](https://github.com/user-attachments/assets/acbc94b8-8d9b-4fde-a3fe-93ce08c6a931)

## Table of Contents

- [About The Project](#about-the-project)
- [Key Features](#key-features)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Install Python Dependencies](#2-install-python-dependencies)
  - [3. Configure the Application](#3-configure-the-application)
- [Usage](#usage)
  - [Manual Execution](#manual-execution)
- [Automation with Systemd](#automation-with-systemd)
  - [Service Files](#service-files)
  - [Setup Steps](#setup-steps)
  - [Managing Services](#managing-services)
- [Configuration Details (`config.toml`)](#configuration-details-configtoml)
- [Project Structure](#project-structure)
- [License](#license)


## Key Features

-   Fetches a wide range of validator metrics:
    -   Account balances (identity and vote)
    -   Active, delegated, activating, and deactivating stake
    -   Epoch information (current epoch, progress, time remaining)
    -   Validator rank and epoch credits (compared to top validator)
    -   Leader slot performance (total, completed, upcoming, skipped, skip rate)
    -   Validator client version and IP address
-   Supports multiple Solana clusters (e.g., Mainnet `um`, Testnet `ut`).
-   Configurable RPC endpoints with retry logic.
-   Includes systemd service files for automation.

## Prerequisites

-   **Python 3.8+**: The application is written in Python.
-   **pip**: Python package installer.
-   **Solana Command-Line Tools (CLI)**: Required for some data-fetching operations.

## Installation & Setup

Follow these steps for installation:

### 1. Clone the Repository

```bash
git clone https://github.com/nusoldi/val-discord-status.git
cd val-discord-status
```

### 2. Install Python Dependencies

The project uses a few Python libraries listed in `requirements.txt`.

```bash
pip install -r requirements.txt
```

### 3. Configure the Application

Configuration is done via the `config.toml` file. You **MUST** edit this file to provide your specific details.

```bash
nano config.toml # Or use your preferred text editor
```

**Critical fields to update in `config.toml`:**

-   `[discord]`
    -   `webhook_url`: **Enter your Discord webhook URL here.**
-   `[validator]`
    -   `identity_um`: Validator identity pubkey for Mainnet.
    -   `identity_ut`: Validator identity pubkey for Testnet

## Usage

### Manual Execution

You can run the script manually from the project's root directory:

```bash
python3 main.py --cluster <cluster_shorthand>
```

Replace `<cluster_shorthand>` with:
-   `um`: For Mainnet
-   `ut`: For Testnet

**Example for Mainnet:**
```bash
python3 main.py --cluster um
```

**Example for Testnet:**
```bash
python3 main.py --cluster ut
```

Logs will be printed to the console based on the `log_level` in `config.toml`.

## Automation with Systemd

Systemd service files are included in the `services/` directory to automate the script to run every hour.

### Service Files

-   `services/dc-status-um.service`: For Mainnet
-   `services/dc-status-ut.service`: For Testnet

Review these files, especially the `User`, `Environment` (PATH for Solana CLI), `ExecStart`, and `WorkingDirectory`, and adjust as needed.

### Setup Steps

1.  **Copy the service files** to the systemd directory:
    ```bash
    sudo cp services/dc-status-um.service /etc/systemd/system/
    sudo cp services/dc-status-ut.service /etc/systemd/system/
    ```

2.  **Reload the systemd daemon** to recognize the new services:
    ```bash
    sudo systemctl daemon-reload
    ```

3.  **Enable the services** to start on boot:
    ```bash
    sudo systemctl enable --now dc-status-um.service
    sudo systemctl enable --now dc-status-ut.service
    ```

4.  **Start the services**:
    ```bash
    sudo systemctl start dc-status-um.service
    sudo systemctl start dc-status-ut.service
    ```

### Managing Services

-   **Check status**:
    ```bash
    sudo systemctl status dc-status-um.service
    sudo systemctl status dc-status-ut.service
    ```

-   **View logs**:
    ```bash
    sudo journalctl -u dc-status-um.service
    sudo journalctl -u dc-status-ut.service
    ```

-   **Stop services**:
    ```bash
    sudo systemctl stop dc-status-um.service
    sudo systemctl stop dc-status-ut.service
    ```

-   **Restart services**:
    ```bash
    sudo systemctl restart dc-status-um.service
    sudo systemctl restart dc-status-ut.service
    ```

## Configuration Details (`config.toml`)

The `config.toml` file is central to the application's behavior:

-   **`[discord]`**:
    -   `webhook_url`: Discord channel webhook URL.
-   **`[validator]`**:
    -   `identity_um`: Validator identity pubkey for Mainnet (`um`).
    -   `identity_ut`: Validator identity pubkey for Testnet (`ut`).
-   **`[rpc_urls]`**:
    -   `urls_um`: List of RPC endpoint URLs for Mainnet.
    -   `urls_ut`: List of RPC endpoint URLs for Testnet.
-   **`[rpc_settings]`**:
    -   `rpc_max_retries`: Number of additional full passes through the RPC URL list if all fail.
    -   `rpc_retry_delay_seconds`: Delay (in seconds) between retry passes.
-   **`[logging]`**:
    -   `log_level`: Desired logging verbosity (e.g., `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).

## Project Structure

-   `main.py`: Main executable script that parses arguments and orchestrates the data fetching and reporting.
-   `config.toml`: User configuration file.
-   `requirements.txt`: Python dependencies.
-   `core/`: Python package containing the core logic.
    -   `config.py`: Loads and provides access to `config.toml` settings.
    -   `fetch_data.py`: Contains all functions for interacting with Solana RPC/CLI and processing validator data.
    -   `discord.py`: Formats messages and sends them to the Discord webhook.
-   `services/`: Contains systemd service files for automation.
    -   `dc-status-um.service`: Systemd service for Mainnet.
    -   `dc-status-ut.service`: Systemd service for Testnet.
-   `.gitignore`: Specifies intentionally untracked files that Git should ignore.
-   `LICENSE`: Project license file.
-   `README.md`: This file.

## License

Distributed under the GPL-3.0 License. See `LICENSE` for more information.
