function importFilteredFromSourceWithConfirm() {
  const ui = SpreadsheetApp.getUi();

  const message =
    'Этот скрипт:\n' +
    '1) Подтянет данные из внешней таблицы "Потребность Набор Оффлайн 2026".\n' +
    '2) Отфильтрует строки, где в столбце I указано "Актуально".\n' +
    '3) Оставит только те строки, где город в столбце C входит в список на листе "Настройки" в диапазоне A2:A100.\n' +
    '4) Полностью очистит лист "Импорт" и запишет в него только выбранные столбцы (A, B, C, F, I, J, L, N, S, T).\n\n' +
    'Продолжить выполнение скрипта?';

  const result = ui.alert(
    'Подтверждение импорта',
    message,
    ui.ButtonSet.YES_NO
  );

  if (result !== ui.Button.YES) {
    ui.alert('Выполнение скрипта отменено.');
    return;
  }

  importFilteredFromSource(); // вызывает основную функцию
}

function importTariffsWithConfirm() {
  const ui = SpreadsheetApp.getUi();

  const message =
    'Этот скрипт:\n' +
    '1) Подтянет данные из внешней таблицы "Тарифы для исполнителей".\n' +
    '2) Отфильтрует строки по городам из листа "Настройки" (A2:A100).\n' +
    '3) Полностью очистит лист "Тарифы" и запишет в него только столбцы A-H.\n\n' +
    'Продолжить выполнение скрипта?';

  const result = ui.alert(
    'Подтверждение импорта',
    message,
    ui.ButtonSet.YES_NO
  );

  if (result !== ui.Button.YES) {
    ui.alert('Выполнение скрипта отменено.');
    return;
  }

  importTariffsFromSource(); // основная функция
}


function importFilteredFromSource() {
  // --- НАСТРОЙКИ ---
  const sourceUrl = 'https://docs.google.com/spreadsheets/d/1EnTdvscFVebcxDvGNCymaEHOZUsI1jWjR9DWqHdHcGQ/edit?gid=1223398234#gid=1223398234';
  const sourceSheetName = 'Потребность Набор Оффлайн 2026';
  const sourceRangeA1 = 'A1:U2000';          // как в IMPORTRANGE
  const targetSheetName = 'Импорт';         // куда писать результат
  const settingsSheetName = 'Настройки';    // откуда брать список городов
  const citiesRangeA1 = 'A2:A100';          // города столбиком

  // --- ЧТЕНИЕ ИСТОЧНИКА ---
  const sourceSs = SpreadsheetApp.openByUrl(sourceUrl);
  const sourceSheet = sourceSs.getSheetByName(sourceSheetName);
  const allValues = sourceSheet.getRange(sourceRangeA1).getValues(); // 2D-массив

  if (allValues.length === 0) return;

  const headers = allValues[0];
  const data = allValues.slice(1); // без заголовков

  // --- ЧТЕНИЕ СПИСКА ГОРОДОВ ИЗ Настройки!A2:A100 ---
  const thisSs = SpreadsheetApp.getActiveSpreadsheet();
  const settingsSheet = thisSs.getSheetByName(settingsSheetName);
  const citiesRange = settingsSheet.getRange(citiesRangeA1).getValues(); // 2D (N×1)

  // Преобразуем в 1D‑массив, убирая пустые значения
  const cities = citiesRange
    .flat()                      // [v1, v2, ...]
    .map(c => String(c).trim())
    .filter(c => c !== '');

  // --- ИНДЕКСАЦИЯ СТОЛБЦОВ (0‑based) ---
  // A=0, B=1, C=2, F=5, I=8, J=9, L=11, N=13, S=18, T=19
  const COL_A = 0;
  const COL_B = 1;
  const COL_C = 2;
  const COL_F = 5;
  const COL_I = 8;
  const COL_J = 9;
  const COL_L = 11;
  const COL_N = 13;
  const COL_S = 18;
  const COL_T = 19;

  // --- ФИЛЬТРАЦИЯ ---
  const filtered = data
    .filter(row => row[COL_I] === 'Актуально') // столбец I
    .filter(row => cities.length === 0 || cities.includes(String(row[COL_C]))); // столбец C

  // --- ФОРМИРУЕМ РЕЗУЛЬТАТ (заголовки + данные) ---
  const result = [];
  result.push([
    headers[COL_A],
    headers[COL_B],
    headers[COL_C],
    headers[COL_F],
    headers[COL_I],
    headers[COL_J],
    headers[COL_L],
    headers[COL_N],
    headers[COL_S],
    headers[COL_T]
  ]);

  filtered.forEach(row => {
    result.push([
      row[COL_A],
      row[COL_B],
      row[COL_C],
      row[COL_F],
      row[COL_I],
      row[COL_J],
      row[COL_L],
      row[COL_N],
      row[COL_S],
      row[COL_T]
    ]);
  });

  // --- ВЫГРУЗКА В ЦЕЛЕВОЙ ЛИСТ ---
  const targetSheet = thisSs.getSheetByName(targetSheetName);
  targetSheet.clearContents();
  if (result.length > 0) {
    targetSheet
      .getRange(1, 1, result.length, result[0].length)
      .setValues(result);
  }
}

