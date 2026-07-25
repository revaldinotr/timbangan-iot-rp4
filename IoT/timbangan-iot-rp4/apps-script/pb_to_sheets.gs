/**
 * ============================================================
 *  Apps_Script_Timbangan.gs  —  VERSI FIX
 *  Formula IMAGE loadable + HYPERLINK clickable
 * ============================================================
 */

var FOLDER_NAME  = "Captures Data Sayur";
var SHEET_NAME   = "";          // kosong = sheet aktif
var THUMB_WIDTH  = 80;
var THUMB_HEIGHT = 60;

/**
 * ── KEAMANAN: Token Bersama ─────────────────────────────────────────────────
 * Web app yang di-deploy dengan akses "Anyone" adalah endpoint TULIS tanpa
 * autentikasi. Siapa pun yang mengetahui URL /exec dapat menyisipkan baris ke
 * Spreadsheet dan mengunggah berkas ke Google Drive Anda.
 *
 * Aktifkan token bersama untuk menutup celah ini:
 *   1. Buka Project Settings → Script Properties
 *   2. Tambahkan properti  SHARED_TOKEN  berisi string acak yang panjang
 *   3. Isi nilai yang sama pada GAS_SHARED_TOKEN di device/.env
 *
 * Token disimpan di Script Properties, BUKAN di dalam kode ini, sehingga berkas
 * ini tetap aman untuk di-commit ke repositori publik.
 *
 * Bila SHARED_TOKEN tidak diset, verifikasi dilewati agar tetap kompatibel
 * dengan pemasangan lama — tetapi endpoint Anda terbuka.
 */
function _tokenValid(payload) {
  var expected = PropertiesService
    .getScriptProperties()
    .getProperty("SHARED_TOKEN");

  if (!expected) { return true; }              // token belum diaktifkan
  var given = (payload && payload.token) || "";

  // Perbandingan waktu-tetap sederhana untuk mempersulit timing attack.
  if (given.length !== expected.length) { return false; }
  var diff = 0;
  for (var i = 0; i < expected.length; i++) {
    diff |= given.charCodeAt(i) ^ expected.charCodeAt(i);
  }
  return diff === 0;
}

function _tolak() {
  return ContentService
    .createTextOutput(JSON.stringify({ status: "ERROR", message: "Unauthorized" }))
    .setMimeType(ContentService.MimeType.JSON);
}


function doPost(e) {
  try {
    var payload   = JSON.parse(e.postData.contents);

    if (!_tokenValid(payload)) { return _tolak(); }

    var berat     = payload.berat      || "0.00";
    var jenis     = payload.jenis      || "";
    var filename  = payload.filename   || ("capture_" + new Date().getTime() + ".jpg");
    var imageData = payload.imageData  || "";
    var folder    = _getOrCreateFolder(payload.folderName || FOLDER_NAME);

    var fotoCell  = "";
    var fileId    = "";
    var fileUrl   = "";

    if (imageData) {
      var decoded = Utilities.base64Decode(imageData);
      var blob    = Utilities.newBlob(decoded, "image/jpeg", filename);
      var file    = folder.createFile(blob);
      file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);

      fileId  = file.getId();
      fileUrl = "https://drive.google.com/file/d/" + fileId + "/view";

      // ═══════════════════════════════════════════════════════════════
      //  FIX: Gunakan titik koma (;) dan URL direct download uc?export
      // ═══════════════════════════════════════════════════════════════
      var imageUrl = "https://drive.google.com/uc?export=download&id=" + fileId;
      fotoCell = '=HYPERLINK("' + fileUrl + '";IMAGE("' + imageUrl + '";4;' + THUMB_HEIGHT + ';' + THUMB_WIDTH + '))';
    }

    var ss    = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = SHEET_NAME ? ss.getSheetByName(SHEET_NAME) : ss.getActiveSheet();

    if (sheet.getLastRow() === 0) {
      _buatHeader(sheet);
    }

    var ts = Utilities.formatDate(
      new Date(),
      Session.getScriptTimeZone(),
      "yyyy-MM-dd HH:mm:ss"
    );

    var newRow = sheet.getLastRow() + 1;
    sheet.getRange(newRow, 1).setValue(ts);
    sheet.getRange(newRow, 2).setValue(parseFloat(berat));
    sheet.getRange(newRow, 3).setValue(jenis);

    if (fotoCell) {
      sheet.setRowHeight(newRow, THUMB_HEIGHT + 10);
      sheet.getRange(newRow, 4).setFormula(fotoCell);   // ← formula di-inject ke sel
    }

    return ContentService
      .createTextOutput(JSON.stringify({
        status   : "OK",
        timestamp: ts,
        fileUrl  : fileUrl,
        fileId   : fileId
      }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({
        status : "ERROR",
        message: err.message
      }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}


function doGet(e) {
  try {
    if (!_tokenValid({ token: e.parameter.token })) { return _tolak(); }

    var berat = e.parameter.berat || "0.00";
    var jenis = e.parameter.jenis || "";

    var ss    = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = SHEET_NAME ? ss.getSheetByName(SHEET_NAME) : ss.getActiveSheet();
    if (sheet.getLastRow() === 0) { _buatHeader(sheet); }

    var ts = Utilities.formatDate(
      new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss"
    );

    var newRow = sheet.getLastRow() + 1;
    sheet.getRange(newRow, 1).setValue(ts);
    sheet.getRange(newRow, 2).setValue(parseFloat(berat));
    sheet.getRange(newRow, 3).setValue(jenis);

    return ContentService
      .createTextOutput(JSON.stringify({ status: "OK", timestamp: ts, note: "GET-no-photo" }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: "ERROR", message: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}


// ── HELPER ────────────────────────────────────────────────────────────────────

function _buatHeader(sheet) {
  sheet.appendRow(["Timestamps", "Berat (Kg)", "Jenis Sayur", "Foto"]);
  var h = sheet.getRange(1, 1, 1, 4);
  h.setBackground("#FF0000");
  h.setFontColor("#FFFFFF");
  h.setFontWeight("bold");
  h.setHorizontalAlignment("center");
  sheet.setColumnWidth(4, THUMB_WIDTH + 20);
}

function _getOrCreateFolder(folderName) {
  var iter = DriveApp.getFoldersByName(folderName);
  if (iter.hasNext()) { return iter.next(); }
  return DriveApp.createFolder(folderName);
}


function testScript() {
  var dummyJpeg = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsL"
                + "DBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/"
                + "2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
                + "MjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFgAB"
                + "AQEAAAAAAAAAAAAAAAAABgUEB/8QAIRAAAQMEAgMAAAAAAAAAAAAAAQIDBAAFEQ"
                + "YSITH/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/"
                + "aAAwDAQACEQMRAD8Amml6xf6pd+BZWMs4QhJWpKQEpz3JPAHvS6KKA//2Q==";

  var fakePayload = {
    postData: {
      contents: JSON.stringify({
        berat    : "1.23",
        jenis    : "TestSayur",
        filename : "test_dummy.jpg",
        imageData: dummyJpeg,
        folderName: FOLDER_NAME
      })
    }
  };

  var result = doPost(fakePayload);
  Logger.log("Result: " + result.getContent());
  Logger.log("Cek Sheets dan folder Drive '" + FOLDER_NAME + "' untuk verifikasi.");
}
