# Apps Script — Bridge to Google Sheets & Drive

This script receives a POST from the Raspberry Pi, saves the photo to Google Drive, and
writes one row of data to Google Sheets.

---

## Installation

### 1. Create a spreadsheet

Create a new spreadsheet at [sheets.google.com](https://sheets.google.com).
The header is created automatically by the script on the first submission:

```
Timestamps | Berat (Kg) | Jenis Sayur | Foto
```

### 2. Paste the script

**Extensions → Apps Script**, delete the default content, paste the entire contents of
`pb_to_sheets.gs`, then save.

### 3. Deploy

**Deploy → New deployment → Web app**

| Setting | Value |
|---|---|
| Execute as | **Me** |
| Who has access | **Anyone** |

Copy the **Deployment ID** from the resulting deploy URL:

```
https://script.google.com/macros/s/<THIS_IS_THE_DEPLOYMENT_ID>/exec
```

> "Anyone" is indeed required so the Raspberry Pi can send without an OAuth flow.
> Put the Deployment ID into the main.py script on the Raspberry Pi device.

---

## Photo Column Formula

The script inserts a combined formula so the cell shows a clickable thumbnail:

```
=HYPERLINK("https://drive.google.com/file/d/ID/view";
           IMAGE("https://drive.google.com/uc?export=download&id=ID";4;60;80))
```

Two important points:

1. **Semicolon argument separator (`;`)** — this follows the Indonesian locale. If your
   spreadsheet uses a locale that requires commas, change the separator in `pb_to_sheets.gs`.
2. **Different URLs for the two functions** — `HYPERLINK` uses `/view` (the Drive page),
   while `IMAGE` uses `uc?export=download` (the file directly). The `/view` URL
   will not display as an image.

The n8n workflow reads this column in FORMULA mode to extract the file ID.

---

## Google Quotas

| Limit | Value (free account) |
|---|---|
| Execution time | 6 minutes per invocation |
| URL Fetch calls | 20,000 / day |
| Drive storage | 15 GB shared across all services |
| Total runtime | 90 minutes / day |

Photos are compressed at JPEG quality 70 on the device side to save on upload
and storage quota.

---

## Changing the Sheet Name

Default: the active sheet. To target a specific tab:

```javascript
var SHEET_NAME = "Stok";
```
