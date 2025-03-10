"""
SEC-API and Filing Analysis Script

This script performs the following tasks:
1. Queries SEC-API for 10-K filings within a specified date range.
2. Enriches filing header information using the SEC Submissions Endpoint.
3. Creates geographic choropleth maps for state-level filings.
4. Downloads and processes filing documents:
   - Extracts the "Item 1. Business" section via regex.
   - Extracts sentences mentioning "Artificial Intelligence".
5. Aggregates and visualizes the filings data based on geographic and AI mention metrics.

Author: Ryan Loveless
Date: 3/5/2025
"""

import os
import time
import random
import re
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime
from bs4 import BeautifulSoup

from constants import API_KEY, USER_AGENT  # Replace with your API Key and User Agent
from sec_api import QueryApi

# === Configuration Constants === #
HEADERS = {"User-Agent": USER_AGENT}
WORKING_DIR = r'C:\Users\ryanl\OneDrive\Desktop\MS Finance Courses\Textual Analysis\Case Studies\Case 4'
DESIRED_COUNT = 500
PAGE_SIZE = 200
QUERY_STRING = (
    'formType:("10-K","10-KT","10KSB","10KT405","10KSB40","10-K405") '
    'AND filedAt:[2023-01-01 TO 2023-12-31]'
)

# === Utility Functions === #
def set_working_directory(path: str) -> None:
    """Ensure the working directory exists and change to it."""
    if not os.path.exists(path):
        os.makedirs(path)
    os.chdir(path)
    print("Working directory set to:", os.getcwd())

def query_filings(api: QueryApi, query_str: str, desired_count: int, page_size: int) -> pd.DataFrame:
    """
    Query SEC-API for filings based on the given query string.

    Args:
        api (QueryApi): An instance of QueryApi.
        query_str (str): The query string for SEC filings.
        desired_count (int): Number of filings to collect.
        page_size (int): Number of filings per page.

    Returns:
        DataFrame containing the queried filings.
    """
    start = 0
    filings_list = []
    while len(filings_list) < desired_count:
        query = {
            "query": {"query_string": {"query": query_str}},
            "from": start,
            "size": page_size,
            "sort": [{"filedAt": {"order": "desc"}}]
        }
        print(f"Fetching filings starting at {start} ...")
        result = api.get_filings(query)
        filings = result.get("filings", [])
        if not filings:
            break
        for filing in filings:
            filings_list.append({
                "cik": filing.get("cik"),
                "companyName": filing.get("companyName"),
                "formType": filing.get("formType"),
                "filedAt": filing.get("filedAt"),
                "accessionNumber": filing.get("accessionNo"),
                "fileLink": filing.get("linkToFilingDetails")
            })
        start += page_size
        time.sleep(1)
    
    print(f"Total filings collected: {len(filings_list)}")
    # Randomly sample if we collected more than desired_count
    if len(filings_list) > desired_count:
        filings_list = random.sample(filings_list, desired_count)
    filings_df = pd.DataFrame(filings_list)
    print("Total 10-K filings in DataFrame:", len(filings_df))
    return filings_df

def get_submission_data(cik: int) -> dict:
    """
    Query the SEC submissions API for header details for a given CIK.

    Args:
        cik (int): The company's CIK.

    Returns:
        Dictionary with submission data if available, else an empty dict.
    """
    cik_str = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_str}.json"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"Warning: Unable to fetch submission data for CIK {cik}")
        return {}

