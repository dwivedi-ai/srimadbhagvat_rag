# Srimad Bhagavatam RAG Chatbot 🕉️

This is a Retrieval-Augmented Generation (RAG) based chatbot that answers questions strictly based on the purports of **Srila Prabhupada** from the **Srimad Bhagavatam**, sourced from [vedabase.io](https://vedabase.io/).

The system retrieves relevant purport chunks, builds a custom prompt, and passes it to a generative language model (Gemini) to produce informative, reference-cited answers.

---

## 🔍 Project Overview

### ✨ What it does

- Scrapes **Srimad Bhagavatam** purports from [vedabase.io](https://vedabase.io)
- Converts them into vector embeddings using `sentence-transformers`
- Stores those vectors using `ChromaDB` (persistent local vector DB)
- On a query, retrieves the top `k` most relevant purports
- Builds a strict prompt with the chunks
- Uses **Gemini 1.5 Flash** to generate a fact-based answer (no hallucinations)

### ⚙️ How it works

| Component                      | Description                                                                 |
|-------------------------------|-----------------------------------------------------------------------------|
| `scripts/scraping/fetch.py`   | Web scraper that downloads and saves purports from vedabase.io             |
| `scripts/indexing/vec_indexing.py` | Converts purports into sentence embeddings and stores them in Chroma       |
| `src/rag_pipeline.py`         | Core RAG logic: embedding, retrieval, prompt building, Gemini generation   |
| `src/api.py`                  | Flask-based API with `/` (UI) and `/query` (JSON endpoint)                 |
| `templates/index.html`        | Basic front-end form to interact with the chatbot                          |

---

## 🧪 Running Locally

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/srimadbhagvat_rag.git
cd srimadbhagvat_rag
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

In the root directory of the project, create a file named `.env`. This file will store the environment variables needed by the app.

Add the following lines to it:

GEMINI_API_KEY=your_google_api_key_here


Make sure you replace `your_google_api_key_here` with your actual Gemini API key.

---

### 4. Run the app

Once everything is set up, just run the app with:

python main.py


After it starts, open your browser and go to [http://localhost:5000](http://localhost:5000) to use the chatbot.
