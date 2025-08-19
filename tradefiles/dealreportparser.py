import csv


def extract_cleared_deals(file_path):
    extracted_rows = []
    start_extraction = False
    with open(file_path, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if "Cleared Deals" in row:
                start_extraction = True
                # Skip the next two header rows after "Cleared Deals"
                next(reader)  # Skip empty row
                next(reader)  # Skip header row
                continue
            if "Futures Deals" in row:
                start_extraction = False
                break
            if start_extraction:
                # Skip empty rows
                if any(field.strip() for field in row):
                    extracted_rows.append(row)
    return extracted_rows


if __name__ == "__main__":
    csv_file_path = "/home/wenhaowang/projects/reconengine/tradefiles/DealReport 27062025.csv"
    output_csv_path = "/home/wenhaowang/projects/reconengine/tradefiles/sourceExchange.csv"

    cleared_deals = extract_cleared_deals(csv_file_path)

    with open(output_csv_path, "w", newline="") as outfile:
        writer = csv.writer(outfile)
        writer.writerows(cleared_deals)
    print(f"Extracted data saved to {output_csv_path}")
