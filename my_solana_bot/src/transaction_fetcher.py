from datetime import datetime
import logging
from api_client import APIClient
from transaction_processor import TransactionProcessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TransactionFetcher:
    def __init__(self, batch_size=2):
        self.client = APIClient()
        self.batch_size = batch_size
        self.processor = TransactionProcessor()

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
        max_iterations = 10  # Maximum number of iterations to prevent infinite loops
        iteration = 0
        duplicate_count = 0  # Counter for duplicate transactions
        logging.info(f"Fetching transaction history for wallet address: {wallet_address}")

        while iteration < max_iterations and len(all_transactions) < max_transactions:
            iteration += 1
            logging.info(f"Iteration {iteration}")

            # Prepare parameters for the API request
            params = [wallet_address, {"limit": self.batch_size}]
            if before_signature:
                params[1]["before"] = before_signature

            # Fetch transactions
            try:
                result = self.client.post_request("getSignaturesForAddress", params)
                if not result or "result" not in result:
                    logging.error(f"Error fetching transactions for {wallet_address}. No result found.")
                    break
                
                transactions = result["result"]
                if not transactions:
                    logging.info(f"No more transactions found for {wallet_address}.")
                    break  # No more transactions to fetch

                # Check for duplicate transactions
                if all_transactions and transactions[0]["signature"] == all_transactions[-1]["signature"]:
                    duplicate_count += 1
                    if duplicate_count >= 3:  # Stop after 3 duplicate batches
                        logging.warning(f"Detected {duplicate_count} duplicate batches. Stopping fetch.")
                        break
                else:
                    duplicate_count = 0  # Reset duplicate counter

                # Log the before_signature and fetched transactions
                logging.info(f"Before signature: {before_signature}")
                logging.info(f"Fetched transactions: {[tx['signature'] for tx in transactions]}")

                # Add fetched transactions to the list
                all_transactions.extend(transactions)
                logging.info(f"Fetched {len(transactions)} transactions for {wallet_address}.")

                # Update before_signature with the last transaction's signature
                before_signature = transactions[-1]["signature"]

                # If we fetched fewer transactions than the batch size, we've reached the end
                if len(transactions) < self.batch_size:
                    logging.info(f"Fetched fewer than batch size ({self.batch_size}) for {wallet_address}, stopping fetch.")
                    break

                # Stop if we've reached the maximum number of transactions
                if len(all_transactions) >= max_transactions:
                    logging.info(f"Reached the maximum number of transactions ({max_transactions}). Stopping fetch.")
                    break

            except Exception as e:
                logging.error(f"Error fetching transactions for {wallet_address}: {e}")
                break

        # Trim the list to the maximum number of transactions
        if len(all_transactions) > max_transactions:
            all_transactions = all_transactions[:max_transactions]

        logging.info(f"Total {len(all_transactions)} transactions fetched for {wallet_address}.")
        return all_transactions
    
    def process_transactions(self, wallet_address, timeframe='overall'):
        logging.info(f"Processing transactions for wallet address: {wallet_address}")
        transaction_signatures = self.fetch_transaction_history(wallet_address)  # Get signatures

        if not transaction_signatures:  # Handle no transactions case
            logging.info(f"No transactions found for {wallet_address}.")
            return []

        processed_transactions = []
        for tx_signature_data in transaction_signatures: # Iterate over transaction signatures
            tx_signature = tx_signature_data.get("signature") # Extract signature safely
            if not tx_signature:
                logging.warning("Transaction signature missing in fetched data.")
                continue

            tx_details = self.fetch_transaction_details(tx_signature) # Fetch details for each transaction signature

            if tx_details:  # Only process if details were successfully fetched
                processed_tx = self.processor.process_transaction(tx_details, [wallet_address]) # Pass wallet_address for now
                if processed_tx and self.processor.is_within_timeframe(processed_tx.timestamp, timeframe):
                    processed_transactions.append(processed_tx)
            else:
                logging.warning(f"Could not fetch details for transaction: {tx_signature}")

        logging.info(f"Processed {len(processed_transactions)} valid transactions for {wallet_address}.")
        return processed_transactions

    def fetch_transaction_details(self, transaction_id):
        """
        Fetches detailed information about a specific transaction.

        Parameters:
            transaction_id (str): The ID of the transaction to fetch details for.

        Returns:
            dict or None: The details of the transaction if successful, None otherwise.
        """
        try:
            result = self.client.post_request("getTransaction", [transaction_id, {"encoding": "jsonParsed"}])
            if not result or "result" not in result:
                logging.error(f"Error fetching details for transaction {transaction_id}.")
                return None
            logging.info(f"Transaction details fetched for {transaction_id}.")
            return result["result"]
        except Exception as e:
            logging.error(f"Error fetching transaction details for {transaction_id}: {e}")
            return None

    def fetch_wallet_balance(self, address):
        """
        Fetches the balance of a specified wallet address in SOL.

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
