from transaction_fetcher import TransactionFetcher
from transaction_processor import TransactionProcessor
from price_fetcher import PriceFetcher
from data_exporter import DataExporter
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class WalletAnalyzer:
    def __init__(self):
        """
        Initializes the WalletAnalyzer with necessary components.
        """
        self.fetcher = TransactionFetcher()
        self.processor = TransactionProcessor()
        self.price_fetcher = PriceFetcher()
        self.exporter = DataExporter()

    def analyze_wallets_and_export(self, wallet_addresses, timeframe, minimum_wallet_capital, minimum_avg_holding_period, minimum_win_rate, minimum_total_pnl, export_filename='analysis_results.csv'):
        """
        Analyzes multiple wallets and exports the results to a file.
        Parameters:
            wallet_addresses (list): List of wallet addresses to analyze.
            timeframe (str): The timeframe to filter transactions ('1', '3', '6', '12', or 'overall').
            minimum_wallet_capital (float): Minimum capital required in USD.
            minimum_avg_holding_period (int): Minimum average holding period in minutes.
            minimum_win_rate (float): Minimum win rate percentage.
            minimum_total_pnl (float): Minimum total PnL in USD.
            export_filename (str): Filename for exporting results.
        """
        results = []

        for address in wallet_addresses:
            logging.info(f"Analyzing wallet: {address}")
            result = self.analyze_wallet(address, timeframe, minimum_wallet_capital, minimum_avg_holding_period, minimum_win_rate, minimum_total_pnl)
            if result:
                results.append(result)
            else:
                logging.info(f"Wallet {address} excluded from analysis.")

        # Export results after analysis
        logging.info("Exporting wallet analysis results...")
        self.exporter.export_wallet_analysis(results, filename=export_filename)

    def analyze_wallet(self, wallet_address, timeframe, minimum_wallet_capital, minimum_avg_holding_period, minimum_win_rate, minimum_total_pnl):
        """
        Analyzes a single wallet based on specified criteria.
        Parameters:
            wallet_address (str): The wallet address to analyze.
            timeframe (str): The timeframe to filter transactions.
            minimum_wallet_capital (float): Minimum capital required in USD.
            minimum_avg_holding_period (int): Minimum average holding period in minutes.
            minimum_win_rate (float): Minimum win rate percentage.
            minimum_total_pnl (float): Minimum total PnL in USD.
        Returns:
            dict: Analysis results for the wallet.
        """
        logging.info(f"Checking wallet capital for {wallet_address}...")
        if not self.check_wallet_capital(wallet_address, minimum_wallet_capital):
            logging.info(f"Wallet {wallet_address} excluded due to insufficient capital.")
            return None

        logging.info(f"Fetching transactions for wallet {wallet_address}...")
        transactions = self.fetcher.fetch_transaction_history(wallet_address)
        if not transactions:
            logging.info(f"No transactions found for wallet: {wallet_address}")
            return {
                "address": wallet_address,
                "total_pnl": 0,
                "realized_pnl": 0,
                "unrealized_pnl": 0,
                "win_rate": 0,
                "buy_sell_dates": []
            }

        processed_transactions = self.process_transactions_concurrently(transactions)
        if not processed_transactions:
            logging.warning(f"No valid transactions processed for wallet {wallet_address}.")
            return None

        total_pnl, realized_pnl, unrealized_pnl, win_rate, buy_sell_dates = self.calculate_pnl(processed_transactions)

        avg_holding_period, holding_count = self.calculate_avg_holding_period(buy_sell_dates)

        # Apply exclusion criteria
        if win_rate < minimum_win_rate or total_pnl < minimum_total_pnl:
            # Determine which threshold caused the exclusion
            reason = []
            if win_rate < minimum_win_rate:
                reason.append(f"win rate ({win_rate:.2f}% < {minimum_win_rate}%)")
            if total_pnl < minimum_total_pnl:
                reason.append(f"total PnL ({total_pnl:.2f} < {minimum_total_pnl})")
            
            # Log the reason for exclusion with exact thresholds
            logging.info(f"Wallet {wallet_address} excluded due to: " + ", ".join(reason) + ".")
            return None

        if avg_holding_period < minimum_avg_holding_period:
            # Log the exact values that led to exclusion
            logging.info(f"Wallet {wallet_address} excluded due to short average holding period ({avg_holding_period:.2f} minutes < {minimum_avg_holding_period} minutes).")
            return None

        return {
            "address": wallet_address,
            "total_pnl": total_pnl,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "win_rate": win_rate,
            "settings": {
                "timeframe": timeframe,
                "minimum_wallet_capital": minimum_wallet_capital,
                "minimum_avg_holding_period": minimum_avg_holding_period,
                "minimum_win_rate": minimum_win_rate,
                "minimum_total_pnl": minimum_total_pnl
            },
            "trades": buy_sell_dates  
        }

    def check_wallet_capital(self, address, minimum_capital_usd):
        """
        Checks if the wallet has sufficient capital.
        Parameters:
            address (str): The wallet address.
            minimum_capital_usd (float): Minimum capital required in USD.
        Returns:
            bool: True if the wallet meets the capital requirement, False otherwise.
        """
        logging.info(f"Fetching wallet balance for {address}...")
        sol_balance = self.fetcher.fetch_wallet_balance(address)
        sol_to_usd = self.get_sol_to_usd_price()

        if sol_to_usd == 0:
            logging.warning(f"Failed to fetch SOL to USD price for wallet {address}.")
            return False

        wallet_balance_usd = sol_balance * sol_to_usd
        logging.info(f"Wallet {address} balance: {wallet_balance_usd:.2f} USD (SOL: {sol_balance:.2f})")

        return wallet_balance_usd >= minimum_capital_usd

    @lru_cache(maxsize=128)
    def get_sol_to_usd_price(self):
        """
        Fetches the current SOL to USD price with caching.
        Returns:
            float: The current SOL to USD price.
        """
        return self.price_fetcher.get_sol_to_usd_price()

    def process_transactions_concurrently(self, transactions):
        """
        Processes transactions concurrently using ThreadPoolExecutor with error handling.
        Parameters:
            transactions (list): List of transaction signatures.
        Returns:
            list: List of processed transactions.
        """
        def fetch_and_process(tx):
            try:
                details = self.fetcher.fetch_transaction_details(tx['signature'])
                if not details:
                    logging.warning(f"Skipping transaction {tx['signature']} due to missing details.")
                    return None
                account_keys = details.get("transaction", {}).get("message", {}).get("accountKeys", [])
                return self.processor.process_transaction(details, account_keys)
            except Exception as e:
                logging.error(f"Error processing transaction {tx['signature']}: {e}")
                return None

        with ThreadPoolExecutor() as executor:
            results = list(executor.map(fetch_and_process, transactions))

        return [tx for tx in results if tx]  # Filter out None values

    def calculate_pnl(self, processed_transactions):
        """
        Calculates PnL metrics for the wallet.
        Parameters:
            processed_transactions (list): List of processed transactions.
        Returns:
            tuple: Total PnL, realized PnL, unrealized PnL, win rate, and buy/sell dates.
        """
        total_pnl = 0
        realized_pnl = 0
        unrealized_pnl = 0
        profitable_trades = 0
        total_trades = 0
        buy_sell_dates = []
        bought_assets = {}

        for transaction in processed_transactions:
            if not transaction:
                continue

            if transaction.type == "buy":
                amount = transaction.amount
                price = self.get_token_price(transaction.token)
                if price == 0:
                    logging.warning(f"Failed to fetch price for token {transaction.token}. Skipping buy transaction.")
                    continue
                unrealized_pnl -= amount * price
                bought_assets[transaction.token] = {
                    "price": price,
                    "amount": amount,
                    "timestamp": transaction.timestamp
                }
                buy_sell_dates.append({
                    'transaction': 'buy',
                    'datetime': datetime.fromtimestamp(transaction.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                })

            elif transaction.type == "sell":
                amount = transaction.amount
                price = self.get_token_price(transaction.token)
                if price == 0:
                    logging.warning(f"Failed to fetch price for token {transaction.token}. Skipping sell transaction.")
                    continue
                if transaction.token not in bought_assets:
                    logging.warning(f"No matching buy transaction found for sell of {transaction.token}. Skipping.")
                    continue

                buy_price = bought_assets[transaction.token]["price"]
                realized_pnl += amount * price - amount * buy_price
                profitable_trades += 1 if price > buy_price else 0
                del bought_assets[transaction.token]
                buy_sell_dates.append({
                    'transaction': 'sell',
                    'datetime': datetime.fromtimestamp(transaction.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                })

            total_trades += 1

        # Calculate unrealized PnL for unsold assets
        for token, asset in bought_assets.items():
            current_price = self.get_token_price(token)
            if current_price == 0:
                logging.warning(f"Failed to fetch current price for token {token}. Skipping unrealized PNL calculation.")
                continue
            unrealized_pnl += asset["amount"] * (current_price - asset["price"])

        total_pnl = realized_pnl + unrealized_pnl
        win_rate = (profitable_trades / total_trades) * 100 if total_trades > 0 else 0

        return total_pnl, realized_pnl, unrealized_pnl, win_rate, buy_sell_dates

    @lru_cache(maxsize=128)
    def get_token_price(self, token):
        """
        Fetches the current price of a token with caching.
        Parameters:
            token (str): The token symbol or mint address.
        Returns:
            float: The current price of the token.
        """
        return self.price_fetcher.get_token_price(token)

    def calculate_avg_holding_period(self, buy_sell_dates):
        """
        Calculates the average holding period for buy/sell pairs.
        Parameters:
            buy_sell_dates (list): List of buy/sell date dictionaries.
        Returns:
            tuple: Average holding period in minutes and the count of holding periods.
        """
        if not buy_sell_dates or len(buy_sell_dates) < 2:
            logging.info("Insufficient buy/sell data to calculate average holding period.")
            return 0, 0

        holding_periods = []
        buy_indices = [i for i, d in enumerate(buy_sell_dates) if d['transaction'] == 'buy']
        sell_indices = [i for i, d in enumerate(buy_sell_dates) if d['transaction'] == 'sell']

        for buy_idx, sell_idx in zip(buy_indices, sell_indices):
            if sell_idx <= buy_idx or sell_idx >= len(buy_sell_dates):
                logging.warning(f"Unmatched buy/sell pair at index {buy_idx}. Skipping.")
                continue

            buy_time = datetime.strptime(buy_sell_dates[buy_idx]['datetime'], '%Y-%m-%d %H:%M:%S')
            sell_time = datetime.strptime(buy_sell_dates[sell_idx]['datetime'], '%Y-%m-%d %H:%M:%S')
            holding_period = (sell_time - buy_time).total_seconds() / 60
            holding_periods.append(holding_period)

        avg_period = sum(holding_periods) / len(holding_periods) if holding_periods else 0
        logging.info(f"Average holding period: {avg_period:.2f} minutes.")
        return avg_period, len(holding_periods)