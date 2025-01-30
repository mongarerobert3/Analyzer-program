import csv
import os
from bs4 import BeautifulSoup
from decouple import config
import requests

# Get URL from environment variable
html_url = config("HTML_URL")  

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',  
    'Connection': 'keep-alive',
    'Referer': 'https://dexcheck.ai/',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
}

# Fetch HTML content from URL
try:
    response = requests.get(html_url, headers=headers)
    response.raise_for_status()  # Check for HTTP errors
    html_content = response.text
except Exception as e:
    print(f"Error fetching URL: {e}")
    exit()

# Parse HTML
soup = BeautifulSoup(html_content, "html.parser")

# Extract wallet addresses
wallet_addresses = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    # Split the URL path and look for the chart segment
    parts = href.split("/")
    
    # Find the position of 'chart' in the path
    try:
        chart_index = parts.index("chart")
        if chart_index + 1 < len(parts):
            wallet_address = parts[chart_index + 1]
            # Better Solana address validation (base58 characters)
            if len(wallet_address) == 44 and all(c in '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz' for c in wallet_address):
                wallet_addresses.append(wallet_address)
    except ValueError:
        continue  # 'chart' not found in this URL

# Remove duplicates while preserving order
seen = set()
wallet_addresses = [x for x in wallet_addresses if not (x in seen or seen.add(x))]

# Save to CSV
csv_filename = "solana_wallets.csv"
with open(csv_filename, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Wallet Address"])
    writer.writerows([[address] for address in wallet_addresses])

print(f"Extracted {len(wallet_addresses)} unique wallet addresses. Saved to {csv_filename}")