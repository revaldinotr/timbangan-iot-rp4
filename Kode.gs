var ss = SpreadsheetApp.openById('1IWkRpkNki8l-rDPSrlVHDvJvYp-LOXUR8RdXTc00iZ0');
var sheet = ss.getSheetByName('Sheet1');

function doGet(e) {
  if (!e.parameter || e.parameter == 'undefined') {
    return ContentService.createTextOutput("Data tidak ditemukan");
  }

  // Mengambil waktu saat ini (Timestamp)
  var now = new Date();
  var timeZone = SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
  var timestamp = Utilities.formatDate(now, timeZone, "yyyy-MM-dd HH:mm:ss");
  
  // Menangkap parameter dari URL ESP32
  var berat = e.parameter.berat; 
  //var jenis = e.parameter.jenis;

  var nextRow = sheet.getLastRow() + 1;
  
  // Mengisi baris baru di Google Sheet sesuai format tabel di foto
  sheet.getRange("A" + nextRow).setValue(timestamp);
  sheet.getRange("B" + nextRow).setValue(berat);
  //sheet.getRange("C" + nextRow).setValue(jenis);
  
  return ContentService.createTextOutput("Data berhasil dikirim ke Google Sheet");
}
