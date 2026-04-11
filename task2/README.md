# Reddit Sentiment Analyser

TF-IDF + Logistic Regression sentiment analysis on Reddit posts, with a Streamlit frontend.

## Project Structure

```
reddit_sentiment_app/
│
├── app.py                    # Streamlit frontend
├── main.py                   # CLI entry point (original behaviour)
├── requirements.txt
│
├── model/
│   ├── __init__.py
│   └── sentiment_model.py    # Builds & trains the ML pipeline
│
├── scraper/
│   ├── __init__.py
│   └── reddit_scraper.py     # Fetches posts via Reddit RSS
│
└── utils/
    ├── __init__.py
    ├── analyser.py           # Runs predictions on posts
    └── html_report.py        # Builds & saves the HTML report
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Streamlit UI
```bash
streamlit run app.py
```

### CLI (original behaviour)
```bash
python main.py
```