const SERVICE_MAPPING = {
  "Услуга продавца за прилавком": "Услуга продавца за прилавок",
  "Услуга по прессовке ВТС": "Услуги по прессовке ВТС"
};

function importTariffsFromSource() {
  // --- НАСТРОЙКИ ---
  const sourceUrl = 'https://docs.google.com/spreadsheets/d/18dfKE7Zqt8qgs5SpfeHeiEoCVvLhyTzrdkee_kFFlIg';
  const sourceSheetName = 'Лист1';      // лист с тарифами в исходной таблице
  const sourceRangeA1 = 'A1:H2000';     // тянем диапазон пошире, но будем искать по именам столбцов
  const targetSheetName = 'Тарифы';     // наш лист назначения
  const settingsSheetName = 'Настройки';
  const citiesRangeA1 = 'A2:A100';      // список городов

  // --- ЧТЕНИЕ ИСТОЧНИКА ---
  const sourceSs = SpreadsheetApp.openByUrl(sourceUrl);
  const sourceSheet = sourceSs.getSheetByName(sourceSheetName);
  const allValues = sourceSheet.getRange(sourceRangeA1).getValues();

  if (allValues.length < 2) return;

  // Строка 2 — это заголовки, строка 3 и далее — данные
  const headers = allValues[1];        // вторая строка (индекс 1)
  const data = allValues.slice(2);     // начиная с третьей (индекс 2)

  // --- ДИНАМИЧЕСКИЙ ПОИСК СТОЛБЦОВ ---
  // Нам нужно найти индексы для: "Город", "Услуга" (или "Должность")
  // Остальные столбцы берем как есть по порядку A-H.

  // Ищем индекс колонки с услугой
  let serviceColIndex = headers.indexOf("Услуга");
  if (serviceColIndex === -1) serviceColIndex = headers.indexOf("Должность");

  // Ищем индекс колонки с городом (для фильтрации)
  const cityColIndex = headers.indexOf("Город"); // Обычно это колонка А (0)

  // --- ЧТЕНИЕ СПИСКА ГОРОДОВ ИЗ Настройки!A2:A100 ---
  const thisSs = SpreadsheetApp.getActiveSpreadsheet();
  const settingsSheet = thisSs.getSheetByName(settingsSheetName);
  const citiesRange = settingsSheet.getRange(citiesRangeA1).getValues();

  const cities = citiesRange
    .flat()
    .map(c => String(c).trim())
    .filter(c => c !== '');

  // --- ФИЛЬТРАЦИЯ И ОБРАБОТКА ---
  const result = [];
  
  data.forEach(row => {
    // 1. Фильтрация по городу
    const rowCity = cityColIndex > -1 ? String(row[cityColIndex]).trim() : "";
    if (cities.length > 0 && !cities.includes(rowCity)) {
       return; // Пропускаем, если города нет в списке
    }

    // 2. Исправление названия услуги
    if (serviceColIndex > -1) {
      let serviceName = String(row[serviceColIndex]).trim();
      if (SERVICE_MAPPING[serviceName]) {
        row[serviceColIndex] = SERVICE_MAPPING[serviceName];
      }
    }

    // 3. Берем первые 8 колонок (A-H)
    result.push(row.slice(0, 8));
  });

  // --- ВЫГРУЗКА В ЦЕЛЕВОЙ ЛИСТ ---
  const targetSheet = thisSs.getSheetByName(targetSheetName);
  
  // Проверяем, есть ли уже шапка на листе
  const lastRow = targetSheet.getLastRow();
  
  if (lastRow === 0) {
    // Если лист пустой - записываем шапку и данные
    const fullResult = [headers.slice(0, 8), ...result];
    if (fullResult.length > 0) {
      targetSheet.getRange(1, 1, fullResult.length, fullResult[0].length).setValues(fullResult);
    }
  } else {
    // Если шапка уже есть - очищаем только данные и записываем новые
    if (lastRow > 1) {
      targetSheet.deleteRows(2, lastRow - 1); // Удаляем старые данные
    }
    if (result.length > 0) {
      targetSheet.getRange(2, 1, result.length, result[0].length).setValues(result);
    }
  }
}
