# SEC Filings & Insider Trading Analysis  

## Overview  
This repo has two Python scripts that pull SEC filings and analyze them. The first script focuses on **10-K filings**, extracting key sections and tracking mentions of **Artificial Intelligence**. The second script looks at **insider trading (Form 4s)**, tracking officer transactions and sell trends.  

---

## Scripts  

### 1️⃣ `sec_api_analysis.py`  
Pulls **10-K filings** using SEC-API, enriches them with company details, and analyzes **text** for key sections. Also creates **state-level visualizations** of filings.  

**What it does:**  
✔ Queries SEC-API for **10-K filings** from 2023  
✔ Extracts **"Item 1. Business"** section  
✔ Checks for **mentions of Artificial Intelligence**  
✔ Enriches data with **company state, SIC, and metadata**  
✔ Generates **state heatmaps** of filings  

**Run it:**  
```sh
python sec_api_analysis.py
```

**Setup:**  
- Install dependencies:  
  ```sh
  pip install requests pandas plotly beautifulsoup4 sec-api
  ```
- Add your **SEC-API key** and **User-Agent** in `constants.py`:  
  ```python
  API_KEY = "your_api_key"
  USER_AGENT = "Your Name (your_email@example.com)"
  ```

---

### 2️⃣ `sec_scrape_analysis.py`  
Tracks **officer transactions from Form 4 filings** and visualizes insider sell trends.  

**What it does:**  
✔ Pulls **Form 4 filings** for insider trading  
✔ Extracts **officer titles, transaction dates, and buy/sell actions**  
✔ Tracks **sell trends ("D" transactions)**  
✔ Creates **bar charts** of officer sales over time  

**Run it:**  
```sh
python sec_scrape_analysis.py
```

**Setup:**  
- Install dependencies:  
  ```sh
  pip install requests pandas matplotlib
  ```

---

## Example Output  

### 📍 State Heatmap of 10-K Filings  
![](example_heatmap.png)  

### 🔍 AI Mentions in Filings  
```
=== Accession Number: 0001234567-23-000001 ===
• "Our company is investing heavily in artificial intelligence for data processing."
• "We believe artificial intelligence will enhance our automation capabilities."
```

### 📈 Insider Trading Trends  
![](example_insider_trades.png)  

---

## Project Structure  
```
📂 sec-filings-analysis
│── sec_scrape_analysis.py   # Form 4 insider trading analysis
│── sec_api_analysis.py       # 10-K filings & textual analysis
│── constants.py                   # API key & user agent
│── README.md                      # Project documentation
```

---

## 🔧 Customization  

### 🎯 Change SEC Queries  
Edit the `QUERY_STRING` inside `sec_scrape_analysis.py`:  
```python
QUERY_STRING = 'formType:("10-K") AND filedAt:[2022-01-01 TO 2022-12-31]'
```
Change **form types** or **date ranges** as needed.  

### 🔄 Analyze a Different Company  
Modify the **CIK** in `sec_api_analysis.py` to target a different company:  
```python
TARGET_CIK = 1411579  # AMC Entertainment
```

---

## License  
Open-source under the [MIT License](LICENSE).  

---

## Contact  
**Author:** Ryan Loveless  
📧 Email: rylo5252@colorado.edu  
💡 Open to contributions or suggestions!
```
