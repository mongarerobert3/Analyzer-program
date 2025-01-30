from transaction_fetcher import TransactionFetcher
from transaction_processor import TransactionProcessor
from price_fetcher import PriceFetcher
from data_exporter import DataExporter
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class WalletAnalyzer:
    def __init__(self):
        self.fetcher = TransactionFetcher()
        self.processor = TransactionProcessor()
        self.price_fetcher = PriceFetcher()
        self.exporter = DataExporter()

    def analyze_wallets_and_export(self, wallet_addresses, timeframe, minimum_wallet_capital, minimum_avg_holding_period, minimum_win_rate, minimum_total_pnl, export_filename='analysis_results.csv'):
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

        processed_transactions = []
        for tx in transactions:
            details = self.fetcher.fetch_transaction_details(tx['signature'])
            if not details:
                logging.warning(f"Error fetching details for transaction {tx['signature']}.")
                continue

            account_keys = details.get("transaction", {}).get("message", {}).get("accountKeys", [])
            processed_tx = self.processor.process_transaction(details, account_keys)
            if processed_tx:
                processed_transactions.append(processed_tx)

        total_pnl = 0
        realized_pnl = 0
        unrealized_pnl = 0
        profitable_trades = 0
        total_trades = 0
        buy_sell_dates = []

        bought_assets = {}

        for transaction in processed_transactions:  # Iterate through *processed* transactions
            if not transaction:  # Check if the transaction is valid
                continue

            if transaction.type == "buy":
                amount = transaction.amount
                price = self.price_fetcher.get_sol_to_usd_price()
                if price == 0:  # Handle price fetching errors
                    logging.warning("Failed to fetch SOL price. Skipping buy transaction.")
                    continue
                unrealized_pnl -= amount * price
                bought_assets[transaction.token] = {"price": price, "amount": amount, "timestamp": transaction.timestamp}
                buy_sell_dates.append({'transaction': 'buy', 'datetime': datetime.fromtimestamp(transaction.timestamp).strftime('%Y-%m-%d %H:%M:%S')})

            elif transaction.type == "sell":
                amount = transaction.amount
                price = self.price_fetcher.get_sol_to_usd_price()
                if price == 0:  # Handle price fetching errors
                    logging.warning("Failed to fetch SOL price. Skipping sell transaction.")
                    continue
                realized_pnl += amount * price
                profitable_trades += 1 if amount * price > bought_assets.get(transaction.token, {}).get("price", 0) else 0 #Check if bought assets price is greater than zero
                buy_sell_dates.append({'transaction': 'sell', 'datetime': datetime.fromtimestamp(transaction.timestamp).strftime('%Y-%m-%d %H:%M:%S')})

            total_trades += 1

        total_pnl = realized_pnl + unrealized_pnl
        win_rate = (profitable_trades / total_trades) * 100 if total_trades > 0 else 0

        if win_rate < minimum_win_rate or total_pnl < minimum_total_pnl:
            logging.info(f"Wallet {wallet_address} excluded due to low win rate or PNL.")
            return None

        logging.info(f"Calculating average holding period for wallet {wallet_address}...")
        avg_holding_period, _ = self.calculate_avg_holding_period(buy_sell_dates)
        if avg_holding_period < minimum_avg_holding_period:
            logging.info(f"Wallet {wallet_address} excluded due to short average holding period.")
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
            }
        }

    def check_wallet_capital(self, address, minimum_capital_usd):
        logging.info(f"Fetching wallet balance for {address}...")
        sol_balance = self.fetcher.fetch_wallet_balance(address)
        sol_to_usd = self.price_fetcher.get_sol_to_usd_price()
        
        if sol_to_usd == 0:
            logging.warning(f"Failed to fetch SOL to USD price for wallet {address}.")
            return False
        
        wallet_balance_usd = sol_balance * sol_to_usd
        logging.info(f"Wallet {address} balance: {wallet_balance_usd:.2f} USD (SOL: {sol_balance:.2f})")
        
        return wallet_balance_usd >= minimum_capital_usd

    def is_within_timeframe(self, tx_timestamp, timeframe):
        if not tx_timestamp:
            return False

        current_time = datetime.now()
        delta_days = (current_time - datetime.fromtimestamp(tx_timestamp)).days

        if timeframe == '1':
            return delta_days <= 30
        elif timeframe == '3':
            return delta_days <= 90
        elif timeframe == '6':
            return delta_days <= 180
        elif timeframe == '12':
            return delta_days <= 365
        else:
            return True

    def calculate_avg_holding_period(self, buy_sell_dates):
        if not buy_sell_dates or len(buy_sell_dates) < 2:
            logging.info("Insufficient buy/sell data to calculate average holding period.")
            return 0, 0

        holding_periods = []
        for i in range(1, len(buy_sell_dates), 2):
            if i >= len(buy_sell_dates):
                break

            buy_time = datetime.strptime(buy_sell_dates[i-1]['datetime'], '%Y-%m-%d %H:%M:%S')
            sell_time = datetime.strptime(buy_sell_dates[i]['datetime'], '%Y-%m-%d %H:%M:%S')
            holding_period = (sell_time - buy_time).total_seconds() / 60
            holding_periods.append(holding_period)

        avg_period = sum(holding_periods) / len(holding_periods) if holding_periods else 0
        logging.info(f"Average holding period: {avg_period:.2f} minutes.")
        return avg_period, len(holding_periods)