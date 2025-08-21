import openpyxl
import csv
import json
from datetime import datetime
from rich.console import Console

console = Console()

def parse_fo_xlsx(input_path, output_path, mapping_path):
    """
    Parses an Excel file (fo.xlsx), transforms the data, and writes it to a CSV file.

    Args:
        input_path (str): Path to the input Excel file.
        output_path (str): Path to the output CSV file.
        mapping_path (str): Path to the JSON mapping file for product names.
    """
    try:
        with open(mapping_path, 'r') as f:
            product_mapping = json.load(f)
    except FileNotFoundError:
        console.print(f"[bold yellow]Warning:[/bold yellow] Mapping file not found at {mapping_path}. Product names will not be mapped.")
        product_mapping = {}

    workbook = openpyxl.load_workbook(input_path)
    sheet = workbook.active

    header = [cell.value for cell in sheet[1]]
    
    # Map columns to their indices
    column_indices = {name: i for i, name in enumerate(header)}

    output_rows = []
    # Add header to output
    output_header = [
        "traderid", "tradedate", "tradetime", "productid", "productname", 
        "productgroupid", "exchangegroupid", "brokergroupid", "exchclearingacctid", 
        "quantitylots", "quantityunits", "unit", "price", "contractmonth", 
        "strike", "specialComms", "spread", "b/s", "RMKS", "BKR"
    ]
    output_rows.append(output_header)

    for row_index in range(2, sheet.max_row + 1):
        row_values = [cell.value for cell in sheet[row_index]]

        # Check if the row is empty
        if not any(row_values):
            continue # Skip empty rows
        
        # Extract values from the row
        time_val = row_values[column_indices.get('Time')]
        product_val = row_values[column_indices.get('Product')]
        size_val = row_values[column_indices.get('Size')]
        price_val = row_values[column_indices.get('Price')]
        spread_val = row_values[column_indices.get('Spread')]
        broker_val = row_values[column_indices.get('Broker')]
        contract_month_val = row_values[column_indices.get('ContractMonth')]

        # --- Filters ---
        if str(broker_val).lower() == 'screen':
            continue
        if str(spread_val).lower() == 'sgx':
            continue

        # --- Transformations ---
        
        # tradedate and tradetime
        tradedate = ""
        tradetime = ""
        if isinstance(time_val, datetime):
            tradedate = time_val.strftime('%d/%m/%Y')
            tradetime = time_val.strftime('%d/%m/%Y %H:%M')

        # productname
        productname = product_mapping.get(str(product_val).lower(), product_val)

        # exchangegroupid, brokergroupid, exchclearingacctid
        exchangegroupid = 1
        brokergroupid = 3
        exchclearingacctid = 2

        # quantity and b/s
        try:
            size_float = float(size_val)
            quantity = abs(size_float * 1000)
            if size_float > 0:
                bs = 'B'
            elif size_float < 0:
                bs = 'S'
            else:
                bs = ''
        except (ValueError, TypeError):
            console.print(f"[bold red]Error:[/bold red] Invalid 'Size' value in row {row_index}: '{size_val}'.")
            raise

        # price
        price = price_val

        # spread
        spread = 'S' if str(spread_val).lower() == 'spr' else ''

        # Create the output row
        output_row = {
            "traderid": "",
            "tradedate": tradedate,
            "tradetime": tradetime,
            "productid": "",
            "productname": productname,
            "productgroupid": "",
            "exchangegroupid": exchangegroupid,
            "brokergroupid": brokergroupid,
            "exchclearingacctid": exchclearingacctid,
            "quantitylots": "",
            "quantityunits": quantity,
            "unit": "",
            "price": price,
            "contractmonth": contract_month_val,
            "strike": "",
            "specialComms": "",
            "spread": spread,
            "b/s": bs,
            "RMKS": "",
            "BKR": ""
        }
        
        output_rows.append([output_row[h] for h in output_header])

    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(output_rows)

if __name__ == '__main__':
    # Define paths
    input_file = '/home/wenhaowang/projects/reconengine/tradefiles/input_traders/fo.xlsx'
    output_file = '/home/wenhaowang/projects/reconengine/tradefiles/output_traders/sourceTraders.csv'
    mapping_file = '/home/wenhaowang/projects/reconengine/tradefiles/mapping.json'
    
    # Run the parser
    parse_fo_xlsx(input_file, output_file, mapping_file)
    
    console.print(f"[bold green]Successfully parsed {input_file} and created {output_file}[/bold green]")
