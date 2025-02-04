from datetime import datetime
import json
import logging
from collections import namedtuple
import base64
from decouple import config

# Define Transaction namedtuple (outside the class)
Transaction = namedtuple("Transaction", ["signature", "timestamp", "type", "amount", "token", "price", "fee", "net_amount"])

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def safe_base64_decode(data):
    """Safely decodes a base64-encoded string, adding padding if necessary."""
    try:
        missing_padding = len(data) % 4
        if missing_padding:
            data += "=" * (4 - missing_padding)
        return base64.b64decode(data)
    except Exception as e:
        logging.error(f"Error decoding base64 instruction data: {e}")
        return None
    
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
        signature = transaction_details.get("transaction", {}).get("signatures", [None])[0]
        timestamp = transaction_details.get("blockTime", 0)

        fee = transaction_details.get("meta", {}).get("fee", 0)

        instructions = transaction_details.get("transaction", {}).get("message", {}).get("instructions", [])
        transaction_type = None
        amount = 0
        token = "SOL" 

        for instruction in instructions:
            program_id_index = instruction.get("programIdIndex")
            if program_id_index is None:
                continue

            program_id = account_keys[program_id_index]
            instruction_data = instruction.get("data")

            decoded_data = self.decode_instruction(instruction_data, str(program_id), account_keys)  
            if decoded_data:
                transaction_type = decoded_data.get("type")
                amount = decoded_data.get("amount", 0)
                token = decoded_data.get("token", "SOL")
                break  # Stop after processing the first relevant instruction (for now)

        net_amount = amount - fee

        logging.info(f"Processed transaction {signature}: type={transaction_type}, amount={amount}, token={token}, fee={fee}, net_amount={net_amount}")
        return Transaction(signature=signature, timestamp=timestamp, type=transaction_type, 
                        amount=amount, token=token, price=0, fee=fee, net_amount=net_amount)


    def decode_instruction(self, instruction_data, program_id, account_keys):
        """
        Decodes the instruction data to extract transaction details.
        Parameters:
            instruction_data (str): Base64-encoded instruction data.
            program_id (str): The program ID associated with the instruction.
            account_keys (list): List of account keys for the transaction.
        Returns:
            dict: A dictionary containing decoded transaction details.
        """
        try:
            if not instruction_data:
                logging.info("Instruction data is empty or None.")
                return None

            # Decode base64 data
            try:
                data = safe_base64_decode(instruction_data)
                logging.info(f"Decoded Instruction Data (hex): {data.hex()}")
            except Exception as e:
                logging.error(f"Error decoding base64 instruction data: {e}")
                return None

            decoded_data = {}

            # Handle Token Program instructions
            if program_id == config("TOKEN_PROGRAM_ID"):  
                if len(data) >= 9:  # At least instruction type + amount
                    instruction_type = data[0]
                    amount = int.from_bytes(data[1:9], byteorder='little') / 10**9  # Convert lamports to SOL

                    if instruction_type == 3:  # Transfer instruction
                        token_account_index = int.from_bytes(data[9:10], byteorder='little')
                        token_account = account_keys[token_account_index] if token_account_index < len(account_keys) else "Unknown"
                        decoded_data = {
                            "type": "transfer",
                            "amount": amount,
                            "token": "SOL",  # Default token; replace with actual token detection logic
                            "token_account": token_account
                        }
                    else:
                        logging.warning(f"Unsupported instruction type {instruction_type} for Token Program.")
            elif program_id == config("SYSTEM_PROGRAM_ID"): 
                # Handle system-level instructions (e.g., transfers)
                if len(data) >= 1:  # At least instruction type
                    instruction_type = data[0]

                    if instruction_type == 2:  # CreateAccount instruction
                        decoded_data = {"type": "create_account"}
                    elif instruction_type == 3:  # Transfer instruction
                        if len(data) >= 9:
                            amount = int.from_bytes(data[1:9], byteorder='little') / 10**9
                            decoded_data = {"type": "transfer", "amount": amount, "token": "SOL"}
                        else:
                            logging.warning("Invalid transfer instruction format for System Program.")
                    else:
                        logging.warning(f"Unsupported instruction type {instruction_type} for System Program.")
            # Handle Serum DEX instructions
            elif program_id == "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8":  # Serum DEX Program
                logging.warning(f"Serum DEX program detected. Skipping instruction decoding for now.")
                # Add decoding logic for Serum DEX instructions here

            # Handle Jupiter Swap instructions
            elif program_id == "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4":  # Jupiter Swap Program
                logging.warning(f"Jupiter Swap program detected. Skipping instruction decoding for now.")
                # Add decoding logic for Jupiter Swap instructions here
            else:
                logging.warning(f"Unsupported program ID: {program_id}")

            return decoded_data if decoded_data else None

        except Exception as e:
            logging.error(f"Error decoding instruction: {e} for program {program_id}")
            import traceback
            traceback.print_exc()
            return None


    @staticmethod
    def is_buy_transaction(transaction):
        """
        Checks if the transaction is of type 'buy'.
        
        Parameters:
            transaction (Transaction): The transaction namedtuple to check.

        Returns:
            bool: True if the transaction type is 'buy', False otherwise.
        """
        return transaction.type == "buy"

    @staticmethod
    def is_sell_transaction(transaction):
        """
        Checks if the transaction is of type 'sell'.
        
        Parameters:
            transaction (Transaction): The transaction namedtuple to check.

        Returns:
            bool: True if the transaction type is 'sell', False otherwise.
        """
        return transaction.type == "sell"

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