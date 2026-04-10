import feedparser
from urllib.parse import quote
from datetime import datetime

from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

# -----------------------
# Minimal training data (required for Logistic Regression)
# -----------------------
train_texts = [
    "I love this", "This is amazing", "very good experience",
    "I hate this", "this is bad", "worst experience ever",
    "it is okay", "not great not bad"
]

train_labels = [
    "positive", "positive", "positive",
    "negative", "negative", "negative",
    "neutral", "neutral"
]

# -----------------------
# Build ML model (TF-IDF + Logistic Regression)
# -----------------------
model = Pipeline([
    ("tfidf", TfidfVectorizer(stop_words="english")),
    ("clf", LogisticRegression(max_iter=1000))
])

model.fit(train_texts, train_labels)

# -----------------------
# Reddit input
# -----------------------
topic = input("Enter topic: ")
encoded_topic = quote(topic)

url = f"https://www.reddit.com/r/all/search.rss?q={encoded_topic}"
feed = feedparser.parse(url)

rows = []

# -----------------------
# Process posts
# -----------------------
for entry in feed.entries[:100]:
    title = entry.title
    summary = entry.get("summary", "")
    link = entry.link

    text = title + " " + summary

    sentiment = model.predict([text])[0]

    if sentiment == "positive":
        color = "green"
        score = 1
    elif sentiment == "negative":
        color = "red"
        score = -1
    else:
        color = "gray"
        score = 0

    rows.append(f"""
    <tr>
        <td><a href="{link}" target="_blank">{title}</a></td>
        <td>{summary}</td>
        <td style="color:{color}; font-weight:bold">{sentiment}</td>
        <td>{score}</td>
    </tr>
    """)

# -----------------------
# HTML output
# -----------------------
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Reddit Sentiment Analysis - {topic}</title>
    <style>
        body {{
            font-family: Arial;
            margin: 20px;
            background: #f5f5f5;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
            vertical-align: top;
        }}
        th {{
            background: #222;
            color: white;
        }}
        tr:nth-child(even) {{
            background: #f2f2f2;
        }}
    </style>
</head>
<body>

<h1>Reddit Sentiment Analysis (TF-IDF + Logistic Regression)</h1>
<p><b>Topic:</b> {topic}</p>
<p><b>Generated:</b> {datetime.now()}</p>

<table>
<tr>
<th>Title</th>
<th>Summary</th>
<th>Sentiment</th>
<th>Score</th>
</tr>

{''.join(rows)}

</table>

</body>
</html>
"""

with open("reddit_sentiment.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("Saved: reddit_sentiment.html")