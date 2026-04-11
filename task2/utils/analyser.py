from sklearn.pipeline import Pipeline


SENTIMENT_META = {
    "positive": {"color": "green",  "score": 1},
    "negative": {"color": "red",    "score": -1},
    "neutral":  {"color": "gray",   "score": 0},
}


def analyse_posts(posts: list[dict], model: Pipeline) -> list[dict]:
    """
    Run sentiment prediction on a list of Reddit posts.

    Args:
        posts: List of dicts with keys title, summary, link.
        model: Trained sklearn Pipeline.

    Returns:
        Same list enriched with sentiment, color, and score keys.
    """
    results = []
    for post in posts:
        text = post["title"] + " " + post["summary"]
        sentiment = model.predict([text])[0]
        meta = SENTIMENT_META[sentiment]
        results.append({
            **post,
            "sentiment": sentiment,
            "color": meta["color"],
            "score": meta["score"],
        })
    return results
