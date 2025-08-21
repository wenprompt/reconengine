
import csv
import json
import os
import re
from rich.console import Console
from rich.prompt import Prompt
from datetime import datetime

console = Console()

def get_cme_month_code_mapping():
    return {
        'F': 'Jan', 'G': 'Feb', 'H': 'Mar', 'J': 'Apr', 'K': 'May',
        'M': 'Jun', 'N': 'Jul', 'Q': 'Aug', 'U': 'Sep', 'V': 'Oct',
        'X': 'Nov', 'Z': 'Dec'
    }

def parse_security(security):
    month_codes = get_cme_month_code_mapping()
    put_call = None
    strike = None

    if '_' in security:
        parts = security.split('_')
        security = parts[0]
        pc_part = parts[1]
        if pc_part.startswith('P') or pc_part.startswith('C'):
            put_call = pc_part[0]
            strike = pc_part[1:]

    # The symbol is everything except the last 3 characters
    symbol = security[:-3]
    month_char = security[-3]
    year = security[-2:]
    
    month = month_codes.get(month_char)
    if month:
        return symbol, f"{month}-{year}", put_call, strike

    return security, None, None, None


def remap_row(row, old_headers, target_headers, product_mapping):
    mapped_row = [''] * len(target_headers)
    old_header_map = {header.strip(): idx for idx, header in enumerate(old_headers)}

    def get_value(header_name):
        try:
            return row[old_header_map[header_name]].strip()
        except (KeyError, IndexError):
            return ""

    clearing_status = get_value("Trade Status")
    if clearing_status.lower() != "cleared":
        return None

    # Handle trade execution date and time
    trade_execution_datetime_str = get_value("Trade Execution Date & Time (SGT)")
    print(f"trade_execution_datetime_str: {trade_execution_datetime_str}")
    if trade_execution_datetime_str:
        try:
            dt_obj = datetime.strptime(trade_execution_datetime_str, '%d/%m/%Y %I:%M %p')
            print(f"dt_obj: {dt_obj}")
            mapped_row[target_headers.index("tradedate")] = dt_obj.strftime('%Y-%m-%d')
            mapped_row[target_headers.index("tradedatetime")] = trade_execution_datetime_str
        except ValueError as e:
            print(f"ValueError: {e}")
            mapped_row[target_headers.index("tradedate")] = ""
            mapped_row[target_headers.index("tradedatetime")] = ""

    # Handle security to get productname and contractmonth
    security = get_value("Security")
    symbol, contract_month_from_security, put_call, strike_from_security = parse_security(security)
    
    productname = product_mapping.get(symbol, symbol)
    mapped_row[target_headers.index("productname")] = productname

    # contractmonth from expiry, fallback to parsed from security
    expiry = get_value("Expiry")
    if expiry:
        mapped_row[target_headers.index("contractmonth")] = expiry
    else:
        mapped_row[target_headers.index("contractmonth")] = contract_month_from_security if contract_month_from_security else ''

    # strike from security if not present in its own column
    strike = get_value("Strike")
    if not strike and strike_from_security:
        mapped_row[target_headers.index("strike")] = strike_from_security
    else:
        mapped_row[target_headers.index("strike")] = strike

    if put_call:
        mapped_row[target_headers.index("put/call")] = put_call

    # Direct mappings
    mapped_row[target_headers.index("dealid")] = get_value("Deal ID")
    mapped_row[target_headers.index("tradeid")] = get_value("Trade ID (Leg)")
    mapped_row[target_headers.index("quantitylots")] = get_value("Quantity In Lots")
    mapped_row[target_headers.index("quantityunits")] = get_value("Quantity In Units")
    mapped_row[target_headers.index("price")] = get_value("Price")
    mapped_row[target_headers.index("clearingstatus")] = clearing_status
    mapped_row[target_headers.index("tradingsession")] = get_value("Trading Session")
    mapped_row[target_headers.index("cleareddate")] = get_value("Cleared Date (SGT)")
    mapped_row[target_headers.index("strike")] = get_value("Strike")
    mapped_row[target_headers.index("unit")] = get_value("Quantity Unit")

    # Conditional mapping for buyer/seller info and b/s determination
    if get_value("Buyer Account"):
        mapped_row[target_headers.index("trader")] = get_value("Buyer Trader")
        mapped_row[target_headers.index("b/s")] = "B"
    elif get_value("Seller Account"):
        mapped_row[target_headers.index("trader")] = get_value("Seller Trader")
        mapped_row[target_headers.index("b/s")] = "S"

    # Hardcoded values
    mapped_row[target_headers.index("brokergroupid")] = "3"
    mapped_row[target_headers.index("exchangegroupid")] = "1"
    mapped_row[target_headers.index("exchclearingacctid")] = "2"

    return mapped_row


if __name__ == "__main__":
    input_dir = "/home/wenhaowang/projects/reconengine/tradefiles/input/"
    output_dir = "/home/wenhaowang/projects/reconengine/tradefiles/output/"
    output_csv_path = os.path.join(output_dir, "sourceExchange.csv")
    mapping_path = "/home/wenhaowang/projects/reconengine/tradefiles/mapping.json"

    available_files = [f for f in os.listdir(input_dir) if f.endswith(".csv") and "titan-otc-trade-export" in f]
    
    if not available_files:
        console.print("[bold red]Error:[/bold red] No 'titan-otc-trade-export' CSV files found in the input directory.")
    else:
        console.print("\nSelect a Titan OTC Trade Export CSV file to process:")
        for i, fname in enumerate(available_files):
            console.print(f"{i+1}. {fname}")
        
        while True:
            try:
                choice = Prompt.ask("Enter the number of your choice")
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(available_files):
                    selected_file = available_files[choice_idx]
                    break
                else:
                    console.print("[bold red]Invalid choice. Please enter a number from the list.[/bold red]")
            except ValueError:
                console.print("[bold red]Invalid input. Please enter a number.[/bold red]")

        csv_file_path = os.path.join(input_dir, selected_file)

        try:
            with open(mapping_path, 'r') as f:
                product_mapping = json.load(f)
        except FileNotFoundError:
            product_mapping = {}
            console.print(f"[bold yellow]Warning:[/bold yellow] {mapping_path} not found. Product names will not be remapped.")

        target_headers = [
            "tradedate", "tradedatetime", "dealid", "tradeid", "productname", 
            "contractmonth", "quantitylots", "quantityunits", "price", 
            "clearingstatus", "exchclearingacctid", "trader", "brokergroupid", "exchangegroupid",
            "tradingsession", "cleareddate", "strike", "unit", "put/call", "b/s"
        ]
        
        remapped_deals = []
        with open(csv_file_path, "r", newline='') as infile:
            reader = csv.reader(infile)
            old_headers = next(reader)
            for row in reader:
                remapped_row = remap_row(row, old_headers, target_headers, product_mapping)
                if remapped_row:
                    remapped_deals.append(remapped_row)

        with open(output_csv_path, "w", newline="") as outfile:
            writer = csv.writer(outfile)
            writer.writerow(target_headers)
            writer.writerows(remapped_deals)
            
        console.print(f"[bold green]Extracted and remapped data saved to {output_csv_path}[/bold green]")
