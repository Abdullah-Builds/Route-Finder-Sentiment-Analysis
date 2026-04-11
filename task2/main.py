"""
CLI entry point — preserves the original task2.py behaviour.
Run: python main.py
"""
from model.sentiment_model import build_model
from scraper.reddit_scraper import fetch_reddit_posts
from utils.analyser import analyse_posts
from utils.html_report import build_html_report, save_html_report

# -----------------------
# Reddit input
# -----------------------
topic = input("Enter topic: ")

model = build_model()
posts = fetch_reddit_posts(topic)
results = analyse_posts(posts, model)
html_content = build_html_report(topic, results)
save_html_report(html_content)
