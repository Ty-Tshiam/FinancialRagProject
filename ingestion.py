import requests
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentContentFormat, AnalyzeResult
import os
import json
import re
import process_module 

#Configuration & Global Variables
DOWNLOAD_DIR = "reports_archive"
AZURE_MARKDOWNS = "azure_output"
OUTPUT_DIR = "clean_reports"

def find_reports(START_YEAR : int, END_YEAR : int) -> dict:
    # --- Configuration ---
    COMPANY_TICKER = "TD"
    # The base URL is now just up to the common PDF folder.
    BASE_URL = "https://www.td.com/content/dam/tdcom/canada/about-td/pdf/"

    # Define the range of years and quarters to target
    QUARTERS = ["q1", "q2", "q3"] 
    Q4_QUARTER = "q4"

    # --- Function to Find a Valid Report URL ---

    def find_report_url(full_url):
        """
        Checks if a URL is valid and accessible.
        
        Returns: The URL if it's valid (HTTP 200), or None on failure (404, etc.).
        """
        # Add a User-Agent header so the site does not block the request
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        try:
            # Use HEAD request for a quick check before downloading content
            head_response = requests.head(full_url, headers=headers, allow_redirects=True, timeout=5)
            if head_response.status_code != 200:
                return None # File doesn't exist at this URL
            return full_url

        except requests.exceptions.RequestException:
            # Gracefully handle download errors (e.g., connection timeout, 403 Forbidden)
            return None

    # ----------------------------------------------------
    # 2. Generate URLs and Find Reports
    # ----------------------------------------------------

    print(f"--- Starting Report Search for {COMPANY_TICKER} ({START_YEAR}-{END_YEAR}) ---")
    found_reports = {}
    found_quarters = set()
    attempted_urls = set() # To track and skip redundant checks

    for year in range(START_YEAR, END_YEAR + 1):
        for q_tag in QUARTERS + [Q4_QUARTER]:
            
            quarter_name = q_tag.upper() # Q1, Q2, Q3, Q4

            # Standardized final filename tag for the RAG pipeline (e.g., TD_2025_Q3.pdf)
            new_filename_tag = f"{COMPANY_TICKER}_{year}_{quarter_name}.pdf"
            
            # List of potential file names to check for this specific year/quarter
            possible_urls = []
            
            # --- Pattern 1: Nested (Most common for recent quarters) ---
            # Example: .../quarterly-results/2025/q3/q3-2025-report-to-shareholders-en.pdf
            if q_tag != Q4_QUARTER:
                # Q1, Q2, Q3 have messy names in the nested folder
                nested_path = f"quarterly-results/{year}/{q_tag}/"
                possible_urls.extend([
                    # Primary QX-YYYY name (like Q3 2025 example)
                    BASE_URL + nested_path + f"{q_tag}-{year}-report-to-shareholders-en.pdf",
                    # Secondary YYYY-QX name (like Q1 2025 example)
                    BASE_URL + nested_path + f"{year}-{q_tag}-reports-shareholders-en.pdf"
                ])
            
            else: # Q4 is the Annual Report (and uses a slightly simpler nested path)
                nested_path_q4 = f"quarterly-results/{year}/{q_tag}/"
                # The Q4 Report to Shareholders is the Annual Report PDF
                possible_urls.extend([
                    # Standard nested path
                    BASE_URL + nested_path_q4 + f"{year}-annual-report-en.pdf",
                    # Variation with just year folder and "-e.pdf" suffix
                    BASE_URL + f"quarterly-results/{year}/" + f"{year}-annual-report-e.pdf",
                    # 2022 Variation: Different path and name
                    f"https://www.td.com/content/dam/tdcom/canada/about-td/for-investors/investor-relations/ar{year}-Complete-Report.pdf"
                ])

            # --- Patterns for Q1, Q2, Q3 ---
            if q_tag != Q4_QUARTER:
                quarter_number = q_tag[1] # "1", "2", or "3"
                possible_urls.extend([
                    # Pattern: Flat structure (e.g., .../pdf/2023-q1-report-to-shareholders-en.pdf)
                    BASE_URL + f"{year}-{q_tag}-report-to-shareholders-en.pdf",
                    # Pattern: Semi-Nested (e.g., .../quarterly-results/2023/2023-q2-report-to-shareholders-en.pdf)
                    BASE_URL + f"quarterly-results/{year}/" + f"{year}-{q_tag}-report-to-shareholders-en.pdf",
                    # 2022 Q1 Variation: Uppercase Q, underscores, _F_EN suffix
                    BASE_URL + f"quarterly-results/{year}/" + f"{year}-Q{quarter_number}_Report_to_Shareholders_F_EN.pdf",
                    # 2022 Q3 Variation: lowercase q, dashes, -f-en suffix
                    BASE_URL + f"quarterly-results/{year}/" + f"{year}-{q_tag}-report-to-shareholders-f-en.pdf"
                ])

            
            # --- EXECUTION: Find the first valid URL for the quarter ---
            is_found = False
            for url in possible_urls:
                if url in attempted_urls:
                    continue
                attempted_urls.add(url)
                
                found_url = find_report_url(url)
                
                if found_url:
                    print(f"✅ Found: {new_filename_tag} (at {found_url.split(BASE_URL)[-1]})")
                    found_reports[new_filename_tag] = found_url
                    found_quarters.add((year, quarter_name))
                    is_found = True
                    break # Move to the next quarter once a successful download is made
            
            if not is_found:
                print(f"--- FAILED to find: {new_filename_tag} ---")

    print("\n----------------------------------------------------------------------")
    print(f"**Search Complete.** Found {len(found_reports)} reports.")
    print("Found Report URLs:")
    for url in found_reports:
        print(f"- {url}")

    return found_reports

def download_reports(reports : dict):

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    for filename, url in reports.items():
        local_path = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(local_path):
            print(f"⏭️  Skipping existing file: {filename}")
            continue
        
        try:
            print(f"⬇️  Downloading: {filename} from {url}")
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an error for bad responses
            
            with open(local_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ Downloaded: {filename}")

        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to download {filename} from {url}. Error: {e}")

def analyze_documents(reports : dict):
    # [START analyze_documents_output_in_markdown]
    endpoint = os.environ["DOCUMENTINTELLIGENCE_ENDPOINT"]
    key = os.environ["DOCUMENTINTELLIGENCE_API_KEY"]
    json_folder = "json_reports"
    os.makedirs(json_folder, exist_ok=True)
    os.makedirs(AZURE_MARKDOWNS, exist_ok=True)
    
    document_intelligence_client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    
    for filename, url in reports.items():
        title = filename.split(".")[0]
        json_destination = os.path.join(json_folder, title)
        markdown_destination = os.path.join(AZURE_MARKDOWNS, title)

        print(f"⬇️  Transforming: {title}")

        poller = document_intelligence_client.begin_analyze_document(
            "prebuilt-layout",
            AnalyzeDocumentRequest(url_source=url),
            output_content_format=DocumentContentFormat.MARKDOWN
        )
        result: AnalyzeResult = poller.result()

        with open(f"{json_destination}.json", "w", encoding = "utf-8") as file:
            json.dump(result.as_dict(), file, indent=4)
            
        with open(f"{markdown_destination}.md", "w", encoding = "utf-8") as file:
            file.write(result.content)
        print(f"✅ Transformed: {title}")
    # [END analyze_documents_output_in_markdown]

    
if __name__ == "__main__":
    from dotenv import find_dotenv, load_dotenv
    load_dotenv(find_dotenv())

    reports = find_reports(2025, 2025)
    download_reports(reports)
    #analyze_documents(reports)
    process_module.main()
