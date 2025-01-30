import requests
import logging
import time
from decouple import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class APIClient:
    def __init__(self):
        # Load RPC URLs from environment variable
        self.rpc_urls = config("HELIUS_RPC_URL", "").split(",")
        self.rpc_urls = [url.strip().strip('"') for url in self.rpc_urls if url.strip()]
        
        if not self.rpc_urls:
            raise ValueError("No valid RPC URLs found in the environment variable.")
        
        self.current_rpc_url = self.rpc_urls[0]  # Start with the first URL
        self.max_retries = 3  # Maximum number of retries per request
        self.timeout = 10  # Request timeout in seconds

    def switch_rpc_url(self):
        """Switch to the next RPC URL in the list."""
        current_index = self.rpc_urls.index(self.current_rpc_url)
        next_index = (current_index + 1) % len(self.rpc_urls)
        self.current_rpc_url = self.rpc_urls[next_index]
        logging.info(f"Switched to RPC URL: {self.current_rpc_url}")

    def post_request(self, method, params):
        """
        Send a POST request to the current RPC URL with retry logic.

        Args:
            method (str): The RPC method to call.
            params (list): The parameters for the RPC method.

        Returns:
            dict: The JSON response from the RPC endpoint, or None if the request fails.
        """
        headers = {"Content-Type": "application/json"}
        data = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

        for attempt in range(self.max_retries):
            try:
                # Send the request to the current RPC URL
                response = requests.post(self.current_rpc_url, headers=headers, json=data, timeout=self.timeout)
                
                # Check if the response is successful
                if response.status_code == 200:
                    return response.json()
                
                # Handle rate limiting
                elif response.status_code == 429:  # Rate-limiting
                    logging.warning(f"Rate limit exceeded (attempt {attempt + 1}/{self.max_retries}). Retrying...")
                
                else:
                    # Log unexpected errors
                    logging.error(f"Unexpected error: {response.status_code}, {response.text}")
            
            except requests.exceptions.RequestException as e:
                logging.error(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")

            # Switch to the next RPC URL and retry
            self.switch_rpc_url()
            time.sleep(2 ** attempt)  # Exponential backoff

        logging.error("Exceeded retry limit for this request.")
        return None

    def get_token_accounts_by_owner(self, wallet_address):
        """Fetch token accounts for a given wallet address."""
        params = [
            wallet_address,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},  
            {"encoding": "jsonParsed"}
        ]
        result = self.post_request("getTokenAccountsByOwner", params)
        if result and 'result' in result:
            return [account['pubkey'] for account in result['result']['value']]
        logging.error("Failed to fetch token accounts.")
        return None

    def check_rpc_url(self):
        """
        Check if the current RPC URL is responding.

        Returns:
            bool: True if the RPC URL is working, False otherwise.
        """
        try:
            # Prepare the health check payload
            payload = {"jsonrpc": "2.0", "id": 1, "method": "getHealth"}
            
            # Send a POST request to the RPC URL with a timeout
            response = requests.post(self.current_rpc_url, json=payload, timeout=5)
            
            # Check if the response is successful
            if response.status_code == 200 and response.json().get("result") == "ok":
                logging.info(f"RPC URL {self.current_rpc_url} is working fine.")
                return True
            else:
                logging.warning(f"RPC URL {self.current_rpc_url} responded with status {response.status_code}.")
                return False
        except requests.exceptions.RequestException as e:
            logging.error(f"Error with RPC URL {self.current_rpc_url}: {str(e)}")
            return False
