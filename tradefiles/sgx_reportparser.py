
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
    
    # It's more reliable to find the split point between letters and numbers
    match = re.match(r"([a-zA-Z]+)([FGHJKMNQUVXZ])(\d{2})", security)
    if match:
        symbol = match.group(1)
        month_char = match.group(2)
        year = match.group(3)
        
        month = month_codes.get(month_char)
        if month:
            return symbol, f"{month}-{year}"
            
    # Fallback for simpler patterns if the above fails
    match = re.match(r"([a-zA-Z]+)(\d{2})", security)
    if match:
        symbol = match.group(1)
        # This part is tricky without the month code, so we might just return the symbol
        return symbol, None

    return security, None


def remap_row(row, old_headers, target_headers, product_mapping):
    mapped_row = [''] * len(target_headers)
    old_header_map = {header.strip().lower(): idx for idx, header in enumerate(old_headers)}

    def get_value(header_name):
        return row[old_header_map[header_name]].strip() if header_name in old_header_map else ""

    # Handle trade execution date and time
    trade_execution_datetime_str = get_value("tradeexecutiondatetime")
    if trade_execution_datetime_str:
        try:
            dt_obj = datetime.strptime(trade_execution_datetime_str, '%Y-%m-%d %H:%M:%S')
            mapped_row[target_headers.index("tradedate")] = dt_obj.strftime('%Y-%m-%d')
            mapped_row[target_headers.index("tradedatetime")] = trade_execution_datetime_str
        except ValueError:
            mapped_row[target_headers.index("tradedate")] = ""
            mapped_row[target_headers.index("tradedatetime")] = ""

    # Handle security to get productname and contractmonth
    security = get_value("security")
    symbol, contract_month_from_security = parse_security(security)
    
    productname = product_mapping.get(symbol.lower(), symbol)
    mapped_row[target_headers.index("productname")] = productname

    # contractmonth from expiry, fallback to parsed from security
    expiry = get_value("expiry")
    if expiry:
        mapped_row[target_headers.index("contractmonth")] = expiry
    else:
        mapped_row[target_headers.index("contractmonth")] = contract_month_from_security if contract_month_from_security else ''

    # Direct mappings
    mapped_row[target_headers.index("dealid")] = get_value("dealid")
    mapped_row[target_headers.index("tradeid")] = get_value("tradeid")
    mapped_row[target_headers.index("quantitylots")] = get_value("quantityinlots")
    mapped_row[target_headers.index("quantityunits")] = get_value("quantityinunits")
    mapped_row[target_headers.index("price")] = get_value("price")
    mapped_row[target_headers.index("clearingstatus")] = get_value("tradestatus")
    mapped_row[target_headers.index("tradingsession")] = get_value("tradingsession")
    mapped_row[target_headers.index("cleareddate")] = get_value("cleareddate")
    mapped_row[target_headers.index("strike")] = get_value("strike")
    mapped_row[target_headers.index("unit")] = get_value("quantityunit")

    # Conditional mapping for buyer/seller info
    if get_value("buyeraccount"):
        mapped_row[target_headers.index("exchclearingacctid")] = get_value("buyeraccount")
        mapped_row[target_headers.index("trader")] = get_value("buyertrader")
        mapped_row[target_headers.index("brokergroupid")] = get_value("buyerbroker")
    elif get_value("selleraccount"):
        mapped_row[target_headers.index("exchclearingacctid")] = get_value("selleraccount")
        mapped_row[target_headers.index("trader")] = get_value("sellertrader")
        mapped_row[target_headers.index("brokergroupid")] = get_value("sellerbroker")

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
            "clearingstatus", "exchclearingacctid", "trader", "brokergroupid", 
            "tradingsession", "cleareddate", "strike", "unit"
        ]
        
        remapped_deals = []
        with open(csv_file_path, "r", newline='') as infile:
            reader = csv.reader(infile)
            old_headers = next(reader)
            for row in reader:
                remapped_deals.append(remap_row(row, old_headers, target_headers, product_mapping))

        with open(output_csv_path, "w", newline="") as outfile:
            writer = csv.writer(outfile)
            writer.writerow(target_headers)
            writer.writerows(remapped_deals)
            
        console.print(f"[bold green]Extracted and remapped data saved to {output_csv_path}[/bold green]")
