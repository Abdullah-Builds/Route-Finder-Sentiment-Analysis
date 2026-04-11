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


def build_model() -> Pipeline:
    """Build and train the TF-IDF + Logistic Regression pipeline."""
    # -----------------------
    # Build ML model (TF-IDF + Logistic Regression)
    # -----------------------
    model = Pipeline([
        ("tfidf", TfidfVectorizer(stop_words="english")),
        ("clf", LogisticRegression(max_iter=1000))
    ])
    model.fit(train_texts, train_labels)
    return model
