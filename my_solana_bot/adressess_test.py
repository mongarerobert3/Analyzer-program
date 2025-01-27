import csv
from src.api_client import APIClient

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
				with open(csv_file, mode='r') as file:
						csv_reader = csv.reader(file)
						for row in csv_reader:
								# Skip the header and empty rows
								if row and row[0] != "id":
										wallet_addresses.append(row[0])
				print(f"Loaded {len(wallet_addresses)} wallet addresses from {csv_file}.")
		except Exception as e:
				print(f"Error reading CSV file: {e}")
		return wallet_addresses


def test_wallet_addresses(api_client, wallet_addresses, working_address=None):
    """
    Test the wallet addresses by fetching token accounts for each one.
    Skip addresses without token accounts to speed up the process.

    Parameters:
            api_client (APIClient): The instance of the API client.
            wallet_addresses (list): A list of wallet addresses to test.
            working_address (str, optional): A known working address to find associated addresses.
    """
    found_addresses = []  # Store addresses with token accounts
    
    # If a working address is provided, try to find associated addresses
    if working_address:
        print(f"Using known working address: {working_address}")
        associated_addresses = api_client.get_associated_wallets_by_owner(working_address)
        print(f"Found {len(associated_addresses)} associated addresses.")
        wallet_addresses.extend(associated_addresses)  # Add associated addresses to the list to test
        
    # Now proceed with testing all addresses
    for address in wallet_addresses:
        print(f"Testing wallet address: {address}")
        
        token_accounts = None  # Initialize the variable outside the try block
        
        try:
            # Fetch token accounts for the address
            token_accounts = api_client.get_token_accounts_by_owner(address)
            
            # If the address has token accounts, print the result and continue
            if token_accounts and "value" in token_accounts and len(token_accounts["value"]) > 0:
                print(f"  - Found {len(token_accounts['value'])} token accounts for {address}.")
                found_addresses.append(address)  # Store the address that has token accounts
            else:
                print(f"  - No token accounts found for {address}. Skipping.")
                
        except Exception as e:
            print(f"Error fetching token accounts for {address}: {e}")
        
        # If token accounts are None or no token accounts found, print the raw response (if available)
        if token_accounts is None or "value" not in token_accounts or len(token_accounts["value"]) == 0:
            print(f"  - Raw response: {api_client.last_response if hasattr(api_client, 'last_response') else 'No raw response available.'}")
    
    # Return the list of addresses that have token accounts
    return found_addresses


if __name__ == "__main__":
		# Define the CSV file containing the wallet addresses
		csv_file = "src/addresses.csv"  # Update with the actual path to your CSV file
		
		# Initialize the API client
		api_client = APIClient(use_helius=True)  # Set to False if you want to use Solana RPC instead of Helius
		
		# Load wallet addresses from CSV
		wallet_addresses = load_wallet_addresses(csv_file)
		
		if wallet_addresses:
				# Test the loaded wallet addresses
				test_wallet_addresses(api_client, wallet_addresses)
