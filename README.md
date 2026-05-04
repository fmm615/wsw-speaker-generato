# WSW Speaker Post Generator

Automatically generates Women Shaping Wealth Summit speaker posts from a Zapier webhook.

## Files

| File | Purpose |
|------|---------|
| `generate_speaker_post.py` | Core image generation script |
| `webhook_server.py` | Flask server — receives Zapier calls |
| `wsw_background.png` | Galaxy background (fixed asset) |
| `wsw_logo_clean.png` | WSW logo with transparent bg (fixed asset) |
| `TT_Drugs_Trial_Bold.otf` | Font — speaker name |
| `TT_Drugs_Trial_Regular.otf` | Font — role, title, URL |

---

## Step 1 — Deploy the server (Render — free tier works)

1. Push this folder to a GitHub repo
2. Go to [render.com](https://render.com) → New Web Service → connect your repo
3. Set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn webhook_server:app`
4. Add these **Environment Variables** in Render:
   - `WEBHOOK_SECRET` → any random string (e.g. `wsw-zapier-2024`) — copy this, you'll need it in Zapier
   - `GDRIVE_FOLDER_ID` → the ID of your Google Drive output folder (from the URL: `drive.google.com/drive/folders/THIS_PART`)
   - `GDRIVE_CREDS_JSON` → the full JSON content of your Google service account key (see Step 2)
5. Deploy. Copy your server URL (e.g. `https://wsw-speaker-gen.onrender.com`)

---

## Step 2 — Google Drive service account

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use existing)
3. Enable **Google Drive API**
4. Go to IAM → Service Accounts → Create Service Account
5. Download the JSON key
6. Copy the full JSON content → paste as `GDRIVE_CREDS_JSON` env variable in Render
7. In Google Drive, right-click your output folder → Share → paste the service account email → Editor

---

## Step 3 — Google Drive input folder (for Zahra)

Create a folder in Drive called `WSW Speaker Images`. Inside it, create subfolders per speaker when needed. 
When Zahra receives a speaker image (email or otherwise), she drops it into this folder.

---

## Step 4 — Set up Zapier

### Trigger: New file in Google Drive folder

1. New Zap → Trigger: **Google Drive** → Event: **New File in Folder**
2. Select your `WSW Speaker Images` folder
3. Test trigger

### Action 1: Get speaker data from Google Sheets

1. Action: **Google Sheets** → Event: **Lookup Spreadsheet Row**
2. Lookup column: Speaker Name (match against filename or a naming convention)
3. Map: `name`, `title`, `role` columns

### Action 2: POST to your webhook

1. Action: **Webhooks by Zapier** → Event: **POST**
2. URL: `https://your-server.onrender.com/generate`
3. Payload type: `JSON`
4. Data:
   ```
   image_url  → {{Google Drive file URL from trigger}}
   name       → {{name from Sheets}}
   title      → {{title from Sheets}}
   role       → {{role from Sheets}}
   ```
5. Headers:
   ```
   X-Webhook-Secret → your WEBHOOK_SECRET value
   Content-Type     → application/json
   ```

### Action 3 (optional): Slack notification

1. Action: **Slack** → **Send Channel Message**
2. Message: `✅ Speaker post ready: {{name}} → {{drive_url}}`
3. Channel: your design team channel

---

## Naming convention (important)

For Zapier to match the Drive image to the correct row in Sheets, use a consistent filename when Zahra uploads:
- File named `firstname_lastname.jpg` → matches `Speaker Name` column in Sheets
- Or add a `Speaker ID` column to Sheets and use that as the folder/filename

---

## Manual usage (CLI)

```bash
python3 generate_speaker_post.py \
  --image path/to/speaker.jpg \
  --role "Judge" \
  --name "HAZLEEN AHMAD" \
  --title "Founder, Neuropower World" \
  --output output.png
```

---

## Output

- 1080×1350 PNG
- Saved to Google Drive output folder automatically
- Design team gets Slack notification with direct link
