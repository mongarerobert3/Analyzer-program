import base64
from datetime import datetime
import logging
from collections import namedtuple  # Import namedtuple
from decouple import config

# Define Transaction namedtuple (outside the class)
Transaction = namedtuple("Transaction", ["signature", "timestamp", "type", "amount", "token", "price", "fee", "net_amount"])

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

    def process_transaction(self, transaction_details, account_keys):  
        """
        Processes a single transaction, calculating important details like value, type, and fees.

        Parameters:
            transaction (dict): The transaction dictionary to process.

        Returns:
            dict: A dictionary with processed transaction data, including transaction type, amount, fees, and tokens.
        """
        try:
            signature = transaction_details.get("transaction", {}).get("signatures", [None])[0]
            if not signature:
                logging.warning("Transaction details missing signature.")
                return None

            processed_tx = {"id": signature}  # Start with the signature

            timestamp = transaction_details.get('blockTime')
            if timestamp:
                processed_tx["timestamp"] = timestamp

            # Process instructions (using account_keys)
            instructions = transaction_details.get("transaction", {}).get("message", {}).get("instructions", [])
            for instruction in instructions:
                program_id_index = instruction.get("programIdIndex")
                if program_id_index is None:
                    continue

                program_id = transaction_details["transaction"]["message"]["accountKeys"][program_id_index]
                instruction_data = instruction.get("data")

                decoded_data = self.decode_instruction(instruction_data, str(program_id))
                if decoded_data:
                    processed_tx.update(decoded_data)

                    # Improved Buy/Sell Logic (using account_keys)
                    if decoded_data.get("type") == "transfer":
                        if decoded_data.get("token") == "SOL":
                            if any(account in account_keys for account in decoded_data.get("destination", [])):
                                processed_tx["type"] = "buy"
                            elif any(account in account_keys for account in decoded_data.get("source", [])):
                                processed_tx["type"] = "sell"

            # Extract fee (if available)
            fee = transaction_details.get("meta", {}).get("fee", 0)
            processed_tx["fee"] = fee

            # Calculate net amount (after decoding)
            amount = processed_tx.get("amount", 0)
            processed_tx["net_amount"] = amount - fee

            logging.info(f"Processed transaction {signature}: {processed_tx}")
            return Transaction(signature=signature, timestamp=timestamp, type=processed_tx.get("type"), 
                               amount=amount, token=processed_tx.get("token"), price=processed_tx.get("price"),
                               fee=fee, net_amount=processed_tx["net_amount"])  # Return a Transaction namedtuple

        except Exception as e:
            logging.error(f"Error processing transaction: {e}")
            import traceback
            traceback.print_exc()
            return None

    def decode_instruction(self, instruction_data, program_id):
        try:
            if not instruction_data:
                return None

            decoded_data = {}  # Initialize an empty dictionary

            # 1. Decode the instruction data from base64
            try:
                # Ensure proper base64 decoding by handling padding
                padding = len(instruction_data) % 4
                if padding != 0:
                    instruction_data += "=" * (4 - padding)  # Add necessary padding
                data = base64.b64decode(instruction_data)
            except Exception as e:
                logging.error(f"Error decoding base64 instruction data: {e}")
                return None

            # 2. Handle different program IDs (replace with your actual program IDs)
            if str(program_id) == config("TOKEN_PROGRAM_ID"):
                decoded_data = self._decode_token_instruction(data)
            else:
                logging.debug(f"Unknown program ID: {program_id}")
                return None

            return decoded_data

        except Exception as e:
            logging.error(f"Error decoding instruction: {e} for program {program_id}")
            import traceback
            traceback.print_exc()
            return None
        
    def _decode_token_instruction(self, data):
        try:
            # Token Instruction Layout (Example: Adapt to your version)
            # Common instruction types include:
            # - 1: Initialize Account
            # - 2: Transfer
            # - 3: Approve
            # You can add others depending on the token program version.
            
            # First byte is the instruction type (based on the Solana Token Program)
            instruction_type = data[0]
            
            # Decode based on the instruction type
            if instruction_type == 3:  # Transfer Instruction
                # Assuming the layout: [instruction_type (1 byte), amount (8 bytes), destination (32 bytes)]
                amount = int.from_bytes(data[1:9], byteorder='little')  # Decode amount (8 bytes)
                destination = data[9:41].decode('utf-8')  # Decode destination address (32 bytes)
                return {"type": "transfer", "amount": amount, "destination": destination, "token": "SOL"}  
            
            elif instruction_type == 2:  # Approve Instruction
                # Assuming the layout: [instruction_type (1 byte), amount (8 bytes), delegate (32 bytes)]
                amount = int.from_bytes(data[1:9], byteorder='little')  # Decode amount (8 bytes)
                delegate = data[9:41].decode('utf-8')  # Decode delegate address (32 bytes)
                return {"type": "approve", "amount": amount, "delegate": delegate, "token": "SOL"} 

            elif instruction_type == 1:  # Initialize Account Instruction
                # Example layout: [instruction_type (1 byte), owner (32 bytes)]
                owner = data[1:33].decode('utf-8')  # Decode the owner address (32 bytes)
                return {"type": "initialize_account", "owner": owner, "token": "SOL"} 

            else:
                logging.debug(f"Unknown instruction type: {instruction_type}")
                return {"type": "unknown_token_instruction"}

        except Exception as e:
            logging.error(f"Error decoding token instruction: {e}")
            return None
        
    @staticmethod
    def is_buy_transaction(transaction):
        """
        Checks if the transaction is of type 'buy'.
        
        Parameters:
            transaction (dict): The transaction dictionary to check.

        Returns:
            bool: True if the transaction type is 'buy', False otherwise.
        """
        return transaction.type == "buy"  # Access namedtuple attribute

    @staticmethod
    def is_sell_transaction(transaction):
        """
        Checks if the transaction is of type 'sell'.
        
        Parameters:
            transaction (dict): The transaction dictionary to check.

        Returns:
            bool: True if the transaction type is 'sell', False otherwise.
        """
        return transaction.type == "sell"  # Access namedtuple attribute

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