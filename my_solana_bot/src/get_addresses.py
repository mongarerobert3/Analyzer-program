import csv
import re
import time
from decouple import config
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException

# Get URL from environment variable
html_url = config("HTML_URL")

# Set up Selenium WebDriver options
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Run in headless mode (no GUI)
options.add_argument("--disable-gpu")  # Disable GPU acceleration (often helpful in headless mode)
options.add_argument("--no-sandbox")  # Bypass OS security restrictions (sometimes needed in headless mode)
options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems

# Initialize WebDriver
driver = webdriver.Chrome(options=options)

# Regular expression for Solana base58 addresses
address_regex = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{44}$")

try:
    driver.get(html_url)  # Load the page

    # Wait for the elements to load (adjust timeout as needed)
    wait = WebDriverWait(driver, 20)

    # The CORRECT and TESTED selector using XPath:
    elements = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href, '/chart/')]")))

    # Find the elements again after waiting (good practice)
    elements = driver.find_elements(By.XPATH, "//a[contains(@href, '/chart/')]")

    wallet_addresses = set()

    for _ in range(3):  # Retry loop for stale elements
        try:
            for element in elements:
                href = element.get_attribute("href")
                if href:
                    parts = href.split("/")
                    try:
                        chart_index = parts.index("chart")  # Or whatever identifies the address
                        if chart_index + 1 < len(parts):
                            wallet_address = parts[chart_index + 1]
                            if address_regex.match(wallet_address):
                                wallet_addresses.add(wallet_address)
                    except ValueError:
                        pass  # "chart" not found, skip
            break  # Exit the retry loop if successful
        except StaleElementReferenceException:
            print("Stale element. Retrying...")
            time.sleep(1)
    else:
        print("Could not retrieve elements after multiple retries (Stale Element Reference).")

    # Save to CSV
    csv_filename = "solana_wallets.csv"
    with open(csv_filename, "w", newline="", encoding="utf-8") as csvfile:  # Added encoding for special characters
        writer = csv.writer(csvfile)
        writer.writerow(["Wallet Address"])
        writer.writerows([[address] for address in wallet_addresses])

    print(f"Extracted {len(wallet_addresses)} unique wallet addresses. Saved to {csv_filename}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()  # Print the full traceback for debugging

finally:
    driver.quit()  # Ensure driver quits even if there's an error