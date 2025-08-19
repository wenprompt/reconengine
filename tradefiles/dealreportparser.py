import csv
import json
import os
from rich.console import Console
from rich.prompt import Prompt

console = Console()

def extract_cleared_deals(file_path):
    extracted_rows = []
    start_extraction = False
    cleared_deals_header = []
    with open(file_path, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if "Cleared Deals" in row:
                start_extraction = True
                # Skip the next two header rows after "Cleared Deals"
                next(reader)  # Skip empty row
                # Capture the header row
                cleared_deals_header = next(reader)
                continue
            if "Futures Deals" in row:
                start_extraction = False
                break
            if start_extraction:
                # Skip empty rows
                if any(field.strip() for field in row):
                    extracted_rows.append(row)

    # Apply filtering
    filtered_rows = []
    if cleared_deals_header:
        try:
            source_col_idx = cleared_deals_header.index("Source")
            trader_col_idx = cleared_deals_header.index("Trader")
        except ValueError as e:
            console.print(f"[bold red]Error:[/bold red] Missing expected column in header: {e}")
            return [], [] # Return empty if headers are missing

        allowed_traders = ["Jiang, S", "Yik, R", "Foo, V"]

        for row in extracted_rows:
            if row[source_col_idx].strip() == "ICE Block" and \
               row[trader_col_idx].strip() in allowed_traders:
                filtered_rows.append(row)

    return cleared_deals_header, filtered_rows


def remap_row(row, old_headers, target_headers):
    mapped_row = [''] * len(target_headers)
    
    # Create a dictionary for easy lookup of old column indices
    old_header_map = {header.strip(): idx for idx, header in enumerate(old_headers)}

    # Load product mapping
    try:
        with open("/home/wenhaowang/projects/reconengine/tradefiles/mapping.json", 'r') as f:
            product_mapping = json.load(f)
    except FileNotFoundError:
        product_mapping = {}
        console.print("[bold yellow]Warning:[/bold yellow] mapping.json not found. Product names will not be remapped.")

    # Define mapping from target header to old header/value
    mapping = {
        "tradedate": "Trade Date",
        "tradedatetime": "Trade Time",
        "dealid": "Deal ID",
        "tradeid": "Leg ID",
        "b/s": "B/S",
        "quantitylots": "Lots",
        "quantityunits": "Total Quantity",
        "unit": "Qty Units",
        "price": "Price",
        "contractmonth": "Contract",
        "productname": "Product", # This will be remapped using mapping.json
        "productid": "", # Left empty as per request
        "trader": "Trader",
        "source": "Source",
        "brokergroupid": "3", # Hardcoded
        "exchangegroupid": "1", # Hardcoded
        "exchclearingacctid": "2", # Hardcoded
        "cleareddate": "", # No direct mapping
        "strike": "", # No direct mapping
        "put/call": "", # No direct mapping
        "clearingstatus": "", # No direct mapping
        "tradingsession": "", # No direct mapping
    }

    for target_idx, target_header in enumerate(target_headers):
        target_header_lower = target_header.lower()
        if target_header_lower in mapping:
            source_key = mapping[target_header_lower]
            
            if target_header_lower == "productname":
                original_product_name = row[old_header_map.get("Hub", -1)].strip() # Get original product name from Hub column
                mapped_product_name = product_mapping.get(original_product_name.lower(), original_product_name) # Remap
                mapped_row[target_idx] = mapped_product_name
            elif source_key in old_header_map:
                mapped_row[target_idx] = row[old_header_map[source_key]]
            elif source_key.isdigit(): # Check if it's a hardcoded value
                mapped_row[target_idx] = source_key
            else:
                mapped_row[target_idx] = "" # Default empty for unmapped or missing

    return mapped_row


if __name__ == "__main__":
    input_dir = "/home/wenhaowang/projects/reconengine/tradefiles/input/"
    output_dir = "/home/wenhaowang/projects/reconengine/tradefiles/output/"
    output_csv_path = os.path.join(output_dir, "sourceExchange.csv")

    # Get list of available CSV files
    available_files = [f for f in os.listdir(input_dir) if f.endswith(".csv")]
    if not available_files:
        console.print("[bold red]Error:[/bold red] No CSV files found in the input directory.")
    else:
        # Present numbered list to user
        console.print("\nSelect a DealReport CSV file to process:")
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

        cleared_deals_header, filtered_cleared_deals = extract_cleared_deals(csv_file_path)

        target_headers = ["tradedate", "tradedatetime", "cleareddate", "dealid", "tradeid", "productid", "productname", "productgroupid", "contractmonth", "quantitylots", "quantityunits", "b/s", "price", "strike", "put/call", "brokergroupid", "exchangegroupid", "exchclearingacctid", "trader", "clearingstatus", "tradingsession", "unit", "source"]

        remapped_deals = []
        for row in filtered_cleared_deals:
            remapped_deals.append(remap_row(row, cleared_deals_header, target_headers))

        with open(output_csv_path, "w", newline="") as outfile:
            writer = csv.writer(outfile)
            writer.writerow(target_headers)
            writer.writerows(remapped_deals)
        console.print(f"[bold green]Extracted and remapped data saved to {output_csv_path}[/bold green]")