import pandas as pd
import json

class DataExporter:
    @staticmethod
    def export_wallet_analysis(results, filename='results.csv'):
        """
        Exports wallet analysis results to a CSV file, sorted by Total PNL in descending order.

        Parameters:
            results (list): A list of dictionaries containing analysis results for each wallet.
            filename (str): The name of the output CSV file.
        """

        valid_results = [result for result in results if result is not None]

        if not valid_results:
            print("No valid results to export.")
            return

        # Create a DataFrame from the results
        df = pd.DataFrame(valid_results)

        # Sort by Total PNL in descending order
        df_sorted = df.sort_values(by='total_pnl', ascending=False)

        # Specify columns to include in the output
        columns_to_export = ['address', 'total_pnl', 'realized_pnl', 'unrealized_pnl', 'win_rate', 'settings']

        try:
            # Export to CSV
            df_sorted[columns_to_export].to_csv(filename, index=False)
            print(f"Results successfully exported: {len(valid_results)} wallets to {filename}.")

        except Exception as e:
            print(f"Error exporting results: {e}")

    @staticmethod
    def export_to_json(data, filename):
        """
        Exports data to a JSON file.

        Parameters:
            data (any): The data to export.
            filename (str): The name of the output JSON file.
        """
        try:
            with open(filename, 'w') as f:
                json.dump(data, f)
            print(f"Data successfully exported to {filename}.")
        except Exception as e:
            print(f"Error exporting data to JSON: {e}")