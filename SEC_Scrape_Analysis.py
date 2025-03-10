"""
SEC and Insider Trading Analysis

This script performs textual analysis on SEC filings for selected banks and
analyzes AMC Entertainment Form 4 filings for insider trading events.

Author: Ryan Loveless
Date: 3/5/2025
"""

import os
import re
import shutil
import requests
import pandas as pd
import matplotlib.pyplot as plt
from typing import List, Optional

# === Configuration Constants === #
from constants import BASE_FILINGS_URL, SEC_BASE_URL, USER_AGENT, WORKING_DIR

# === Utility Functions === #
def ensure_working_directory(path: str) -> None:
    """Ensure the working directory exists and change to it."""
    if not os.path.exists(path):
        os.makedirs(path)
    os.chdir(path)

def download_and_extract_index(year: int, quarter: int, base_url: str, user_agent: str) -> Optional[pd.DataFrame]:
    """
    Download and extract SEC index file for a given year and quarter.
    
    Returns:
        DataFrame of the parsed index or None if download fails.
    """
    zip_filename = f"master{year}qtr{quarter}.zip"
    txt_filename = f"master{year}qtr{quarter}.txt"
    url = f"{base_url}{year}/QTR{quarter}/master.zip"
    print(f"Processing {year} Q{quarter}...")
    
    response = requests.get(url, headers={"User-Agent": user_agent})
    if response.status_code != 200:
        print(f"Failed to download data for {year} Q{quarter}")
        return None

    with open(zip_filename, 'wb') as f:
        f.write(response.content)
    
    shutil.unpack_archive(zip_filename)
    os.rename("master.idx", txt_filename)
    
    # Skip header lines and parse the rest into a DataFrame.
    with open(txt_filename, 'r', encoding='latin1') as f:
        lines = f.readlines()[11:]
    data = [line.strip().split('|') for line in lines if line.strip()]
    return pd.DataFrame(data, columns=['CIK', 'CompanyName', 'FormType', 'DateFiled', 'FileName'])

def download_filing(file_url: str, local_path: str, user_agent: str) -> Optional[str]:
    """
    Download a filing and save it locally.
    
    Returns:
        The filing text if download succeeds, or None.
    """
    response = requests.get(file_url, headers={"User-Agent": user_agent})
    if response.status_code == 200:
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        return response.text
    else:
        print(f"Failed to download filing from {file_url}")
        return None

# === Text Extraction Functions === #
def extract_first_topic(text: str) -> str:
    """
    Extract the first event topic from the 'ITEM INFORMATION:' header.
    
    If no topic is found, returns "Unknown".
    """
    pattern = re.compile(r'ITEM INFORMATION:\s*(.+)', re.IGNORECASE)
    match = pattern.search(text)
    if match:
        return match.group(1).splitlines()[0].strip()
    return "Unknown"

def extract_all_topics(text: str) -> List[str]:
    """
    Extract all event topics from the 'ITEM INFORMATION:' header.
    
    Returns:
        A list of topics extracted from the text.
    """
    pattern = re.compile(r'ITEM INFORMATION:\s*(.*?)(?=\bFILED AS OF DATE:|\Z)', re.IGNORECASE | re.DOTALL)
    match = pattern.search(text)
    if match:
        topics_block = match.group(1)
        return [line.strip() for line in topics_block.splitlines() if line.strip()]
    return []

def extract_filed_date(text: str) -> Optional[str]:
    """
    Extract the filing date following 'FILED AS OF DATE:'.
    
    Returns:
        The date string in 8-digit format if found, otherwise None.
    """
    pattern = re.compile(r'\bFILED AS OF DATE:\s*(\d{8})\b', re.IGNORECASE)
    match = pattern.search(text)
    if match:
        return match.group(1)
    return None

def count_bankruptcy_terms(text: str) -> int:
    """
    Count occurrences of 'bankruptcy' or 'bankruptcies' in the text.
    
    Returns:
        The count as an integer.
    """
    pattern = re.compile(r'\b(bankruptcy|bankruptcies)\b', re.IGNORECASE)
    return len(pattern.findall(text))

