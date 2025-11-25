# AdShare Automation Scripts - GitHub Actions Setup

This guide provides instructions to set up your intelligent AdShare automation scripts using GitHub Actions.

## 🚀 Overview

This automation suite intelligently manages your AdShare campaigns by:
-   **Dynamic Login**: Securely logs in and maintains session persistence.
-   **Smart Bid Monitoring**: Monitors active campaigns, checks completion percentage (only acts if `< 95% complete`), and adjusts bids to stay competitive. It reduces check frequency for highly completed campaigns to save resources.
-   **Daily Visitor Assignment**: Automatically assigns 50 visitors with a 12-hour revisit schedule to campaigns marked as 'COMPLETE' once per day at a randomized time.
-   **Robustness**: Includes retry mechanisms for network errors and dynamic parsing for website changes.

## 📋 Scripts Included

1.  **`adshare_login.py`**: Centralized script for handling dynamic login, session creation, and cookie management.
2.  **`bid_monitor.py`**: The intelligent bid monitoring script.
3.  **`daily_assigner.py`**: The daily visitor assignment script.

## ⚙️ GitHub Actions Workflows

These workflow files define when and how your scripts run on GitHub's servers. They are located in the `.github/workflows/` directory.

1.  **`bid_monitor.yml`**:
    *   **Purpose**: Runs the `bid_monitor.py` script.
    *   **Schedule**: Every 15 minutes. The script itself determines if actual bidding checks are needed based on campaign completion.
    *   **Optimized**: Conserves GitHub Actions minutes by intelligently pausing or skipping checks when campaigns are highly completed.

2.  **`daily_assigner.yml`**:
    *   **Purpose**: Runs the `daily_assigner.py` script.
    *   **Schedule**: Once daily around **12:15 UTC (5:45 PM IST)**. The script includes an additional random delay to vary the execution time within a 5:30 PM - 6:00 PM IST window.

## 🛠️ Setup Instructions

Follow these steps carefully to deploy your automation:

### 1. Create a GitHub Repository

*   If you don't have one, create a new public or private GitHub repository. (e.g., `adshare-automation`).

### 2. Upload Your Scripts

*   Copy the three Python scripts to the **root** of your GitHub repository:
    *   `adshare_login.py`
    *   `bid_monitor.py`
    *   `daily_assigner.py`
*   You will also need to create the `.github/workflows/` directory in your repository. Then, upload the two `.yml` workflow files into this directory:
    *   `bid_monitor.yml`
    *   `daily_assigner.yml`

### 3. Configure Repository Secrets

Your AdShare username and password are sensitive. We will store them securely using GitHub Secrets.

*   Go to your GitHub repository.
*   Click on the **`Settings`** tab.
*   In the left sidebar, navigate to **`Secrets and variables`** > **`Actions`**.
*   Click **`New repository secret`** and add the following two secrets:
    *   **Name**: `ADSHARE_USERNAME`, **Value**: Your AdShare account email (e.g., `jiocloud90@gmail.com`)
    *   **Name**: `ADSHARE_PASSWORD`, **Value**: Your AdShare account password (e.g., `@Sd2007123`)

### 4. Initial Session Setup (Optional but Recommended)

For the very first run, it's beneficial to establish an initial session and save cookies locally. This helps the GitHub Actions workflow start with an existing session.

*   **Run `adshare_login.py` locally** once on your computer or Termux:
    ```bash
    python adshare_login.py
    ```
    This will create a `session_cookies.pkl` file.
*   **Upload `session_cookies.pkl`** to the root of your GitHub repository. This file will be managed by GitHub Actions artifacts thereafter.

### 5. Workflows Activation

*   Once the scripts, workflow files, and secrets are in place, the GitHub Actions workflows will automatically activate according to their schedules.
*   You can monitor their execution under the **`Actions`** tab of your repository.

### 6. Manual Testing (Optional)

To test immediately, go to the **`Actions`** tab in your repository, select either "Smart Bid Monitor" or "Daily Visitor Assigner" workflow, and click **`Run workflow`**.

## 🧠 Smart Features Explained

*   **Intelligent Bid Monitoring**: The `bid_monitor.py` script fetches campaign data. If all your campaigns are detected as being `95% or more completed`, the script will simply exit. This saves valuable GitHub Actions minutes, as it avoids unnecessary bidding checks when campaigns are nearly full. Bid adjustments only occur for campaigns that are still actively receiving visitors (under 95% complete) and your bid is not the highest.
*   **Randomized Daily Assignment**: The `daily_assigner.py` will run approximately at 5:45 PM IST, but introduces a random delay to prevent predictable automation patterns. It checks for `COMPLETE` campaigns and assigns 50 visitors to the first one it finds.
*   **Session Persistence**: The `adshare-session` artifact (containing `session_cookies.pkl`) is uploaded after each successful workflow run and downloaded before the next. This ensures your session is maintained across runs without needing to re-login every time.

## 🔒 Security

*   Your AdShare credentials are kept secure as GitHub Repository Secrets and are never exposed in logs or code.
*   `ADSHARE_USERNAME` and `ADSHARE_PASSWORD` are accessed as environment variables within the GitHub Actions runtime.

## 📊 Resource Optimization

The entire system is designed to minimize GitHub Actions minutes usage by:
*   Intelligently pausing or skipping checks when campaigns do not require action.
*   Only running bid checks during periods when campaigns are actively receiving visitors.
*   Using shared session management to avoid repeated logins.

This completes the setup. Your AdShare automation system is now ready!