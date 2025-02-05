import logging
import pandas as pd
from decouple import config
from api_client import APIClient
from wallet_analyzer import WalletAnalyzer
from data_exporter import DataExporter

class Bot:
    def __init__(self):
        self.analyzer = WalletAnalyzer()
        self.api_client = APIClient()
        self.data_exporter = DataExporter()

    def load_wallet_addresses_from_csv(self, file_path='addresses.csv'):
        """Loads wallet addresses from a CSV file."""
        try:
            df = pd.read_csv(file_path)
            print(f"Wallet addresses loaded from {file_path}")
            return df.iloc[:, 0].tolist()  
        except FileNotFoundError:
            print(f"Error: The file '{file_path}' does not exist.")
        except Exception as e:
            print(f"Error loading CSV file: {e}")
        return []

    def run(self, csv_filename='addresses.csv', timeframe='3',
        minimum_wallet_capital=1000, minimum_avg_holding_period=60,
        minimum_win_rate=30, minimum_total_pnl=500, export_filename='results.csv'):
        """
        Main function to execute wallet analysis.
        Parameters:
            csv_filename (str): Path to the CSV file containing wallet addresses.
            timeframe (str): Timeframe for filtering transactions ('1', '3', '6', '12', or 'overall').
            minimum_wallet_capital (float): Minimum capital required in USD.
            minimum_avg_holding_period (int): Minimum average holding period in minutes.
            minimum_win_rate (float): Minimum win rate percentage.
            minimum_total_pnl (float): Minimum total PnL in USD.
            export_filename (str): Filename for exporting results.
        """
        # Log the start of the workflow
        logging.info("Starting wallet analysis workflow.")

        # Load wallet addresses from the CSV file
        wallet_addresses = self.load_wallet_addresses_from_csv(csv_filename)
        if not wallet_addresses:
            logging.warning("No wallet addresses found in the CSV file. Exiting workflow.")
            return

        # Initialize results list
        results = []

        # Analyze each wallet address
        for wallet_address in wallet_addresses:
            logging.info(f"Analyzing wallet {wallet_address}...")

            # Fetch and analyze wallet data
            wallet_results = self.analyzer.analyze_wallet(
                wallet_address,
                timeframe,
                minimum_wallet_capital,
                minimum_avg_holding_period,
                minimum_win_rate,
                minimum_total_pnl
            )

            # Validate and append results
            if wallet_results and self.is_wallet_valid(wallet_results):
                logging.info(f"Wallet {wallet_address} passed the analysis criteria.")
                results.append(wallet_results)
            else:
                logging.info(f"Wallet {wallet_address} excluded due to low win rate, PnL, or other criteria.")

        # Export results to CSV if there are valid results
        if results:
            logging.info(f"Exporting {len(results)} valid results to {export_filename}.")
            self.data_exporter.export(results, export_filename)
        else:
            logging.info("No valid results to export. Workflow completed.")


    @staticmethod
    def is_wallet_valid(wallet_results):
        """Checks if a wallet meets the analysis criteria."""
        return wallet_results.get('win_rate', 0) >= 50 and wallet_results.get('total_pnl', 0) >= 100


if __name__ == "__main__":
    bot = Bot()
    bot.run(csv_filename='addresses.csv')  
