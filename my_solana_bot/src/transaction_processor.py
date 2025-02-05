from datetime import datetime
import json
import logging
from collections import namedtuple
import base64
from decouple import config

from api_client import APIClient

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
		self.client = APIClient()
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
		Processes a single transaction and extracts relevant details.
		Parameters:
			transaction_details (dict): Raw transaction details.
			account_keys (list): List of account keys for the transaction.
		Returns:
			Transaction: A named tuple representing the processed transaction.
		"""
		# Extract basic transaction details
		signature = transaction_details.get("transaction", {}).get("signatures", [None])[0]
		timestamp = transaction_details.get("blockTime", 0)
		fee = transaction_details.get("meta", {}).get("fee", 0)
		instructions = transaction_details.get("transaction", {}).get("message", {}).get("instructions", [])

		# Initialize transaction variables
		transaction_type = None
		amount = 0
		token = "SOL"

		# Log transaction signature and number of instructions
		logging.info(f"Processing transaction {signature} with {len(instructions)} instructions.")

		# Process each instruction in the transaction
		for instruction in instructions:
			program_id_index = instruction.get("programIdIndex")
			if program_id_index is None or program_id_index >= len(account_keys):
				logging.warning(f"Instruction in transaction {signature} has invalid programIdIndex. Skipping.")
				return None

			# Extract program ID and instruction data
			program_id = account_keys[program_id_index] if program_id_index < len(account_keys) else "Unknown"
			instruction_data = instruction.get("data")

			# Log raw instruction data for debugging purposes
			logging.debug(f"Transaction {signature} - Instruction Data: {instruction_data}, Program ID: {program_id}")

			# Decode the instruction data
			decoded_data = self.decode_instruction(instruction_data, str(program_id), account_keys)

			# Log the result of decoding
			if decoded_data:
				logging.info(f"Transaction {signature} - Decoded Instruction: type={decoded_data.get('type')}, "
							f"amount={decoded_data.get('amount', 0)}, token={decoded_data.get('token', 'SOL')}")
				transaction_type = decoded_data.get("type")
				amount = decoded_data.get("amount", 0)
				token = decoded_data.get("token", "SOL")
				break  # Stop after processing the first relevant instruction
			else:
				logging.warning(f"Transaction {signature} - Failed to decode instruction for program {program_id}.")

		# If no valid instruction was found, log a warning
		if transaction_type is None:
			logging.warning(f"Transaction {signature} - No valid instructions found. Assuming fee-only transaction.")

		# Calculate net amount
		net_amount = amount - fee

		# Use current timestamp if blockTime is missing
		if timestamp is None:
			signature = transaction_details.get("transaction", {}).get("signatures", [None])[0]
			logging.warning(f"Transaction {signature} - Missing blockTime. Using current timestamp as fallback.")
			timestamp = int(datetime.now().timestamp())

		# Log final processed transaction details
		logging.info(f"Processed transaction {signature}: type={transaction_type}, amount={amount}, token={token}, fee={fee}, net_amount={net_amount}")

		# Return the processed transaction as a named tuple
		return Transaction(
			signature=signature,
			timestamp=timestamp,
			type=transaction_type,
			amount=amount,
			token=token,
			price=0,  
			fee=fee,
			net_amount=net_amount
		)

	def detect_token(self, token_account):
		response = self.client.post_request("getAccountInfo", [token_account, {"encoding": "jsonParsed"}])
		if response:
			result = response.get("result", {})
			if result:
				account_data = result.get("value", {}).get("data", {})
				if account_data:
					parsed_info = account_data.get("parsed", {}).get("info", {})
					mint = parsed_info.get("mint")
					if mint:
						token_mappings = {
							"So11111111111111111111111111111111111111112": "SOL",
							"TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": "USDC",
							"Es9vMFrzaCERzHkzWi8kFZrA6t5E3kJ9QH6uQKXz7b7": "USDT",
						}
						return token_mappings.get(mint, "Unknown")
		return "Unknown"

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
				if len(data) >= 9:
					instruction_type = data[0]
					amount = int.from_bytes(data[1:9], byteorder="little") / 10**9  # Convert lamports to SOL

					if instruction_type == 3:  # Transfer
						token_account_index = data[9]
						token_account = account_keys[token_account_index] if token_account_index < len(account_keys) else "Unknown"
						token = self.detect_token(token_account)

						decoded_data = {
							"type": "transfer",
							"amount": amount,
							"token": token,
							"token_account": token_account,
						}
					elif instruction_type == 7:  # CloseAccount
						logging.info(f"CloseAccount instruction detected for {program_id}.")
					else:
						logging.warning(f"Unsupported instruction type {instruction_type} for Token Program.")

			# Handle System Program instructions
			elif program_id == config("SYSTEM_PROGRAM_ID") or program_id == "11111111111111111111111111111111":
				if len(data) >= 9:
					instruction_type = data[0]

					if instruction_type == 3:  # Transfer
						amount = int.from_bytes(data[1:9], byteorder="little") / 10**9
						decoded_data = {"type": "transfer", "amount": amount, "token": "SOL"}
					elif instruction_type == 2:  # CreateAccount
						logging.info(f"CreateAccount instruction detected for {program_id}.")
					elif instruction_type == 1:  # Assign
						logging.info(f"Assign instruction detected for {program_id}.")
					else:
						logging.warning(f"Unsupported instruction type {instruction_type} for System Program.")

			# Handle Associated Token Program
			elif program_id == "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL":
				logging.info(f"Associated Token Program detected. Skipping instruction decoding.")

			# Handle Compute Budget Program
			elif program_id == "ComputeBudget111111111111111111111111111111":
				if len(data) >= 4:
					instruction_type = data[0]
					if instruction_type == 1:  # Example instruction type
						budget_limit = int.from_bytes(data[1:5], byteorder="little")
						decoded_data = {"type": "set_budget", "limit": budget_limit}
					else:
						logging.warning(f"Unsupported instruction type {instruction_type} for Compute Budget Program.")
				else:
					logging.warning("Invalid instruction format for Compute Budget Program.")

			# Handle Serum DEX Program
			elif program_id == "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8":
				logging.info("Serum DEX program detected. Skipping instruction decoding.")

			# Handle Jupiter Swap Program
			elif program_id == "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4":
				logging.info("Jupiter Swap program detected. Skipping instruction decoding.")

			# Handle Unknown Programs
			else:
				logging.warning(f"Unsupported program ID: {program_id}")

			# Log detailed information about the decoded data
			if decoded_data:
				logging.info(f"Successfully decoded instruction for program {program_id}: {decoded_data}")
			else:
				logging.warning(f"No valid data decoded for program {program_id}.")

			return decoded_data if decoded_data else None

		except Exception as e:
			logging.error(f"Error decoding instruction: {e} for program {program_id}")
			import traceback
			traceback.print_exc()
			return None