# === Main Analysis Functions === #
def process_sec_filings():
    """Process SEC filings for the two banks and perform textual analyses."""
    # Define quarters for SEC analysis.
    sec_quarters = [
        (2022, 4), (2023, 1), (2023, 2), (2023, 3),
        (2023, 4), (2024, 1), (2024, 2), (2024, 3)
    ]
    dataframes = []
    for year, quarter in sec_quarters:
        df = download_and_extract_index(year, quarter, SEC_BASE_URL, USER_AGENT)
        if df is not None:
            dataframes.append(df)
    if not dataframes:
        print("No SEC data available.")
        return
    sec_data = pd.concat(dataframes, ignore_index=True)
    sec_data['CIK'] = sec_data['CIK'].astype(int)

    # Filter for the two banks.
    bank_ciks = [719739, 834285]
    bank_data = sec_data[sec_data['CIK'].isin(bank_ciks)]
    form_frequencies = bank_data.groupby(['CIK', 'FormType']).size().reset_index(name='Frequency')
    print("SEC Form Frequencies for the two banks (2022Q4 to 2024Q3):")
    print(form_frequencies)

    # Download and analyze 8-K filings.
    bank_8k = bank_data[bank_data['FormType'] == '8-K'].copy()
    os.makedirs("8K_filings", exist_ok=True)
    filing_texts = {}
    for idx, row in bank_8k.iterrows():
        file_url = BASE_FILINGS_URL + row['FileName']
        local_filename = os.path.join("8K_filings", f"{row['CIK']}_{row['DateFiled']}_{idx}.txt")
        print(f"Downloading 8-K filing for CIK {row['CIK']}...")
        text = download_filing(file_url, local_filename, USER_AGENT)
        if text:
            filing_texts[idx] = text

    # Extract and analyze first topics.
    bank_8k['FirstTopic'] = bank_8k.index.map(lambda idx: extract_first_topic(filing_texts.get(idx, "")))
    freq_first_topics = bank_8k.groupby(['CIK', 'FirstTopic']).size().reset_index(name='Frequency')
    freq_first_topics = freq_first_topics.sort_values(by='Frequency', ascending=False)
    print("\nFrequencies of 8-K topics (first topic extracted):")
    print(freq_first_topics)

    # Delisting analysis based on first topic.
    delisting_filing_dates = {}
    for idx, text in filing_texts.items():
        topic = extract_first_topic(text)
        if re.search(r'\bdelisting\b', topic, re.IGNORECASE):
            filed_date = extract_filed_date(text)
            if filed_date:
                cik = bank_8k.loc[idx, 'CIK']
                delisting_filing_dates.setdefault(cik, []).append(filed_date)
    print("\nDelisting Filing Dates (based on first topic extraction):")
    for cik, dates in delisting_filing_dates.items():
        print(f"CIK {cik}: {dates}")

    # Delisting analysis based on all topics.
    delisting_filing_dates_all = {}
    for idx, text in filing_texts.items():
        topics = extract_all_topics(text)
        if any(re.search(r'\bdelisting\b', t, re.IGNORECASE) for t in topics):
            filed_date = extract_filed_date(text)
            if filed_date:
                cik = bank_8k.loc[idx, 'CIK']
                delisting_filing_dates_all.setdefault(cik, []).append(filed_date)
    print("\nDelisting Filing Dates (based on all topics extraction):")
    for cik, dates in delisting_filing_dates_all.items():
        print(f"CIK {cik}: {dates}")

    # Bankruptcy count analysis.
    bankruptcy_counts = {idx: count_bankruptcy_terms(text) for idx, text in filing_texts.items()}
    bank_8k['BankruptcyCount'] = bank_8k.index.map(lambda idx: bankruptcy_counts.get(idx, 0))
    firm_bankruptcy_counts = bank_8k.groupby('CIK')['BankruptcyCount'].sum().reset_index()
    print("\nCount of 'bankruptcy' or 'bankruptcies' in each firm's entire 8-K documents:")
    print(firm_bankruptcy_counts)

