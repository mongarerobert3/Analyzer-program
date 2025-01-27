from api_client import APIClient  # Assuming your class is in api_client.py

def test_api():
    # Create an instance of the APIClient with Helius as the API
    api_client = APIClient(use_helius=True)

    # Define the API method and parameters to test
    method = "getAccountInfo"  # Solana RPC method
    params = ['vines1vzrYbzLMRdu58ou5XTby4qAqVRLmqo36NKPTg'] # Sample Wallet address from documentation

    # Send the request
    response = api_client.post_request(method, params)

    # Print the response
    if response:
        print("API response received:")
        print(response)
    else:
        print("No response or failed request.")

def test_get_wallet_addresses():
    # Initialize the API client
    api_client = APIClient(use_helius=False)  # Set to True if using Helius RPC

    # Fetch all token accounts
    print("Fetching all token accounts...")
    all_token_accounts = api_client.get_token_accounts()
    if all_token_accounts:
        # Extract wallet addresses from token accounts
        wallet_addresses = [
            account["pubkey"] for account in all_token_accounts
        ]
        print(f"Wallet Addresses ({len(wallet_addresses)}):")
        print(wallet_addresses)
    else:
        print("Failed to fetch token accounts.")
 
if __name__ == "__main__":
    #test_api()
    test_get_wallet_addresses()
