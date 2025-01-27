from pycoingecko import CoinGeckoAPI

class PriceFetcher:
    def __init__(self):
        self.cg = CoinGeckoAPI()

    def get_sol_to_usd_price(self):
        """
        Fetches the current price of SOL in USD.

        Returns:
            float: The current price of SOL in USD.
        """
        prices = self.cg.get_price(ids='solana', vs_currencies='usd')
        
        if 'solana' in prices and 'usd' in prices['solana']:
            return prices['solana']['usd']
        
        print("Error fetching SOL price in USD")
        return 0.0

    def convert_to_usd(self, amount_sol):
        """
        Converts an amount in SOL to USD.

        Parameters:
            amount_sol (float): The amount in SOL to convert.

        Returns:
            float: The equivalent amount in USD.
        """
        price = self.get_sol_to_usd_price()
        
        if price > 0:
            return amount_sol * price
        
        return 0.0
