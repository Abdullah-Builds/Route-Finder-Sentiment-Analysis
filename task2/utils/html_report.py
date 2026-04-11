from datetime import datetime


def build_html_report(topic: str, results: list[dict]) -> str:
    """
    Build the full HTML report string from analysed posts.

    Args:
        topic: The search topic used.
        results: List of enriched post dicts (title, summary, link,
                 sentiment, color, score).

    Returns:
        HTML string.
    """
    rows = []
    for r in results:
        rows.append(f"""
    <tr>
        <td><a href="{r['link']}" target="_blank">{r['title']}</a></td>
        <td>{r['summary']}</td>
        <td style="color:{r['color']}; font-weight:bold">{r['sentiment']}</td>
        <td>{r['score']}</td>
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
    return html_content


def save_html_report(html_content: str, filepath: str = "reddit_sentiment.html") -> None:
    """Write HTML content to a file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Saved: {filepath}")
