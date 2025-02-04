import requests
import logging
from decouple import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Helius API configuration
HELIUS_API_KEY = config("HELIUS_API_KEY")
RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# Transaction signature to fetch
TRANSACTION_SIGNATURE = "5wsYnreTLwZgB9G6DfSssgngJyujGm8npzsB4rAhagfyrSpSZCaH2MDaBH1kfUk2MsLRWUz75n7cktjRBHkHqV8Z"

def fetch_transaction_details(signature):
    """
    Fetches detailed information about a specific Solana transaction using Helius RPC.
    Parameters:
        signature (str): The transaction signature to fetch details for.
    Returns:
        dict: The transaction details if successful, None otherwise.
    """
    headers = {"Content-Type": "application/json"}
    data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [signature, {"encoding": "jsonParsed"}]
    }

    try:
        response = requests.post(RPC_URL, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if "result" in result and result["result"]:
                logging.info(f"Successfully fetched details for transaction {signature}.")
                return result["result"]
            else:
                logging.error(f"Transaction {signature} not found or no result returned.")
                return None
        else:
            logging.error(f"Failed to fetch transaction details. Status code: {response.status_code}, Response: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching transaction details: {e}")
        return None

if __name__ == "__main__":
    transaction_signature = TRANSACTION_SIGNATURE
    transaction_details = fetch_transaction_details(transaction_signature)

    if transaction_details:
        logging.info("Transaction Details:")
        logging.info(transaction_details)
    else:
        logging.error(f"Could not fetch details for transaction {transaction_signature}.")