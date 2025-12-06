# PubMed AI Neurology Data Extractor (2015–2025)

This repository contains the full bibliometric extraction pipeline used to generate the dataset for the manuscript:

**“The Cognitive Crossroads: Bridging the Ethical Gap of Artificial Intelligence in Neurology.”**

The script collects, categorizes, and exports **PubMed-indexed artificial intelligence (AI) publications** from **2015–2025**, with a specific focus on **neurology subspecialties and neuroethics**. All data retrieved come from **publicly accessible PubMed APIs** and contain **no patient-level or proprietary data**.

---

## 🔍 Purpose

This script was designed to:
- Quantify the volume of AI-related publications across **11 major neurological categories**, plus neuroethics.
- Ensure **mutually exclusive categorization** using a priority ordering system to prevent double-counting.
- Generate the dataset used in the manuscript’s empirical analysis of the gap between **neurological AI research** and **neuroethical scholarship**.
- Compute the **total AI literature denominator** for proportion calculations.
- Export a complete, structured dataset for reproducibility and transparency.

---

## 🧠 How It Works — Overview

### 1. Build Core AI Query
The query includes both MeSH terms and TIAB keyword terms for:
- artificial intelligence
- machine learning
- deep learning
- neural networks
- NLP and related terms

This forms the **AI superset (Q-AI)** used across all categories.

### 2. Iterate Over 11 Neurology Subcategories
Defined in the script under `CATEGORY_SEARCH_STRINGS`, including:
- Stroke  
- Epilepsy  
- Dementia  
- Oncology  
- Movement Disorders  
- MS/Autoimmune  
- Neuromuscular Disorders  
- Brain Injury  
- Headache/Migraine  
- Spine Disorders  
- Ethics / Neuroethics

### 3. Mutually Exclusive Categorization Logic
The script enforces priority ordering:
- If a PMID appears in a higher-priority category, it is excluded from lower categories.
- This ensures **no overlap** across categories.

### 4. Metadata Extraction
For every PMID, the script retrieves:
- Title  
- Abstract  
- Publication year  
- MeSH terms  
- Category assignment  

### 5. Data Export
Outputs include:
- `final_categorized_articles.xlsx`
- `final_summary_counts.csv`
- Per-category PMID checkpoint files

All output is placed in:

```
pubmed_data_extractor_results/
```

---

## ⚙️ Configuration

Edit these:

```python
NCBI_API_KEY = "PLACE_API_KEY_HERE"
EMAIL = "PLACE_EMAIL_HERE"
START_YEAR = 2015
END_YEAR = 2025
```

---

## ▶️ How to Run

```bash
python pubmed_data_extractor.py
```

The script automatically:
- Creates required folders  
- Resumes from checkpoints  
- Prints progress summaries  
- Produces final datasets  

---

## 📁 Output Structure

```
pubmed_data_extractor_results/
├── Stroke/
├── Epilepsy/
├── ...
├── final_categorized_articles.xlsx
└── final_summary_counts.csv
```

---

## 📊 Reproducibility Notes

- All data originate from **PubMed**, a public database.
- Search strings, date ranges, and processing logic are fully transparent.
- No proprietary or clinical data are included.
- Anyone may re-run the script to reconstruct the dataset.

---

## 📚 Citation

If you use or adapt this script, please cite:

> El-Sherif Y. *The Cognitive Crossroads: Bridging the Ethical Gap of Artificial Intelligence in Neurology.* (AJOB Neuroscience, submitted 2025).

---

## 🛡️ License

MIT License.

---

## ✉️ Contact

**Yasir El-Sherif, MD, PhD**  
Staten Island University Hospital / Northwell Health  
Email: yelsherif@northwell.edu
