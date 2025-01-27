import csv

class TransactionFetcher:
    def __init__(self, client):
        self.client = client

    def fetch_transaction_details(self, transaction_id):
        """
        Fetches detailed information about a specific transaction.

        Parameters:
            transaction_id (str): The ID of the transaction to fetch details for.

        Returns:
            dict or None: The details of the transaction if successful, None otherwise.
        """
        result = self.client.post_request(f"getTransaction/{transaction_id}", {"encoding": "jsonParsed"})
        if not result:
            return None
        return result.get("result", None)


class MockClient:
    """Mock client to simulate API responses."""
    def post_request(self, endpoint, data):
        # Simulate a realistic response for the given transaction ID
        if "getTransaction" in endpoint:
            transaction_id = endpoint.split("/")[-1]
            if transaction_id == "valid_tx_id":
                return {
                    "result": {
                        "blockTime": 1672531200,
                        "transfers": [
                            {"token_id": "token_1", "amount": 100},
                            {"token_id": "token_2", "amount": 200}
                        ],
                        "details": "Sample transaction details",
                        "amount": 300
                    }
                }
            elif transaction_id == "invalid_tx_id":
                return None  # Simulate a failed API call
        return None


def load_wallet_addresses(csv_file):
    """
    Loads wallet addresses from a CSV file.

    Parameters:
        csv_file (str): The path to the CSV file containing wallet addresses.

    Returns:
        list: A list of wallet addresses.
    """
    wallet_addresses = []
    try:
        with open(csv_file, mode="r") as file:
            csv_reader = csv.reader(file)
            for row in csv_reader:
                # Skip header and empty rows
                if row and row[0] != "id":
                    wallet_addresses.append(row[0])
        print(f"Loaded {len(wallet_addresses)} wallet addresses from {csv_file}.")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
    return wallet_addresses


def test_transaction_details_from_csv(csv_file):
    # Initialize the mock client and fetcher
    mock_client = MockClient()
    fetcher = TransactionFetcher(mock_client)

    # Load wallet addresses from the CSV file
    wallet_addresses = load_wallet_addresses(csv_file)

    # Test transaction details for each wallet address
    for address in wallet_addresses:
        print(f"Testing transactions for wallet address: {address}")

        # Replace with actual logic to get a transaction ID for the wallet
        # Here, we simulate using 'valid_tx_id' or 'invalid_tx_id' for testing
        transaction_id = "valid_tx_id" if address.endswith("1") else "invalid_tx_id"

        result = fetcher.fetch_transaction_details(transaction_id)
        if result and "amount" in result:
            print(f"Amount for transaction {transaction_id}: {result['amount']}")
        else:
            print(f"No valid amount found for transaction {transaction_id}.")
        print("-" * 50)


if __name__ == "__main__":
    # Provide the path to your CSV file
    csv_file_path = "src/addresses.csv"  # Update with the actual path to your CSV file
    test_transaction_details_from_csv(csv_file_path)
