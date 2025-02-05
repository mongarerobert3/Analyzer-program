from datetime import datetime
import logging
from api_client import APIClient
from transaction_processor import TransactionProcessor
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from time import sleep
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TransactionFetcher:
    def __init__(self, batch_size=2, max_workers=5):
        """
        Initializes the TransactionFetcher with an API client, batch size, and thread pool for concurrency.
        """
        self.client = APIClient()
        self.batch_size = batch_size
        self.processor = TransactionProcessor()
        self.max_workers = max_workers  # Number of threads for concurrent processing

    def fetch_transaction_history(self, wallet_address, max_transactions=50):
        """
        Fetches the transaction history for a given wallet address, limited to the last `max_transactions`.
        Parameters:
            wallet_address (str): The wallet address to fetch transactions for.
            max_transactions (int): The maximum number of transactions to fetch.
        Returns:
            list: A list of fetched transactions, up to `max_transactions`.
        """
        all_transactions = []
        before_signature = None
        max_iterations = max(1, max_transactions // self.batch_size + 1)  # Dynamically calculate iterations
        iteration = 0
        duplicate_count = 0  # Counter for duplicate transactions
        logging.info(f"Fetching transaction history for wallet address: {wallet_address}")

        while iteration < max_iterations and len(all_transactions) < max_transactions:
            iteration += 1
            logging.info(f"Iteration {iteration}")
            params = [wallet_address, {"limit": self.batch_size}]
            if before_signature:
                params[1]["before"] = before_signature

            try:
                result = self.client.post_request("getSignaturesForAddress", params)
                if not result or "result" not in result:
                    logging.error(f"Error fetching transactions for {wallet_address}. No result found.")
                    break

                transactions = result["result"]
                if not transactions:
                    logging.info(f"No more transactions found for {wallet_address}.")
                    break

                # Check for duplicate transactions
                if all_transactions and transactions[0]["signature"] == all_transactions[-1]["signature"]:
                    duplicate_count += 1
                    if duplicate_count >= 3:  # Stop after 3 duplicate batches
                        logging.warning(f"Detected {duplicate_count} duplicate batches. Stopping fetch.")
                        break
                else:
                    duplicate_count = 0  # Reset duplicate counter

                logging.info(f"Fetched transactions: {[tx['signature'] for tx in transactions]}")
                all_transactions.extend(transactions)
                logging.info(f"Fetched {len(transactions)} transactions for {wallet_address}.")

                if len(transactions) < self.batch_size:
                    logging.info(f"Fetched fewer than batch size ({self.batch_size}) for {wallet_address}, stopping fetch.")
                    break

                if len(all_transactions) >= max_transactions:
                    logging.info(f"Reached the maximum number of transactions ({max_transactions}). Stopping fetch.")
                    break

                before_signature = transactions[-1]["signature"]

            except Exception as e:
                logging.error(f"Error fetching transactions for {wallet_address}: {e}")
                break

        # Trim the list to the maximum number of transactions
        if len(all_transactions) > max_transactions:
            all_transactions = all_transactions[:max_transactions]

        logging.info(f"Total {len(all_transactions)} transactions fetched for {wallet_address}.")
        return all_transactions

    def process_transactions(self, wallet_address, timeframe='overall'):
        """
        Processes transactions for a given wallet address within a specified timeframe.
        Parameters:
            wallet_address (str): The wallet address to process transactions for.
            timeframe (str): The timeframe to filter by ('1', '3', '6', '12', or 'overall').
        Returns:
            list: A list of processed transactions within the specified timeframe.
        """
        logging.info(f"Processing transactions for wallet address: {wallet_address}")
        transaction_signatures = self.fetch_transaction_history(wallet_address)

        if not transaction_signatures:
            logging.info(f"No transactions found for {wallet_address}.")
            return []

        def fetch_and_process(tx_signature_data):
            tx_signature = tx_signature_data.get("signature")
            if not tx_signature:
                logging.warning("Transaction signature missing in fetched data.")
                return None

            tx_details = self.fetch_transaction_details(tx_signature)
            if tx_details:
                processed_tx = self.processor.process_transaction(tx_details, [wallet_address])
                if processed_tx and self.processor.is_within_timeframe(processed_tx.timestamp, timeframe):
                    return processed_tx
            logging.warning(f"Could not fetch details for transaction: {tx_signature}")
            return None

        # Use ThreadPoolExecutor for concurrent processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(fetch_and_process, transaction_signatures))

        # Filter out None values
        processed_transactions = [tx for tx in results if tx]
        logging.info(f"Processed {len(processed_transactions)} valid transactions for {wallet_address}.")
        return processed_transactions

    @lru_cache(maxsize=128)
    def fetch_transaction_details(self, transaction_id, retries=3, backoff_factor=1):
        """
        Fetches detailed information about a specific transaction with retry logic.
        Parameters:
            transaction_id (str): The ID of the transaction to fetch details for.
            retries (int): Number of retry attempts.
            backoff_factor (float): Factor to increase delay between retries.
        Returns:
            dict or None: The details of the transaction if successful, None otherwise.
        """
        attempt = 0
        while attempt < retries:
            try:
                result = self.client.post_request("getTransaction", [transaction_id, {"maxSupportedTransactionVersion": 0}])
                logging.debug(f"Raw API response for {transaction_id}: {result}")

                if not result or "result" not in result:
                    logging.warning(f"Transaction {transaction_id} returned an invalid response: {result}")
                    raise ValueError("Invalid API response")

                logging.info(f"Successfully fetched transaction details for {transaction_id}.")
                return result["result"]

            except Exception as e:
                attempt += 1
                logging.error(f"Attempt {attempt}/{retries} failed for transaction {transaction_id}: {e}")
                if attempt < retries:
                    sleep_time = backoff_factor * (2 ** (attempt - 1)) + random.uniform(0, 0.5)  # Exponential backoff with jitter
                    logging.info(f"Retrying in {sleep_time:.2f} seconds...")
                    sleep(sleep_time)
                else:
                    logging.error(f"Failed to fetch details for transaction {transaction_id} after {retries} attempts.")
                    return None


    @lru_cache(maxsize=128)
    def fetch_wallet_balance(self, address):
        """
        Fetches the balance of a specified wallet address in SOL with caching.
        Parameters:
            address (str): The wallet address to fetch the balance for.
        Returns:
            float: The balance in SOL.
        """
        try:
            result = self.client.post_request("getBalance", [address])
            if result and "result" in result:
                sol_balance = result["result"]["value"] / 10**9  # Convert lamports to SOL
                logging.info(f"Fetched wallet balance for {address}: {sol_balance} SOL.")
                return sol_balance
            else:
                logging.error(f"Error fetching balance for {address}.")
                return 0.0
        except Exception as e:
            logging.error(f"Error fetching wallet balance for {address}: {e}")
            return 0.0