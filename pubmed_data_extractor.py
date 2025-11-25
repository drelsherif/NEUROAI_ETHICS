import requests
import time
import pandas as pd
import datetime
from tqdm import tqdm
import os
import json
import xml.etree.ElementTree as ET
from collections import defaultdict 

# --- CONFIGURATION ---

# IMPORTANT: Replace with your actual NCBI API Key for faster performance and higher rate limits.
NCBI_API_KEY = "PLACE_API_KEY_HERE" 
EMAIL = "PLACE_EMAIL_HERE" # Required for E-Utilities usage

# The target years (inclusive)
START_YEAR = 2015
END_YEAR = 2025

# PubMed API settings
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
DB = "pubmed"
RETMAX = 10000 # Max allowed return limit per ESearch query
FETCH_BATCH_SIZE = 20 # Reduced for better reliability
# -------------------------------------------------------------

# --- CHECKPOINT/DATA DIRECTORY ---
OUTPUT_DIR = "pubmed_data_extractor_results"
# Ensure the root output directory exists immediately upon script start
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- 1. SEARCH STRINGS AND PRIORITY ORDER ---
# The search is divided into 11 mutually exclusive categories based on the user's priority.

# SPECIFIC NEUROMUSCULAR TERMS (TESTED: 285 articles vs 1084 broad terms)
SPECIFIC_NEUROMUSCULAR_QUERY = (
    '"Amyotrophic Lateral Sclerosis"[Mesh] OR '
    '"Muscular Atrophy, Spinal"[Mesh] OR '
    '"Muscular Dystrophy, Duchenne"[Mesh] OR '
    '"Muscular Dystrophy, Facioscapulohumeral"[Mesh] OR '
    '"Muscular Dystrophy, Myotonic"[Mesh] OR '
    '"Myasthenia Gravis"[Mesh] OR '
    '"Lambert-Eaton Myasthenic Syndrome"[Mesh] OR '
    '"Dermatomyositis"[Mesh] OR '
    '"Polymyositis"[Mesh] OR '
    '"Myositis, Inclusion Body"[Mesh] OR '
    '"Guillain-Barre Syndrome"[Mesh] OR '
    '"Polyradiculoneuropathy, Chronic Inflammatory Demyelinating"[Mesh] OR '
    '"Charcot-Marie-Tooth Disease"[Mesh] OR '
    '"Rhabdomyolysis"[Mesh] OR '
    '"Myotonic Disorders"[Mesh] OR '
    '"Periodic Paralysis"[Mesh]'
)

CATEGORY_SEARCH_STRINGS = {
    "Stroke": '"Stroke"[Mesh] OR "Cerebrovascular Disorders"[Mesh]',
    "Epilepsy": '"Epilepsy"[Mesh] OR "Seizures"[Mesh] OR "Status Epilepticus"[Mesh]',
    "Dementia": '"Dementia"[Mesh] OR "Alzheimer Disease"[Mesh] OR "Mild Cognitive Impairment"[Mesh]',
    "Oncology": '"Brain Neoplasms"[Mesh] OR "Spinal Cord Neoplasms"[Mesh] OR "Neurofibromatoses"[Mesh]',
    "Movement Disorders": '"Parkinson Disease"[Mesh] OR "Tremor"[Mesh] OR "Dystonia"[Mesh] OR "Huntington Disease"[Mesh]',
    "Autoimmune/MS": '"Multiple Sclerosis"[Mesh] OR "Neuroimmunomodulation"[Mesh] OR "Neuromyelitis Optica"[Mesh]',
    "Neuromuscular": SPECIFIC_NEUROMUSCULAR_QUERY,  # <-- UPDATED WITH TESTED SPECIFIC TERMS
    "Brain Injury": '"Traumatic Brain Injury"[Mesh] OR "Brain Injuries"[Mesh] OR "Concussion"[Mesh]',
    "Headaches/Migraines": '"Headache"[Mesh] OR "Migraine Disorders"[Mesh]',
    "Spine Disorders": '"Spinal Cord Diseases"[Mesh]',
    "Ethics": '("Neurosciences/ethics"[Mesh] OR "Bioethics"[Mesh] OR "Ethics, Medical"[Mesh]) OR "Neuroethics"[TIAB]',
}

