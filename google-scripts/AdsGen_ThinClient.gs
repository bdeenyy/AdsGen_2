/**
 * AdsGen 2.0 - Google Sheets Thin Client
 * 
 * Этот скрипт устанавливается в вашу Google Таблицу и позволяет
 * отправлять данные на обработку в новый сервис воркеров.
 */

const API_BASE_URL = "http://YOUR_SERVER_IP:8000"; // Замените на IP вашего сервера (или туннель)

/**
 * Создает меню при открытии таблицы
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('🚀 AdsGen 2.0')
      .addItem('📥 Отправить текущий лист на импорт', 'triggerImport')
      .addSeparator()
      .addItem('🔄 Запустить генерацию (Batch)', 'triggerBatch')
      .addItem('📄 Сформировать XML для Авито', 'triggerXmlExport')
      .addSeparator()
      .addItem('⚙️ Настройки API', 'showSettings')
      .addToUi();
}

/**
 * Отправляет данные текущего листа напрямую в API (JSON Push)
 * Не требует настройки Google Cloud Console или API ключей.
 */
function triggerImport() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getActiveSheet();
  
  // Получаем все данные из листа
  const data = sheet.getDataRange().getValues();
  if (data.length < 2) {
    SpreadsheetApp.getUi().alert('❌ Лист пуст.');
    return;
  }

  // Превращаем в массив объектов (ключи из первой строки)
  const headers = data[0];
  const rows = data.slice(1).map(row => {
    let obj = {};
    headers.forEach((header, i) => {
      obj[header] = row[i];
    });
    return obj;
  });
  
  const options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(rows),
    muteHttpExceptions: true
  };
  
  try {
    const response = UrlFetchApp.fetch(`${API_BASE_URL}/import/json`, options);
    const result = JSON.parse(response.getContentText());
    
    if (response.getResponseCode() === 200) {
      SpreadsheetApp.getUi().alert(`✅ Данные отправлены напрямую!\nID задачи: ${result.task_id}\n\nВоркеры начали обработку.`);
    } else {
      SpreadsheetApp.getUi().alert(`❌ Ошибка API: ${result.detail || 'Неизвестная ошибка'}`);
    }
  } catch (e) {
    SpreadsheetApp.getUi().alert(`❌ Ошибка подключения: ${e.message}\nПроверьте API_BASE_URL (через меню Настройки).`);
  }
}

/**
 * Запускает пакетную генерацию
 */
function triggerBatch() {
  const options = {
    method: 'post',
    muteHttpExceptions: true
  };
  
  const response = UrlFetchApp.fetch(`${API_BASE_URL}/generate/batch?limit=50`, options);
  const result = JSON.parse(response.getContentText());
  
  if (response.getResponseCode() === 200) {
    SpreadsheetApp.getUi().alert(`🚀 Запущена генерация для ${result.triggered || 'новых'} объявлений.`);
  } else {
    SpreadsheetApp.getUi().alert(`❌ Ошибка: ${result.detail}`);
  }
}

/**
 * Запускает экспорт XML
 */
function triggerXmlExport() {
  const options = {
    method: 'post',
    muteHttpExceptions: true
  };
  
  const response = UrlFetchApp.fetch(`${API_BASE_URL}/publish/xml`, options);
  const result = JSON.parse(response.getContentText());
  
  if (response.getResponseCode() === 200) {
    SpreadsheetApp.getUi().alert(`📄 Экспорт запущен. Файл будет готов через минуту.`);
  } else {
    SpreadsheetApp.getUi().alert(`❌ Ошибка: ${result.detail}`);
  }
}

function showSettings() {
  const ui = SpreadsheetApp.getUi();
  const result = ui.prompt('Настройка API', 'Введите URL вашего API (например, туннель tuna.am или IP:8000):', ui.ButtonSet.OK_CANCEL);
  
  if (result.getSelectedButton() == ui.Button.OK) {
    const newUrl = result.getResponseText();
    // В реальном сценарии тут можно сохранить в PropertiesService
    ui.alert('Настройки (визуально) обновлены. В коде скрипта нужно обновить переменную API_BASE_URL.');
  }
}
