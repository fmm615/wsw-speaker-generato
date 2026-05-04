#!/usr/bin/env python3
"""
WSW Speaker Post — Zapier Webhook Server
Receives POST from Zapier, downloads speaker image from Dropbox,
generates post, uploads to Google Drive.

Deploy on Render:
  Build command:  pip install -r requirements.txt
  Start command:  gunicorn webhook_server:app
"""

import os, io, json, tempfile, traceback
from pathlib import Path
from flask import Flask, request, jsonify
from generate_speaker_post import generate
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account

app = Flask(__name__)

# ── ENV VARIABLES (set these in Render) ────────────────────────────────────────
WEBHOOK_SECRET    = os.environ.get("WEBHOOK_SECRET", "")
GDRIVE_FOLDER_ID  = os.environ.get("GDRIVE_FOLDER_ID", "")
GDRIVE_CREDS_JSON = os.environ.get("GDRIVE_CREDS_JSON", "")

BASE_DIR = Path(__file__).parent


def get_drive_service():
    creds_info = json.loads(GDRIVE_CREDS_JSON)
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)


def normalize_dropbox_url(url: str) -> str:
    """
    Convert Dropbox shared/preview URL to a direct download URL.
    Zapier gives URLs like: https://www.dropbox.com/s/xxx/file.jpg?dl=0
    We need:                 https://www.dropbox.com/s/xxx/file.jpg?dl=1
    """
    if "dropbox.com" in url:
        url = url.replace("?dl=0", "?dl=1")
        url = url.replace("&dl=0", "&dl=1")
        if "dl=" not in url:
            url += "?dl=1"
    return url


def download_image(url: str) -> str:
    """Download image to a temp file. Returns temp file path."""
    url  = normalize_dropbox_url(url)
    resp = requests.get(url, timeout=30, allow_redirects=True)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "jpeg" in content_type or "jpg" in content_type:
        suffix = ".jpg"
    elif "png" in content_type:
        suffix = ".png"
    else:
        suffix = ".jpg"  # safe default

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(resp.content)
    tmp.close()
    return tmp.name


def upload_to_drive(image_path: str, filename: str) -> str:
    """Upload generated post PNG to Google Drive. Returns shareable link."""
    service       = get_drive_service()
    file_metadata = {"name": filename, "parents": [GDRIVE_FOLDER_ID]}

    with open(image_path, "rb") as f:
        media = MediaIoBaseUpload(io.BytesIO(f.read()), mimetype="image/png")

    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink"
    ).execute()

    # Make readable by anyone with link
    service.permissions().create(
        fileId=uploaded["id"],
        body={"role": "reader", "type": "anyone"}
    ).execute()

    return uploaded.get("webViewLink", "")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/generate", methods=["POST"])
def webhook():
    # Auth check
    if WEBHOOK_SECRET:
        token = request.headers.get("X-Webhook-Secret", "")
        if token != WEBHOOK_SECRET:
            return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)

    # Validate
    missing = [f for f in ["image_url", "name", "title"] if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    image_url = data["image_url"]
    name      = data["name"].upper()
    title     = data["title"]
    role      = data.get("role", "Speaker")

    tmp_input = tmp_output = None

    try:
        # 1. Download from Dropbox
        tmp_input  = download_image(image_url)

        # 2. Generate post
        tmp_output = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        generate(tmp_input, role, name, title, tmp_output)

        # 3. Upload to Drive
        safe_name = name.replace(" ", "_").lower()
        filename  = f"wsw_speaker_{safe_name}.png"
        drive_url = upload_to_drive(tmp_output, filename)

        return jsonify({
            "status":    "success",
            "speaker":   name,
            "drive_url": drive_url,
            "filename":  filename
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        for f in [tmp_input, tmp_output]:
            if f and Path(f).exists():
                Path(f).unlink()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"WSW Webhook Server running on port {port}")
    app.run(host="0.0.0.0", port=port)