# AI Superset Query (Q-AI) - Applied to every search
Q_AI_MEANS = '"Artificial Intelligence"[Mesh] OR "Machine Learning"[Mesh] OR "Deep Learning"[Mesh] OR "Neural Networks (Computer)"[Mesh]'
Q_AI_KEYWORDS = 'AI[TIAB] OR "deep learning"[TIAB] OR CNN[TIAB] OR RNN[TIAB] OR "natural language processing"[TIAB] OR NLP[TIAB]'
Q_AI_BASE = f"({Q_AI_MEANS}) OR ({Q_AI_KEYWORDS})"

# Full time range query
Q_TIME_RANGE = f'("{START_YEAR}/01/01"[DP] : "{END_YEAR}/12/31"[DP])'


# --- 2. CORE UTILITY FUNCTIONS ---

def get_api_params():
    """Returns base parameters for API calls."""
    params = {
        "db": DB,
        "tool": "PubMedAICollector",
        "email": EMAIL,
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    return params


def get_pubmed_count(query_term):
    """
    Makes an ESearch request optimized ONLY to get the total article COUNT.
    Returns the count as an integer.
    """
    params = get_api_params()
    params.update({
        "term": query_term,
        "retmax": 1,        # Only retrieve 1 record, since we only need the count
        "retmode": "json",
    })
    
    retries = 3
    for attempt in range(retries):
        try:
            response = requests.get(ESEARCH_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # The total count is reliable even if the retmax is low
            count = int(data['esearchresult']['count'])
            return count
        
        except requests.exceptions.RequestException as e:
            print(f"Count search failed (Attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
            else:
                return 0
        except json.JSONDecodeError:
            return 0
    return 0


def esearch_pmids(query_term):
    """Makes an ESearch request to get PMIDs for a query."""
    params = get_api_params()
    params.update({
        "term": query_term,
        "retmax": RETMAX,
        "retmode": "json",
    })
        
    retries = 3
    for attempt in range(retries):
        try:
            response = requests.get(ESEARCH_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            count = int(data['esearchresult']['count'])
            if count > RETMAX:
                 print(f"WARNING: Count ({count}) exceeds RETMAX ({RETMAX}). Monthly chunking failed for this time frame.")

            pmids = data['esearchresult'].get('idlist', [])
            return pmids
        
        except requests.exceptions.RequestException as e:
            print(f"ESearch failed (Attempt {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
            else:
                return []
    return []


def parse_medline_article(root, category):
    """Parses XML data from EFetch to extract Title, Abstract, Year, and MeSH terms."""
    articles_data = []
    
    # Iterate through all PubMedArticle tags in the XML response
    for pubmed_article in root.findall('./PubmedArticle'):
        pmid_element = pubmed_article.find('.//PMID')
        if pmid_element is None:
            continue
        pmid = pmid_element.text
        
        article_data = {
            'PMID': pmid,
            'Category': category,
            'Title': None,
            'Year': None,
            'Abstract': None,
            'MeSH_Terms': [],
        }
        
        # --- Extract Title ---
        title_element = pubmed_article.find('.//ArticleTitle')
        if title_element is not None:
            article_data['Title'] = title_element.text.strip() if title_element.text else "N/A"
            
        # --- Extract Publication Year ---
        pub_date_year = pubmed_article.find('.//PubDate/Year')
        if pub_date_year is not None:
            article_data['Year'] = pub_date_year.text
        else:
            # Fallback to MedlineDate if Year is missing (e.g., '2020 Fall')
            medline_date = pubmed_article.find('.//MedlineDate')
            if medline_date is not None and medline_date.text:
                 article_data['Year'] = medline_date.text.split()[0]
        
        # --- Extract Abstract ---
        abstract_parts = []
        for abstract_text in pubmed_article.findall('.//Abstract/AbstractText'):
            if abstract_text is not None and abstract_text.text:
                label = abstract_text.get('Label')
                text = abstract_text.text.strip()
                if label:
                    abstract_parts.append(f"({label}): {text}")
                else:
                    abstract_parts.append(text)
        article_data['Abstract'] = ' '.join(abstract_parts) if abstract_parts else "N/A"
        
        # --- Extract MeSH Terms ---
        mesh_terms = []
        mesh_heading_list = pubmed_article.find('.//MeshHeadingList')
        if mesh_heading_list is not None:
            for mesh_heading in mesh_heading_list.findall('./MeshHeading'):
                descriptor_name = mesh_heading.find('./DescriptorName')
                if descriptor_name is not None and descriptor_name.text:
                    term = descriptor_name.text.strip()
                    major_topic = descriptor_name.get('MajorTopicYN', 'N')
                    if major_topic == 'Y':
                        term += '*'  # Mark as major topic
                    mesh_terms.append(term)
                    
        article_data['MeSH_Terms'] = ' | '.join(mesh_terms) if mesh_terms else ""
        articles_data.append(article_data)
        
    return articles_data


def fetch_metadata(pmids, category):
    """Fetches metadata for a list of PMIDs using EFetch API with improved error handling."""
    if not pmids:
        return []
    
    all_articles = []
    failed_batches = []
    
    # Process PMIDs in batches to avoid API limits
    for i in tqdm(range(0, len(pmids), FETCH_BATCH_SIZE), desc=f"Fetching {category} metadata"):
        batch_pmids = pmids[i:i+FETCH_BATCH_SIZE]
        
        params = get_api_params()
        params.update({
            "id": ','.join(batch_pmids),
            "retmode": "xml",
            "rettype": "medline",
        })
        
        retries = 5  # Increased retries
        batch_success = False
        
        for attempt in range(retries):
            try:
                response = requests.get(EFETCH_URL, params=params, timeout=90)  # Longer timeout
                response.raise_for_status()
                
                # Parse the XML response
                root = ET.fromstring(response.content)
                batch_articles = parse_medline_article(root, category)
                all_articles.extend(batch_articles)
                batch_success = True
                break
                
            except requests.exceptions.RequestException as e:
                print(f"EFetch failed for batch {i//FETCH_BATCH_SIZE + 1} (Attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** (attempt + 1))  # Exponential backoff
                else:
                    print(f"Failed to fetch batch {i//FETCH_BATCH_SIZE + 1} after {retries} attempts - WILL RETRY")
                    failed_batches.append((i, batch_pmids))
            except ET.ParseError as e:
                print(f"XML parsing error for batch {i//FETCH_BATCH_SIZE + 1}: {e}")
                break
        
        # Throttle API calls more aggressively
        if batch_success:
            time.sleep(0.5)  # Slower rate
        else:
            time.sleep(2.0)  # Even slower after failures
    
    # Retry failed batches with smaller batch size
    if failed_batches:
        print(f"Retrying {len(failed_batches)} failed batches with smaller batch size...")
        for batch_index, batch_pmids in failed_batches:
            # Split failed batch into smaller chunks
            mini_batch_size = 5
            for j in range(0, len(batch_pmids), mini_batch_size):
                mini_batch = batch_pmids[j:j+mini_batch_size]
                
                params = get_api_params()
                params.update({
                    "id": ','.join(mini_batch),
                    "retmode": "xml",
                    "rettype": "medline",
                })
                
                try:
                    response = requests.get(EFETCH_URL, params=params, timeout=90)
                    response.raise_for_status()
                    root = ET.fromstring(response.content)
                    mini_articles = parse_medline_article(root, category)
                    all_articles.extend(mini_articles)
                    time.sleep(1.0)  # Slow rate for retries
                except Exception as e:
                    print(f"Mini-batch retry failed: {e}")
                    continue
        
    print(f"Fetched metadata for {len(all_articles)}/{len(pmids)} articles in {category}")
    return all_articles


def load_existing_pmids(category_names):
    """Loads existing PMIDs from checkpoint files to enable resuming."""
    all_collected_pmids = set()
    category_pmid_sets = defaultdict(set) 
    
    for category in category_names:
        safe_category_name = category.replace('/', '_').replace(' ', '_')
        category_dir = os.path.join(OUTPUT_DIR, safe_category_name)
        
        if os.path.exists(category_dir):
            for filename in os.listdir(category_dir):
                if filename.endswith('_pmid_checkpoint.csv'):
                    try:
                        df = pd.read_csv(os.path.join(category_dir, filename))
                        if 'PMID' in df.columns:
                            pmids = set(df['PMID'].astype(str))
                            all_collected_pmids.update(pmids)
                            category_pmid_sets[category].update(pmids)
                    except Exception as e:
                        print(f"Error loading checkpoint {filename}: {e}")

    # The initial exclusion set is simply ALL PMIDs loaded from disk.
    return all_collected_pmids, category_pmid_sets


def run_bibliometric_analysis():
    """
    Phase 1: Collects PMIDs using monthly chunks and priority exclusion.
    Phase 2: Fetches full metadata and saves to Excel.
    """
    
    category_names = list(CATEGORY_SEARCH_STRINGS.keys())
    
    # --- CALCULATE TOTAL AI LITERATURE COUNT (THE DENOMINATOR) ---
    total_ai_query = f"({Q_AI_BASE}) AND {Q_TIME_RANGE}"
    total_ai_count = get_pubmed_count(total_ai_query)
    print(f"\nTotal AI Literature (2015-2025, Q-AI Base): {total_ai_count:,} articles")
    
    # Test the specific neuromuscular query count
    neuromuscular_ai_query = f"({Q_AI_BASE}) AND ({SPECIFIC_NEUROMUSCULAR_QUERY}) AND {Q_TIME_RANGE}"
    neuromuscular_ai_count = get_pubmed_count(neuromuscular_ai_query)
    print(f"Specific Neuromuscular AI Literature: {neuromuscular_ai_count:,} articles (tested: 285)")
    
    # --- RESUME LOGIC INITIATION ---
    pmids_to_exclude, category_pmid_sets = load_existing_pmids(category_names)
    
    # Initialize dictionary for final results
    final_pmids_by_category = {} 
    
    print(f"Total PMIDs loaded from checkpoints: {len(pmids_to_exclude):,}")

    # CRITICAL WARNING CHECK
    if NCBI_API_KEY == "YOUR_NCBI_API_KEY":
        print("\n!!! WARNING: NCBI API KEY IS MISSING OR IS THE DEFAULT PLACEHOLDER !!!")
        print("    The script will execute at an extremely slow rate (3 requests/sec).")
        print("    Please replace 'YOUR_API_KEY' in the script for proper performance.")

    print("\n--- PHASE 1: PMID Collection (Mutually Exclusive) ---")
    
    # Loop through each category based on the defined priority order
    for i, category in enumerate(tqdm(category_names, desc="Categories", leave=True)):
        q_category = CATEGORY_SEARCH_STRINGS[category]
        category_pmids = category_pmid_sets[category] # Start with already collected PMIDs for this category
        
        # --- FIX 3: Sanitize category name for path creation ---
        safe_category_name = category.replace('/', '_').replace(' ', '_')
        category_dir = os.path.join(OUTPUT_DIR, safe_category_name)
        os.makedirs(category_dir, exist_ok=True)
        # ---------------------------------------------------
        
        print(f"\n-> Starting Priority {i+1}/{len(category_names)}: {category}")
        
        # Calculate exclusion set size for display. 
        exclusion_size_display = len(pmids_to_exclude) - len(category_pmids)
        print(f"   Excluding {exclusion_size_display:,} PMIDs found in HIGHER-priority categories.")

        # Flag to find the exact month to resume from
        resumed_search = False
        
        # The number of months in the target range (11 years * 12 months)
        total_months_to_process = (END_YEAR - START_YEAR + 1) * 12
        months_processed_for_category = 0

        # Iterating through the years and months
        for year in range(START_YEAR, END_YEAR + 1):
            for month in range(1, 13):
                
                # Check if this month has already been processed (Resume Logic)
                filename = os.path.join(category_dir, f"{safe_category_name}_{year}-{month:02d}_pmid_checkpoint.csv")
                
                if os.path.exists(filename):
                    months_processed_for_category += 1
                    if not resumed_search:
                         print(f"   Skipping processed month: {year}-{month:02d}")
                    resumed_search = True
                    continue
                
                # If we reach here, we are starting a new search chunk
                if not resumed_search:
                    print(f"   Resuming at: {year}-{month:02d}")
                    resumed_search = True

                # --- A. Define Monthly Time Chunk ---
                date_start = f"{year}/{month:02d}/01"
                date_end = f"{year}/{month:02d}/{31}" # Use 31 as a safe upper limit for the month
                date_range_query = f"(\"{date_start}\"[DP] : \"{date_end}\"[DP])"
                
                # Full PubMed query: (AI Base OR AI Keywords) AND (Category MeSH) AND (Date Range)
                full_query = f"({Q_AI_BASE}) AND ({q_category}) AND {date_range_query}"
                
                # --- B. Execute Search ---
                pmids = esearch_pmids(full_query)
                
                if not pmids:
                    time.sleep(0.35) # Still throttle even if 0 results
                    months_processed_for_category += 1
                    continue
                    
                # --- C. Apply Exclusion and Deduping Logic in Python ---
                new_pmids = []
                for pmid in pmids:
                    pmid_str = str(pmid)
                    # 1. Exclusion: Must not be in any higher-priority category set (pmids_to_exclude holds ALL prior PMIDs)
                    if pmid_str not in pmids_to_exclude:
                        # 2. Deduping: Must not have been processed in a previous month for this category (handled by category_pmids set)
                        if pmid_str not in category_pmids:
                            new_pmids.append(pmid_str)
                            category_pmids.add(pmid_str)
                            
                # --- D. Checkpoint Save (PMID only) ---
                if new_pmids:
                    # Save the checkpoint file
                    df = pd.DataFrame({'PMID': new_pmids})
                    df['Category'] = category
                    df.to_csv(filename, index=False)
                
                time.sleep(0.35) # Throttle ESearch calls
                months_processed_for_category += 1

        # Save the final unique PMIDs for the current category
        final_pmids_by_category[category] = list(category_pmids)
        
        # CRITICAL: Update the exclusion set for the next category loop
        pmids_to_exclude.update(category_pmids)
        
    print("\n--- PHASE 2: Metadata Fetching and Final Export ---")
    
    # --- Phase 2: Metadata Fetching and Consolidation ---
    all_final_articles = []
    
    # Fetch metadata for each category's collected PMIDs
    for category, pmid_list in final_pmids_by_category.items():
        if pmid_list:
            print(f"Fetching metadata for {category} ({len(pmid_list):,} articles)...")
            articles_data = fetch_metadata(pmid_list, category)
            all_final_articles.extend(articles_data)
        
    
    print("\n--- Saving Final Dataset ---")
    
    # --- Final Save to Excel ---
    if all_final_articles:
        final_df = pd.DataFrame(all_final_articles)
        
        # Reorder columns for better readability
        cols = ['PMID', 'Category', 'Year', 'Title', 'Abstract', 'MeSH_Terms']
        final_df = final_df[cols]
        
        excel_path = os.path.join(OUTPUT_DIR, 'final_categorized_articles.xlsx')
        final_df.to_excel(excel_path, index=False)
        
        print(f"SUCCESS: Final dataset saved to: {excel_path}")
        
        # Print Final Summary Counts
        print("\nFinal Categorized Counts (Mutually Exclusive):")
        summary_data = []
        
        # Add the Total AI Count (The Denominator) to the summary
        summary_data.append({'Category': "Total AI Literature (2015-2025)", 'Total Count': total_ai_count})
        print(f"  {'Total AI Literature (2015-2025)':<35}: {total_ai_count:,} articles")
        print("-" * 52)
        
        # Add individual Neurology category counts
        total_neurology_count = 0
        for category in category_names:
            count = len([d for d in all_final_articles if d['Category'] == category])
            total_neurology_count += count
            summary_data.append({'Category': category, 'Total Count': count})
            print(f"  {category:<35}: {count:,} articles")
            
        print("-" * 52)
        summary_data.append({'Category': "Total Neurology AI (Sum of 11 Categories)", 'Total Count': total_neurology_count})
        print(f"  {'Total Neurology AI (Mutually Exclusive)':<35}: {total_neurology_count:,} articles")

        summary_df = pd.DataFrame(summary_data)
        summary_path = os.path.join(OUTPUT_DIR, 'final_summary_counts.csv')
        summary_df.to_csv(summary_path, index=False)
        print(f"\nSummary counts saved to: {summary_path}")

    else:
        print("COMPLETED: No articles found matching the search criteria.")


if __name__ == "__main__":
    print("Starting PubMed AI Neurology Data Extractor...")
    print("=== UPDATED: Specific Neuromuscular Terms (285 articles tested) ===")
    run_bibliometric_analysis()