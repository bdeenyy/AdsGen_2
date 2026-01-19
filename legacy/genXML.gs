/**
 * Генерирует XML для всех объявлений на листе 'Работа-Вакансии'
 */
function generateXML() {
  processXMLData(false); // false = обрабатывать все строки
}

/**
 * ТЕСТОВАЯ ФУНКЦИЯ: Генерирует XML только для первой вакансии
 */
function generateXMLTest() {
  processXMLData(true); // true = только первая строка
}

/**
 * Основная логика обработки данных и формирования XML
 */
function processXMLData(isTest) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("Работа-Вакансии");
  
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Ошибка: не найден лист 'Работа-Вакансии'");
    return;
  }
  
  // Получаем названия полей из строки 2
  const fieldNames = sheet.getRange(2, 1, 1, 47).getValues()[0];
  
  // Получаем данные начиная с 5 строки
  const lastRow = sheet.getLastRow();
  if (lastRow < 5) {
    SpreadsheetApp.getUi().alert("Нет данных для генерации XML");
    return;
  }
  
  const numRows = isTest ? 1 : lastRow - 4;
  const data = sheet.getRange(5, 1, numRows, 47).getValues();
  
  // Начинаем формировать XML
  let xml = '<Ads formatVersion="3" target="Avito.ru">\n';
  
  // Обрабатываем строки
  for (let i = 0; i < data.length; i++) {
    const row = data[i];
    if (!row[0]) continue;
    
    xml += buildAdXml(row, fieldNames);
  }
  
  xml += '</Ads>';
  
  const fileName = isTest ? "Работа-Вакансии-ТЕСТ.xml" : "Работа-Вакансии.xml";
  saveXmlToFile(xml, fileName);
  
  const count = isTest ? 1 : data.filter(r => r[0]).length;
  SpreadsheetApp.getUi().alert("XML файл успешно создан!\nФайл: " + fileName + "\nОбработано строк: " + count);
}

/**
 * Формирует XML блок <Ad> для одной строки
 */
function buildAdXml(row, fieldNames) {
  let adXml = '\t<Ad>\n';
  
  for (let j = 0; j < 47; j++) {
    const fieldName = fieldNames[j];
    if (!fieldName) continue;
    
    let value = (row[j] || "").toString();
    
    // 🎨 СПЕЦИАЛЬНАЯ ЛОГИКА ДЛЯ ИЗОБРАЖЕНИЙ (Images)
    if (fieldName === "Images") {
      const urls = value.split(" | ").map(url => url.trim()).filter(url => url !== "");
      adXml += `\t\t<Images>\n`;
      for (const url of urls) {
        adXml += `\t\t\t<Image url="${escapeXml(url)}"/>\n`;
      }
      adXml += `\t\t</Images>\n`;
      continue;
    }
    
    // 💰 СПЕЦИАЛЬНАЯ ЛОГИКА ДЛЯ ЗАРПЛАТЫ (SalaryRange)
    if (fieldName === "SalaryRange") {
      const parts = value.split("|").map(p => p.trim()).filter(p => p !== "");
      if (parts.length >= 2) {
        adXml += `\t\t<SalaryRange>\n`;
        adXml += `\t\t\t<From>${escapeXml(parts[0])}</From>\n`;
        adXml += `\t\t\t<To>${escapeXml(parts[1])}</To>\n`;
        adXml += `\t\t</SalaryRange>\n`;
      } else if (parts.length === 1) {
        // Если только одно число, можно вывести как обычное поле или только From
        adXml += `\t\t<SalaryRange>\n`;
        adXml += `\t\t\t<From>${escapeXml(parts[0])}</From>\n`;
        adXml += `\t\t</SalaryRange>\n`;
      }
      continue;
    }
    
    // 📋 ЛОГИКА ДЛЯ СПИСКОВ (Option)
    if (value.includes(" | ")) {
      const options = value.split(" | ").map(opt => opt.trim());
      adXml += `\t\t<${fieldName}>\n`;
      for (const option of options) {
        adXml += `\t\t\t<Option>${escapeXml(option)}</Option>\n`;
      }
      adXml += `\t\t</${fieldName}>\n`;
    } else {
      // Обычное значение
      adXml += `\t\t<${fieldName}>${escapeXml(value)}</${fieldName}>\n`;
    }
  }
  
  adXml += '\t</Ad>\n';
  return adXml;
}


// Функция для экранирования специальных символов XML
function escapeXml(unsafe) {
  return unsafe.replace(/[<>&'"]/g, function (c) {
    switch (c) {
      case '<': return '&lt;';
      case '>': return '&gt;';
      case '&': return '&amp;';
      case '\'': return '&apos;';
      case '"': return '&quot;';
    }
  });
}


// Функция для сохранения XML файла в Google Drive
function saveXmlToFile(xmlContent, fileName) {
  const folder = DriveApp.getRootFolder();
  const files = folder.getFilesByName(fileName);
  
  if (files.hasNext()) {
    const file = files.next();
    file.setContent(xmlContent);
  } else {
    folder.createFile(fileName, xmlContent);
  }
}


// ✅ Предварительный просмотр XML для первой записи
function previewXML() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("Работа-Вакансии");
  
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Ошибка: не найден лист 'Работа-Вакансии'");
    return;
  }
  
  const fieldNames = sheet.getRange(2, 1, 1, 47).getValues()[0];
  const lastRow = sheet.getLastRow();
  
  if (lastRow < 5) {
    SpreadsheetApp.getUi().alert("Нет данных для генерации XML");
    return;
  }
  
  const data = sheet.getRange(5, 1, 1, 47).getValues();
  let xml = '<Ads formatVersion="3" target="Avito.ru">\n';
  xml += buildAdXml(data[0], fieldNames);
  xml += '\t<!-- ... остальные объявления ... -->\n';
  xml += '</Ads>';
  
  const htmlOutput = HtmlService
    .createHtmlOutput('<pre style="white-space: pre-wrap; word-wrap: break-word; font-family: monospace;">' + 
                      escapeHtml(xml) + 
                      '</pre>')
    .setWidth(800)
    .setHeight(600);
  
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'Предварительный просмотр XML (первая запись)');
}


// Функция для экранирования HTML
function escapeHtml(unsafe) {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
