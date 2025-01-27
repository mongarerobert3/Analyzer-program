from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TransactionProcessor:
    def __init__(self):
        pass

    @staticmethod
    def filter_transactions(transactions):
        """
        Filters transactions to include only buy and sell types.

        Parameters:
            transactions (list): A list of transaction dictionaries.

        Returns:
            list: A list of filtered buy/sell transactions.
        """
        try:
            buy_sell_transactions = [t for t in transactions if t.get("type") in ["buy", "sell"]]
            logging.info(f"Filtered {len(buy_sell_transactions)} buy/sell transactions.")
            return buy_sell_transactions
        except Exception as e:
            logging.error(f"Error filtering transactions: {e}")
            return []

    @staticmethod
    def process_transaction(transaction):
        """
        Processes a single transaction, calculating important details like value, type, and fees.

        Parameters:
            transaction (dict): The transaction dictionary to process.

        Returns:
            dict: A dictionary with processed transaction data, including transaction type, amount, fees, and tokens.
        """
        processed_tx = {}

        try:
            # Extract basic fields
            signature = transaction.get("signature")
            amount = transaction.get("amount", 0)  # The transaction amount
            transaction_type = transaction.get("type")  # Can be 'buy', 'sell', or other
            fees = transaction.get("fee", 0)  # Transaction fee, default to 0 if not available
            timestamp = transaction.get("timestamp")  # Time of the transaction (if available)

            # Convert amount if needed (e.g., lamports to SOL if applicable)
            if isinstance(amount, dict) and "lamports" in amount:
                amount_in_sol = amount["lamports"] / 10**9  # Convert lamports to SOL
            else:
                amount_in_sol = amount  # If it's already in SOL, use it directly

            # Process based on transaction type
            if transaction_type == "buy":
                processed_tx["type"] = "buy"
                processed_tx["amount"] = amount_in_sol
                processed_tx["fees"] = fees
                processed_tx["net_amount"] = amount_in_sol - fees  # Net amount after fees
            elif transaction_type == "sell":
                processed_tx["type"] = "sell"
                processed_tx["amount"] = amount_in_sol
                processed_tx["fees"] = fees
                processed_tx["net_amount"] = amount_in_sol - fees  # Net amount after fees
            else:
                processed_tx["type"] = "other"
                processed_tx["amount"] = amount_in_sol

            # Add signature for tracking
            processed_tx["id"] = signature

            # Add timestamp if available
            if timestamp:
                processed_tx["timestamp"] = timestamp

            logging.info(f"Processed transaction {signature}: {processed_tx}")

        except Exception as e:
            logging.error(f"Error processing transaction: {e}")
            return {}

        return processed_tx

    @staticmethod
    def is_buy_transaction(transaction):
        """
        Checks if the transaction is of type 'buy'.
        
        Parameters:
            transaction (dict): The transaction dictionary to check.

        Returns:
            bool: True if the transaction type is 'buy', False otherwise.
        """
        return transaction.get("type") == "buy"

    @staticmethod
    def is_sell_transaction(transaction):
        """
        Checks if the transaction is of type 'sell'.
        
        Parameters:
            transaction (dict): The transaction dictionary to check.

        Returns:
            bool: True if the transaction type is 'sell', False otherwise.
        """
        return transaction.get("type") == "sell"

    @staticmethod
    def is_within_timeframe(tx_timestamp, timeframe):
        """
        Checks if a transaction is within the specified timeframe.

        Parameters:
            tx_timestamp (int): The timestamp of the transaction.
            timeframe (str): The timeframe to filter by ('1', '3', '6', '12', or 'overall').

        Returns:
            bool: True if the transaction is within the timeframe, False otherwise.
        """
        try:
            if not tx_timestamp:
                return False

            current_time = datetime.now()
            delta = current_time - datetime.fromtimestamp(tx_timestamp)

            if timeframe == '1':
                return delta.days <= 30
            elif timeframe == '3':
                return delta.days <= 90
            elif timeframe == '6':
                return delta.days <= 180
            elif timeframe == '12':
                return delta.days <= 365
            else:
                return True  # No filtering if 'overall'

        except Exception as e:
            logging.error(f"Error checking timeframe: {e}")
            return False