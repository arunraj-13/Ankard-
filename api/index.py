# api/index.py
from flask import Flask

app = Flask(__name__)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    # If this works, you will see this message in your browser.
    return "<h1>Success! Your Vercel server is running.</h1><p>You can now proceed to the next step.</p>"

# This is the entry point Vercel will use.
# The 'app' variable must be accessible here.