def enrich_header_data(filings_df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich the filings DataFrame with additional header information via the SEC Submissions Endpoint.

    Args:
        filings_df (DataFrame): The initial filings DataFrame.

    Returns:
        DataFrame enriched with header details.
    """
    header_data = []
    for _, row in filings_df.iterrows():
        submission = get_submission_data(row["cik"])
        state = submission.get("stateOfIncorporation", "")
        if not state:
            state = submission.get("businessAddress", {}).get("state", "")
            if not state:
                state = submission.get("mailingAddress", {}).get("state", "")
        header_data.append({
            "CIK": row["cik"],
            "CompanyName": submission.get("name", row["companyName"]),
            "FormType": row["formType"],
            "FilingDate": row["filedAt"],
            "SIC": submission.get("sic", ""),
            "State": state,
            "City": submission.get("businessAddress", {}).get("city", ""),
            "Zip": submission.get("businessAddress", {}).get("zip", ""),
            "AccessionNumber": row["accessionNumber"],
            "FileLink": row["fileLink"]
        })
    headers_df = pd.DataFrame(header_data)
    headers_df["FilingDate"] = pd.to_datetime(headers_df["FilingDate"])
    print(headers_df.info())
    print(headers_df.head(10))
    return headers_df

def create_state_heatmap(df: pd.DataFrame, title: str) -> None:
    """
    Create a geographic choropleth map based on state-level filings data.

    Args:
        df (DataFrame): DataFrame with 'State' and at least one count column.
        title (str): Title for the plot.
    """
    fig = px.choropleth(
        df,
        locations="State",
        locationmode="USA-states",
        color=df.columns[1],
        scope="usa",
        title=title,
        hover_data=df.columns.tolist()
    )
    fig.show()

def get_filing_text(file_link: str) -> str:
    """
    Download and parse the filing details page, extracting the primary 10-K document text.

    Args:
        file_link (str): URL of the filing details page.

    Returns:
        The text content of the 10-K document.
    """
    try:
        response = requests.get(file_link, headers=HEADERS)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "lxml")
            docs = soup.find_all("document")
            for doc in docs:
                type_tag = doc.find("type")
                if type_tag and type_tag.get_text().strip() == "10-K":
                    return doc.get_text(separator=" ", strip=True)
            return soup.get_text(separator=" ", strip=True)
        else:
            print(f"Error {response.status_code} fetching {file_link}")
            return ""
    except Exception as e:
        print(f"Error fetching filing at {file_link}: {e}")
        return ""

def extract_item1_business(text: str) -> str:
    """
    Extract the 'Item 1. Business' section from a filing text.

    Args:
        text (str): Filing document text.

    Returns:
        The extracted 'Item 1. Business' section or an empty string if not found.
    """
    pattern = r'ITEM\s+1\s*\.?\s*BUSINESS.*?(?=ITEM\s+1A\s*\.?\s*RISK\s+FACTORS)'
    matches = re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return matches[0] if matches else ""

def extract_ai_sentences(text: str) -> list:
    """
    Extract sentences from text that mention 'Artificial Intelligence'.

    Args:
        text (str): Filing document text.

    Returns:
        List of sentences containing the term 'Artificial Intelligence'.
    """
    pattern_ai = re.compile(r'artificial intelligence', flags=re.IGNORECASE)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s for s in sentences if pattern_ai.search(s)]

def process_filings_documents(filings_df: pd.DataFrame) -> dict:
    """
    Download, clean, and process filing documents for each accession number.

    Args:
        filings_df (DataFrame): DataFrame containing filings information.

    Returns:
        Dictionary mapping accession numbers to their filing text.
    """
    clean_docs = {}
    for idx, row in filings_df.iterrows():
        print(f"Processing filing {idx+1} of {len(filings_df)}")
        filing_text = get_filing_text(row["fileLink"])
        clean_docs[row["accessionNumber"]] = filing_text
    return clean_docs

def analyze_filings(filings_df: pd.DataFrame, headers_df: pd.DataFrame, clean_docs: dict) -> pd.DataFrame:
    """
    Analyze filings documents to extract AI-related sentences and enrich headers data.

    Args:
        filings_df (DataFrame): Original filings DataFrame.
        headers_df (DataFrame): Enriched header data.
        clean_docs (dict): Dictionary of filing texts.

    Returns:
        Updated headers DataFrame with an AI flag.
    """
    # Extract "Item 1. Business" from each filing.
    item1_data = {acc: extract_item1_business(text) for acc, text in clean_docs.items()}
    if clean_docs:
        sample_acc = list(clean_docs.keys())[0]
        print("\nExample snippet of 'Item 1. Business':")
        print(item1_data[sample_acc][:500])
    else:
        print("No filings processed for Item 1 extraction.")
    
    # Extract sentences containing "Artificial Intelligence".
    ai_sentences = {acc: extract_ai_sentences(text) for acc, text in clean_docs.items()}
    if any(len(sents) > 0 for sents in ai_sentences.values()):
        for acc, sentences in ai_sentences.items():
            if sentences:
                print(f"\n=== Accession Number: {acc} ===")
                for sentence in sentences:
                    print("•", sentence)
    else:
        print("No documents mention 'Artificial Intelligence' by that exact phrase.")
    
    # Add AI_Flag to headers_df: 1 if AI sentences found, else 0.
    headers_df["AI_Flag"] = headers_df["AccessionNumber"].apply(
        lambda acc: 1 if len(ai_sentences.get(acc, [])) > 0 else 0
    )
    return headers_df

def main():
    # Set up working directory.
    set_working_directory(WORKING_DIR)
    
    # --- PART 1: Query 10-K Filings via SEC-API --- #
    query_api = QueryApi(api_key=API_KEY)
    filings_df = query_filings(query_api, QUERY_STRING, DESIRED_COUNT, PAGE_SIZE)
    
    # --- PART 1(b): Enrich Header Information --- #
    headers_df = enrich_header_data(filings_df)
    
    # --- PART 1(c): Geographic Visualization – State-Level Heatmap --- #
    state_counts = headers_df[headers_df["State"] != ""].groupby("State").size().reset_index(name="Count")
    print("State counts:")
    print(state_counts)
    create_state_heatmap(state_counts, "Number of Firms by State (Headquarters)")
    
    # --- PART 2: Download, Clean, and Process Filing Documents --- #
    clean_docs = process_filings_documents(filings_df)
    
    # --- PART 2(b) & 2(c): Extract 'Item 1. Business' and AI-related Sentences --- #
    headers_df = analyze_filings(filings_df, headers_df, clean_docs)
    
    # Aggregate by state: total filings and filings mentioning AI.
    state_agg = headers_df[headers_df["State"] != ""].groupby("State").agg(
        Total_Filings=("AccessionNumber", "count"),
        AI_Filings=("AI_Flag", "sum")
    ).reset_index()
    print(state_agg)
    create_state_heatmap(state_agg, "Number of Filings and Filings Mentioning 'Artificial Intelligence'")

if __name__ == '__main__':
    main()
