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

    def run(self, csv_filename='addresses.csv', timeframe='1',
            minimum_wallet_capital=1000, minimum_avg_holding_period=0,
            minimum_win_rate=0, minimum_total_pnl=0, export_filename='results.csv'):
        """Main function to execute wallet analysis."""
        print("Starting wallet analysis...")
        wallet_addresses = self.load_wallet_addresses_from_csv(csv_filename)

        if not wallet_addresses:
            print("No wallet addresses found. Exiting.")
            return

        results = []

        for wallet_address in wallet_addresses:
            print(f"Analyzing wallet {wallet_address}...")

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
                print(f"Wallet {wallet_address} passed the analysis criteria.")
                results.append(wallet_results)
            else:
                print(f"Wallet {wallet_address} excluded due to low win rate or PNL.")

        if results:
            print(f"Exporting {len(results)} valid results to CSV.")
            self.data_exporter.export(results, export_filename)
        else:
            print("No valid results to export.")


    @staticmethod
    def is_wallet_valid(wallet_results):
        """Checks if a wallet meets the analysis criteria."""
        return wallet_results.get('win_rate', 0) >= 50 and wallet_results.get('total_pnl', 0) >= 100


if __name__ == "__main__":
    bot = Bot()
    bot.run(csv_filename='addresses.csv')  # Run with the default CSV file of wallet addresses