def process_amc_filings():
    """Process AMC Entertainment Form 4 filings and perform insider trading analysis."""
    # Define AMC filing quarters.
    amc_quarters = [
        (2020, 3), (2020, 4), (2021, 1), (2021, 2),
        (2021, 3), (2021, 4), (2022, 1), (2022, 2)
    ]
    amc_dataframes = []
    for year, quarter in amc_quarters:
        df = download_and_extract_index(year, quarter, SEC_BASE_URL, USER_AGENT)
        if df is not None:
            amc_dataframes.append(df)
    if not amc_dataframes:
        print("No AMC data available.")
        return
    amc_index_data = pd.concat(amc_dataframes, ignore_index=True)
    amc_index_data['CIK'] = amc_index_data['CIK'].astype(int)

    # Filter for AMC Entertainment Form 4 filings.
    amc_data = amc_index_data[(amc_index_data['CIK'] == 1411579) &
                              (amc_index_data['FormType'] == '4')].copy()
    print("\nAMC Entertainment Form 4 Filings:")
    print(amc_data)

    os.makedirs("Form4_filings", exist_ok=True)
    amc_filings_texts = {}
    for idx, row in amc_data.iterrows():
        file_url = BASE_FILINGS_URL + row['FileName']
        local_filename = os.path.join("Form4_filings", f"{row['CIK']}_{row['DateFiled']}_{idx}.txt")
        print(f"Downloading AMC Form 4 filing...")
        text = download_filing(file_url, local_filename, USER_AGENT)
        if text:
            amc_filings_texts[idx] = text

    # --- Task B1: Extract isOfficer indicator --- #
    def extract_is_officer(text: str) -> Optional[str]:
        pattern = re.compile(r'<\s*isOfficer\s*>\s*(\d+)\s*<\s*/\s*isOfficer\s*>', re.IGNORECASE)
        match = pattern.search(text)
        return match.group(1).strip() if match else None

    amc_data['IsOfficer'] = amc_data.index.map(lambda idx: extract_is_officer(amc_filings_texts.get(idx, "")))
    officer_filings = amc_data[amc_data['IsOfficer'] == "1"]
    print(f"\nNumber of Form 4 filings filed by an officer: {len(officer_filings)}")

    # --- Task B2: Extract and clean officer titles --- #
    def extract_officer_title(text: str) -> str:
        pattern = re.compile(r'<\s*officerTitle\s*>\s*(.*?)\s*<\s*/\s*officerTitle\s*>', re.IGNORECASE | re.DOTALL)
        match = pattern.search(text)
        if match:
            title = match.group(1)
            title_clean = title.replace('&amp;', '').replace(',', '')
            return " ".join(title_clean.split()).upper()
        return "UNKNOWN"

    officer_filings.loc[:, 'OfficerTitle'] = officer_filings.index.map(lambda idx: extract_officer_title(amc_filings_texts.get(idx, "")))
    officer_title_freq = officer_filings['OfficerTitle'].value_counts().reset_index()
    officer_title_freq.columns = ['OfficerTitle', 'Frequency']
    print("\nCleaned Officer Titles and their Frequencies:")
    print(officer_title_freq)

    # --- Task B3: Extract transaction type code (A or D) --- #
    def extract_transaction_type(text: str) -> Optional[str]:
        pattern = re.compile(
            r'<\s*transactionAcquiredDisposedCode\s*>\s*<\s*value\s*>\s*([AD])\s*<\s*/\s*value\s*>\s*<\s*/\s*transactionAcquiredDisposedCode\s*>',
            re.IGNORECASE
        )
        match = pattern.search(text)
        return match.group(1).strip().upper() if match else None

    officer_filings.loc[:, 'TransactionType'] = officer_filings.index.map(lambda idx: extract_transaction_type(amc_filings_texts.get(idx, "")))
    transaction_type_counts = officer_filings['TransactionType'].value_counts().reset_index()
    transaction_type_counts.columns = ['TransactionType', 'Frequency']
    print("\nTransaction Type Counts among Officer Filings:")
    print(transaction_type_counts)

    # --- Task B4: Extract transaction date --- #
    def extract_transaction_date(text: str) -> Optional[str]:
        pattern = re.compile(
            r'<\s*transactionDate\s*>\s*<\s*value\s*>\s*([\d\-]+)\s*<\s*/\s*value\s*>\s*<\s*/\s*transactionDate\s*>',
            re.IGNORECASE
        )
        match = pattern.search(text)
        return match.group(1).strip().replace('-', '') if match else None

    officer_filings.loc[:, 'TransactionDate'] = officer_filings.index.map(lambda idx: extract_transaction_date(amc_filings_texts.get(idx, "")))
    print("\nExtracted Transaction Dates from Officer Filings:")
    print(officer_filings[['TransactionDate']])

    # --- Task B5: Bar chart for "D" (Disposed) transactions by date --- #
    disposed_filings = officer_filings[officer_filings['TransactionType'] == "D"]
    disposed_counts = disposed_filings['TransactionDate'].value_counts().sort_index().reset_index()
    disposed_counts.columns = ['TransactionDate', 'Count']
    print("\nDisposed Transaction Counts by Transaction Date:")
    print(disposed_counts)

    plt.figure(figsize=(10, 6))
    plt.bar(disposed_counts['TransactionDate'], disposed_counts['Count'])
    plt.xlabel("Transaction Date")
    plt.ylabel("Count of 'D' Transactions")
    plt.title("Counts of Officer 'Disposed' Transactions by Date")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

    if not disposed_counts.empty:
        max_row = disposed_counts.loc[disposed_counts['Count'].idxmax()]
        print(f"\nDate with the largest number of officer-selling transactions: {max_row['TransactionDate']} (Count: {max_row['Count']})")
    else:
        print("\nNo officer-selling ('D') transactions found.")

def main():
    ensure_working_directory(WORKING_DIR)
    process_sec_filings()
    process_amc_filings()

if __name__ == '__main__':
    main()
