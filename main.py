import os
from api.index import app

if __name__ == "__main__":
    # For local testing, use the port provided by GCP or default to 8080
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
