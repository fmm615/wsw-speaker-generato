#!/usr/bin/env python3
"""
WSW Speaker Post — Zapier Webhook Server
Receives POST from Zapier, downloads speaker image, generates post, uploads to Google Drive.

Deploy on any server (Railway, Render, VPS) with:
  pip install flask requests google-auth google-auth-httplib2 google-api-python-client pillow
  python3 webhook_server.py
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

# ── CONFIG — set these as environment variables on your server ──────────────────
WEBHOOK_SECRET      = os.environ.get("WEBHOOK_SECRET", "")           # optional auth token
GDRIVE_FOLDER_ID    = os.environ.get("GDRIVE_FOLDER_ID", "")         # output Drive folder ID
GDRIVE_CREDS_JSON   = os.environ.get("GDRIVE_CREDS_JSON", "")        # service account JSON string

BASE_DIR = Path(__file__).parent


def get_drive_service():
    creds_info = json.loads(GDRIVE_CREDS_JSON)
    creds = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)


def download_image(url: str) -> str:
    """Download image from URL to a temp file. Returns temp file path."""
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    suffix = ".jpg" if "jpeg" in resp.headers.get("content-type","") else ".png"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(resp.content)
    tmp.close()
    return tmp.name


def upload_to_drive(image_path: str, filename: str) -> str:
    """Upload generated post to Google Drive. Returns shareable URL."""
    service = get_drive_service()
    file_metadata = {
        "name": filename,
        "parents": [GDRIVE_FOLDER_ID]
    }
    with open(image_path, "rb") as f:
        media = MediaIoBaseUpload(io.BytesIO(f.read()), mimetype="image/png")
    
    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink"
    ).execute()

    # Make it readable by anyone with link
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
    # ── Optional auth check ──
    if WEBHOOK_SECRET:
        token = request.headers.get("X-Webhook-Secret", "")
        if token != WEBHOOK_SECRET:
            return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(force=True)

    # ── Validate required fields ──
    required = ["image_url", "name", "title"]
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    image_url = data["image_url"]
    name      = data["name"].upper()          # always uppercase
    title     = data["title"]
    role      = data.get("role", "Speaker")   # default to Speaker

    tmp_input  = None
    tmp_output = None

    try:
        # 1. Download speaker image
        tmp_input  = download_image(image_url)

        # 2. Generate post
        tmp_output = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        generate(tmp_input, role, name, title, tmp_output)

        # 3. Upload to Google Drive
        safe_name  = name.replace(" ", "_").lower()
        filename   = f"wsw_speaker_{safe_name}.png"
        drive_url  = upload_to_drive(tmp_output, filename)

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
