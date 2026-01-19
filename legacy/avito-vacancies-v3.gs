// ═══════════════════════════════════════════════════════════════════════════// ============================================
// CONFIGURATION / НАСТРОЙКА
// ============================================
const TUNNEL_URL = "https://cvlo1j-45-8-146-39.ru.tuna.am";

// ГЕНЕРАТОР ВАКАНСИЙ AVITO (LOGIC)
// Использует данные из файла templates.gs
// ═══════════════════════════════════════════════════════════════════════════

// ============================================
// AI CONFIGURATION
// ============================================
const DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions";

const AI_MODELS = {
  deepseek: "deepseek-chat"
};

// Названия листов для Шага 1
const IMPORT_SHEET_NAME = "Импорт";
const OUTPUT_SHEET_NAME = "Вакансии";
const BATCH_SIZE = 50; // Размер пачки для сохранения

// Список допустимых городов
const ALLOWED_CITIES = [
  "Москва",
  "Московская область", 
  "Санкт-Петербург",
  "Ленинградская область",
  "Курск",
  "Орел",
  "Нижний Новгород"
];

/**
 * Вспомогательная функция для генерации заголовка по шаблонам (Variant 1)
 */
function generateTitleVariant1(profession, address, noExperience, payoutFrequency, index) {
  const template = TITLE_TEMPLATES[profession];
  if (!template) return profession;
  
  const baseIndex = index % template.base.length;
  const locationIndex = template.location.length > 0 ? index % template.location.length : -1;
  const experienceIndex = template.experience.length > 0 && noExperience ? 0 : -1;
  
  let title = template.base[baseIndex];
  if (locationIndex >= 0) title += " " + template.location[locationIndex];
  if (experienceIndex >= 0) title += " " + template.experience[experienceIndex];
  
  return title;
}

/**
 * Вспомогательная функция для генерации заголовка (Variant 2 - Advanced)
 */
function generateTitleVariant2(profession, address, noExperience, payoutFrequency, index) {
  const template = TITLE_TEMPLATES[profession];
  if (!template) return profession;
  
  const formats = [
    (base, loc, exp) => `${base}${loc ? " " + loc : ""}${exp ? " " + exp : ""}`,
    (base, loc, exp) => `${base}${exp ? " " + exp : ""}${loc ? " " + loc : ""}`,
    (base, loc, exp) => `${base}${loc ? ", " + loc : ""}${exp ? ", " + exp : ""}`,
    (base, loc, exp) => `${base}${exp ? " (" + exp + ")" : ""}${loc ? ", " + loc : ""}`,
  ];
  
  const baseIndex = index % template.base.length;
  const formatIndex = index % formats.length;
  const locationIndex = template.location.length > 0 ? (index + 1) % template.location.length : -1;
  const experienceIndex = template.experience.length > 0 && noExperience ? 0 : -1;
  
  const base = template.base[baseIndex];
  const location = locationIndex >= 0 ? template.location[locationIndex] : "";
  const experience = experienceIndex >= 0 ? template.experience[experienceIndex] : "";
  
  return formats[formatIndex](base, location, experience);
}

/**
 * Генерирует уникальное название объявления
 * Чередует варианты генерации для максимального разнообразия
 */
function generateUniqueTitle(profession, address, noExperience, payoutFrequency, rowIndex) {
  if (rowIndex % 2 === 0) {
    return generateTitleVariant1(profession, address, noExperience, payoutFrequency, rowIndex);
  } else {
    return generateTitleVariant2(profession, address, noExperience, payoutFrequency, rowIndex);
  }
}

/**
 * Генерирует уникальное описание объявления (фолбек)
 */
function generateDescription(profession, address, salary, title, rowIndex) {
  const template = DESCRIPTION_TEMPLATES[profession];
  if (!template) {
    return `<p><strong>${title}</strong></p><p>Приглашаем в нашу дружную команду! Удобный график, выплаты без задержек. Звоните или пишите прямо сейчас!</p>`;
  }

  const duty = template.duties[rowIndex % template.duties.length];
  const adv = template.advantages[rowIndex % template.advantages.length];
  
  return `
    <p><strong>${title}</strong></p>
    <p>Мы ищем ответственного сотрудника на позицию <strong>${profession}</strong> в наш магазин по адресу: ${address}.</p>
    <h3>Что нужно делать:</h3>
    ${duty}
    <h3>Наши преимущества:</h3>
    ${adv}
    <p>Звоните или пишите, мы ждем вас!</p>
  `.trim();
}

/**
 * Выбирает URL изображения для профессии
 * Если изображений нет, возвращает дефолтную ссылку (можно настроить)
 */
function getProfessionImage(profession, gender, age, notes) {
  // Теперь используем динамическую генерацию картинок через ИИ-туннель
  // с учетом рандомного пола, возраста и примечаний
  const result = generateImage(profession, gender, age, notes);
  
  if (result && result.startsWith("http")) {
    return result;
  }
  
  Logger.log(`Ошибка генерации картинки для ${profession}: ${result}`);
  
  // Фолбек
  return "https://www.avito.ru/static/images/profile/default_profile_140x140.png";
}

/**
 * Генерирует изображение для профессии и возвращает публичную ссылку.
 */
function generateImage(profession, gender, age, notes) {
  if (!profession) {
    return "Error: Profession is required";
  }

  // Переводим промт на английский перед отправкой в ComfyUI
  const enProfession = translateToEnglish(profession);
  const enNotes = notes ? translateToEnglish(notes) : null;

  Logger.log(`Генерация картинки: [RU: ${profession}, EN: ${enProfession}]`);
  if (notes) {
    Logger.log(`Заметки: [RU: ${notes}, EN: ${enNotes}]`);
  }

  const payload = {
    profession: enProfession,
    gender: gender || null,
    age: age || null,
    notes: enNotes
  };

  const options = {
    method: "POST",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
    timeout: 300000 // 5 minutes timeout for generation
  };

  try {
    const response = UrlFetchApp.fetch(TUNNEL_URL + "/generate", options);
    const statusCode = response.getResponseCode();
    const result = JSON.parse(response.getContentText());

    if (statusCode === 200 && result.success) {
      return result.image_url;
    } else {
      return "Error: " + (result.error || result.detail || "Unknown error");
    }
  } catch (e) {
    return "Error: " + e.message;
  }
}

/**
 * Переводит текст на английский язык с помощью DeepSeek.
 */
function translateToEnglish(text) {
  if (!text) return "";
  
  const prompt = `Translate the following text strictly to English. The text describes a job position or visual details for an image generation prompt. 
Respond ONLY with the translation, no explanations, no quotes.

Text to translate:
${text}`;

  const translated = AI_REQUEST(prompt, 500, 0.3);
  
  if (translated) {
    // Чистим возможные артефакты (кавычки и т.д. - ИИ иногда их лепит)
    return translated.replace(/^["']|["']$/g, "").trim();
  }
  
  Logger.log(`Ошибка перевода текста: ${text}. Используем оригинал.`);
  return text;
}

/**
 * Проверяет доступность сервера генерации.
 */
function checkServerHealth() {
  try {
    const response = UrlFetchApp.fetch(TUNNEL_URL + "/health", {
      muteHttpExceptions: true
    });
    const result = JSON.parse(response.getContentText());

    if (result.comfyui_available && result.yandex_disk_configured) {
      return "✅ Server is ready";
    } else if (!result.comfyui_available) {
      return "⚠️ ComfyUI not available";
    } else {
      return "⚠️ Yandex Disk not configured";
    }
  } catch (e) {
    return "❌ Server unavailable: " + e.message;
  }
}

/**
 * Получает список доступных профессий.
 */
function getAvailableProfessions() {
  try {
    const response = UrlFetchApp.fetch(TUNNEL_URL + "/professions", {
      muteHttpExceptions: true
    });
    const result = JSON.parse(response.getContentText());
    return result.professions;
  } catch (e) {
    return ["Error: " + e.message];
  }
}

/**
 * АВТОМАТИЗАЦИЯ: Запуск циклического триггера
 */
function startAutoProcessing() {
  stopAutoProcessing(); // Удаляем старые, если есть
  
  ScriptApp.newTrigger('autoFillVacancies')
    .timeBased()
    .everyMinutes(10) // Каждые 10 минут
    .create();
    
  SpreadsheetApp.getUi().alert("🚀 Авто-генерация запущена!\nСкрипт будет запускаться каждые 10 минут, пока не обработает все вакансии.");
}

/**
 * АВТОМАТИЗАЦИЯ: Остановка триггера
 */
function stopAutoProcessing() {
  const triggers = ScriptApp.getProjectTriggers();
  for (let i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'autoFillVacancies') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
}

/**
 * Воркер для триггера
 */
function autoFillVacancies() {
  const isMoreWorkLeft = fillVacanciesWork(true); // true = режим триггера
  
  if (!isMoreWorkLeft) {
    stopAutoProcessing();
    Logger.log("Все вакансии обработаны. Триггер остановлен.");
  }
}

function fillVacanciesWork(isAutoMode) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sourceSheet = ss.getSheetByName("Вакансии");
  const targetSheet = ss.getSheetByName("Работа-Вакансии");
  
  if (!sourceSheet || !targetSheet) {
    SpreadsheetApp.getUi().alert("Ошибка: не найден лист 'Вакансии' или 'Работа-Вакансии'");
    return;
  }
  
  // Получаем все данные из листа "Вакансии" начиная со 2 строки
  const lastRow = sourceSheet.getLastRow();
  if (lastRow < 2) {
    SpreadsheetApp.getUi().alert("Нет данных для обработки на листе 'Вакансии'");
    return;
  }
  
  // Проверка времени выполнения
  const startTime = new Date().getTime();
  const MAX_EXECUTION_TIME = 300000; // 5 минут (чтобы оставить запас до лимита в 6 минут)
  
  // Колонки на листе "Вакансии"
  const STATUS_COL = 12; // Столбец L для статуса (✅)
  
  // Проверяем наличие заголовка "Статус"
  if (sourceSheet.getRange(1, STATUS_COL).getValue() !== "Статус") {
    sourceSheet.getRange(1, STATUS_COL).setValue("Статус").setFontWeight("bold");
  }
  
  const sourceData = sourceSheet.getRange(2, 1, lastRow - 1, STATUS_COL).getValues(); // A-L
  
  let processedCount = 0;
  let skippedCount = 0;
  let unmappedPositions = new Set();
  let isStoppedByTimeout = false;
  
  // Обрабатываем каждую строку из исходных данных
  for (let i = 0; i < sourceData.length; i++) {
    // 1. Проверяем остаток времени перед каждой строкой
    if (new Date().getTime() - startTime > MAX_EXECUTION_TIME) {
      isStoppedByTimeout = true;
      break;
    }

    const row = sourceData[i];
    const sourceRowIndex = i + 2;
    
    // 2. Пропускаем пустые строки
    if (!row[0]) continue;
    
    // 3. Пропускаем уже обработанные (статус ✅)
    if (row[STATUS_COL - 1] === "✅") {
      skippedCount++;
      continue;
    }
    
    // 4. Пропускаем скрытые фильтром строки
    if (sourceSheet.isRowHiddenByFilter(sourceRowIndex)) {
      continue;
    }
    
    // Определяем текущую свободную строку для записи в "Работа-Вакансии"
    let targetNextRow = targetSheet.getLastRow() + 1;
    if (targetNextRow < 5) targetNextRow = 5;
    
    const newRow = new Array(47).fill(""); // 47 столбцов (A-AU)
    
    // Получаем должность из столбца D
    const originalPosition = row[3] ? row[3].trim() : "";
    const profession = POSITION_TO_PROFESSION[originalPosition];
    
    // Проверяем маппинг
    if (!profession) {
      unmappedPositions.add(originalPosition);
      continue; // Пропускаем строку если нет маппинга
    }
    
    // Определяем нужен ли опыт и адрес
    const noExperience = true; // по умолчанию требуется
    const address = (row[1] || "") + ", " + (row[2] || ""); // B + C
    const salary = "от 200 рублей/час";
    
    // A: Лист "Вакансии" столбик A
    newRow[0] = row[0];
    
    // B: Package
    newRow[1] = "Package";
    
    // C: Пусто
    newRow[2] = "";
    
    // D: Анастасия
    newRow[3] = "Анастасия";
    
    // E: 79082348946
    newRow[4] = "79082348946";
    
    // Получаем тип услуги из столбика I
    const service = row[8] ? String(row[8]).trim() : "";

    // Генерация параметров для картинки
    const gender = Math.random() > 0.5 ? "man" : "woman";
    const age = Math.floor(Math.random() * (45 - 20 + 1)) + 20;
    const rawNotes = row[4] ? String(row[4]).trim() : "";
    let notes = rawNotes ? `Ниже текст из примечания, возьми из него только осмысленный текст, относящийся к описанию внешности или контексту профессии: ${rawNotes}` : "";
    
    // Добавляем информацию об услуге в примечание для картинки, чтобы ИИ понимал контекст (например, наличие техники)
    if (service) {
      notes += (notes ? ". " : "") + `Контекст услуги: ${service}`;
    }

    // F: Images (Generated via AI)
    newRow[5] = getProfessionImage(profession, gender, age, notes || null);
    
    // G: Лист "Вакансии" столбик B + ", " + C
    newRow[6] = row[2];
    
    // H: По телефону и в сообщениях
    newRow[7] = "По телефону и в сообщениях";
    
    // I: Вакансии
    newRow[8] = "Вакансии";
    
    // J: Розничная и оптовая торговля
    newRow[9] = "Розничная и оптовая торговля";
    
    // K & Q: ГЕНЕРИРУЕМЫЙ КОНТЕНТ (TITLE & DESCRIPTION)
    const storeType = row[7] ? String(row[7]).trim() : "";
    const aiContent = generateAiVacancyContent(profession, address, salary, service, storeType);
    
    // K: СГЕНЕРИРОВАННОЕ УНИКАЛЬНОЕ НАЗВАНИЕ (TITLE)
    const generatedTitle = aiContent.title || generateUniqueTitle(profession, address, noExperience, "Каждый день", targetNextRow);
    newRow[10] = generatedTitle;
    
    // L: Полная
    newRow[11] = "Полная";
    
    // M: Гибкий
    newRow[12] = "Гибкий";
    
    // N: 3–4 дня | 5 дней | 6–7 дней
    newRow[13] = "3–4 дня | 5 дней | 6–7 дней";
    
    // O: 8 часов | 9–10 часов | 11–12 часов
    newRow[14] = "8 часов | 9–10 часов | 11–12 часов";
    
    // P: Без опыта
    newRow[15] = "Без опыта";
    
    // Q: ГЕНЕРИРУЕМОЕ ОПИСАНИЕ (DESCRIPTION)
    newRow[16] = aiContent.description || generateDescription(
      profession,
      address,
      salary,
      generatedTitle,
      targetNextRow
    );
    
    // R: Лист "Вакансии" столбик J | Лист "Вакансии" столбик K
    newRow[17] = row[9] + "| " + row[10];
    
    // S: за смену
    newRow[18] = "за смену";
    
    // T: Каждый день
    newRow[19] = "Каждый день";
    
    // U: На руки
    newRow[20] = "На руки";
    
    // V: Униформа | Парковка | Зоны отдыха | Обучение
    newRow[21] = "Униформа | Парковка | Зоны отдыха | Обучение";
    
    // W: Profession (MAPPED)
    newRow[22] = profession;
    
    // X: Старше 45 лет | С нарушениями здоровья | Для пенсионеров
    newRow[23] = "Старше 45 лет | С нарушениями здоровья | Для пенсионеров";
    
    // Y: Да
    newRow[24] = "Да";
    
    // Z: Трудовой договор | Договор ГПХ с ИП | Договор ГПХ с самозанятым | Договор ГПХ с физлицом
    newRow[25] = "Трудовой договор | Договор ГПХ с ИП | Договор ГПХ с самозанятым | Договор ГПХ с физлицом";
    
    // AA: Любые
    newRow[26] = "Любые";
    
    // AB: 18|65
    newRow[27] = "18|65";
    
    // AC: Россия
    newRow[28] = "Россия";
    
    // AD-AJ: Пусто
    for (let j = 29; j <= 35; j++) {
      newRow[j] = "";
    }
    
    // AK: Лист "Вакансии" столбик B + "_" + D + "_" + F
    newRow[36] = row[1] + "_" + row[3] + "_" + row[5];
    
    // AL: Нет
    newRow[37] = "Нет";
    
    // AM: Да
    newRow[38] = "Да";
    
    // AN: Email
    newRow[39] = "projectstroy-8@mail.ru";
    
    // AO: Проводить
    newRow[40] = "Проводить";
    
    // AP: Проектстрой-8
    newRow[41] = "Проектстрой-8";
    
    // AQ: Пусто
    newRow[42] = "";
    
    // AR: Лист "Вакансии" столбик K
    newRow[43] = row[10];
    
    // AS: Да
    newRow[44] = "Да";
    
    // AT: Активно
    newRow[45] = "Активно";
    
    // AU: Нет
    newRow[46] = "Нет";
    
    // 5. Записываем строку и отмечаем статус СРАЗУ
    targetSheet.getRange(targetNextRow, 1, 1, 47).setValues([newRow]);
    targetSheet.getRange(targetNextRow, 17, 1, 1).setWrapStrategy(SpreadsheetApp.WrapStrategy.CLIP);
    sourceSheet.getRange(sourceRowIndex, STATUS_COL).setValue("✅");
    
    processedCount++;
    
    // Периодически сбрасываем кэш в Google Sheets для видимости прогресса
    if (processedCount % 10 === 0) {
      SpreadsheetApp.flush();
    }
  }
  
  let finalMessage = "";
  if (isAutoMode) {
    // В автоматическом режиме не показываем алерты, только логи
    Logger.log(finalMessage);
    return isStoppedByTimeout; // Если остановились по таймауту, значит есть еще работа
  }

  SpreadsheetApp.getUi().alert(finalMessage);
  return isStoppedByTimeout;
}

/**
 * ТЕСТОВАЯ ФУНКЦИЯ: Генерирует только одну вакансию (первую из списка)
 * Используется для проверки формата XML и других полей
 */
function fillOneVacancyTest() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sourceSheet = ss.getSheetByName("Вакансии");
  const targetSheet = ss.getSheetByName("Работа-Вакансии");
  
  if (!sourceSheet || !targetSheet) {
    SpreadsheetApp.getUi().alert("Ошибка: не найден лист 'Вакансии' или 'Работа-Вакансии'");
    return;
  }
  
  // Берем только первую строку данных (после заголовка)
  const sourceData = sourceSheet.getRange(2, 1, 1, 11).getValues();
  
  if (!sourceData[0][0]) {
    SpreadsheetApp.getUi().alert("Первая строка на листе 'Вакансии' пуста");
    return;
  }
  
  // Определяем следующую свободную строку для записи
  let targetNextRow = targetSheet.getLastRow() + 1;
  if (targetNextRow < 5) targetNextRow = 5;
  
  const outputData = [];
  const row = sourceData[0];
  const newRow = new Array(47).fill("");
  
  const originalPosition = row[3] ? row[3].trim() : "";
  const profession = POSITION_TO_PROFESSION[originalPosition];
  
  if (!profession) {
    SpreadsheetApp.getUi().alert("Ошибка: должность '" + originalPosition + "' не найдена в маппинге templates.gs");
    return;
  }
  
  const noExperience = true;
  const address = (row[1] || "") + ", " + (row[2] || "");
  const salary = "от 200 рублей/час";
  
  newRow[0] = row[0];
  newRow[1] = "Package";
  newRow[3] = "Анастасия";
  newRow[4] = "79082348946";
  // Получаем тип услуги из столбика I (row[8])
  const service = row[8] ? String(row[8]).trim() : "";

  // Генерация параметров для картинки (Тест)
  const gender = Math.random() > 0.5 ? "man" : "woman";
  const age = Math.floor(Math.random() * (45 - 20 + 1)) + 20;
  const rawNotes = row[4] ? String(row[4]).trim() : "";
  let notes = rawNotes ? `Ниже текст из примечания, возьми из него только осмысленный текст, относящийся к описанию внешности или контексту профессии: ${rawNotes}` : "";
  
  if (service) {
    notes += (notes ? ". " : "") + `Контекст услуги: ${service}`;
  }

  newRow[5] = getProfessionImage(profession, gender, age, notes || null); // Чистая ссылка (XML сделает genXML.gs)
  newRow[6] = row[2];
  newRow[7] = "По телефону и в сообщениях";
  newRow[8] = "Вакансии";
  newRow[9] = "Розничная и оптовая торговля";
  // K & Q: ГЕНЕРИРУЕМЫЙ КОНТЕНТ (TITLE & DESCRIPTION)
  const storeType = row[7] ? String(row[7]).trim() : "";
  const aiContent = generateAiVacancyContent(profession, address, salary, service, storeType);

  // K: СГЕНЕРИРОВАННОЕ УНИКАЛЬНОЕ НАЗВАНИЕ (TITLE)
  const generatedTitle = aiContent.title || generateUniqueTitle(profession, address, noExperience, "Каждый день", 0);
  newRow[10] = generatedTitle;
  
  // L: Полная
  newRow[11] = "Полная";
  
  // M: Гибкий
  newRow[12] = "Гибкий";
  
  // N: 3–4 дня | 5 дней | 6–7 дней
  newRow[13] = "3–4 дня | 5 дней | 6–7 дней";
  
  // O: 8 часов | 9–10 часов | 11–12 часов
  newRow[14] = "8 часов | 9–10 часов | 11–12 часов";
  
  // P: Без опыта
  newRow[15] = "Без опыта";
  
  // Q: ГЕНЕРИРУЕМОЕ ОПИСАНИЕ (DESCRIPTION)
  newRow[16] = aiContent.description || generateDescription(profession, address, salary, generatedTitle, 0);
  newRow[17] = row[9] + "| " + row[10];
  newRow[18] = "за смену";
  newRow[19] = "Каждый день";
  newRow[20] = "На руки";
  newRow[21] = "Униформа | Парковка | Зоны отдыха | Обучение";
  newRow[22] = profession;
  newRow[23] = "Старше 45 лет | С нарушениями здоровья | Для пенсионеров";
  newRow[24] = "Да";
  newRow[25] = "Трудовой договор | Договор ГПХ с ИП | Договор ГПХ с самозанятым | Договор ГПХ с физлицом";
  newRow[26] = "Любые";
  newRow[27] = "18|65";
  newRow[28] = "Россия";
  newRow[36] = row[1] + "_" + row[3] + "_" + row[5];
  newRow[37] = "Нет";
  newRow[38] = "Да";
  newRow[39] = "projectstroy-8@mail.ru";
  newRow[40] = "Проводить";
  newRow[41] = "Проектстрой-8";
  newRow[43] = row[10];
  newRow[44] = "Да";
  newRow[45] = "Активно";
  newRow[46] = "Нет";
  
  outputData.push(newRow);
  const testRange = targetSheet.getRange(targetNextRow, 1, 1, 47);
  testRange.setValues(outputData);
  
  // Форматирование для теста
  targetSheet.getRange(targetNextRow, 17, 1, 1)
    .setWrapStrategy(SpreadsheetApp.WrapStrategy.CLIP);
  
  SpreadsheetApp.getUi().alert("Тестовая вакансия сгенерирована в строку " + targetNextRow + " листа 'Работа-Вакансии'");
}

/**
 * Синхронизирует удаленные вакансии
 * Если вакансия есть в "Вакансии" (статус ✅), но её нет в "Работа-Вакансии" по ID,
 * меняет статус на "🗑️" для повторной генерации
 */
function syncDeletedVacancies() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sourceSheet = ss.getSheetByName("Вакансии");
  const targetSheet = ss.getSheetByName("Работа-Вакансии");
  
  if (!sourceSheet || !targetSheet) {
    SpreadsheetApp.getUi().alert("Ошибка: не найден лист 'Вакансии' или 'Работа-Вакансии'");
    return;
  }
  
  // 1. Собираем все ID из "Работа-Вакансии" (столбец A)
  const targetLastRow = targetSheet.getLastRow();
  const targetIds = new Set();
  if (targetLastRow >= 5) {
    const targetData = targetSheet.getRange(5, 1, targetLastRow - 4, 1).getValues();
    targetData.forEach(r => { if (r[0]) targetIds.add(String(r[0]).trim()); });
  }
  
  // 2. Проверяем "Вакансии"
  const sourceLastRow = sourceSheet.getLastRow();
  if (sourceLastRow < 2) return;
  
  const STATUS_COL = 12; // L
  const sourceRange = sourceSheet.getRange(2, 1, sourceLastRow - 1, STATUS_COL);
  const sourceData = sourceRange.getValues();
  const statusesToUpdate = [];
  let foundDeleted = 0;
  
  for (let i = 0; i < sourceData.length; i++) {
    const id = String(sourceData[i][0]).trim();
    const status = sourceData[i][STATUS_COL - 1];
    
    // Если статус ✅, но ID нет в целевом листе
    if (status === "✅" && !targetIds.has(id)) {
      sourceSheet.getRange(i + 2, STATUS_COL).setValue("🗑️");
      foundDeleted++;
    }
  }
  
  if (foundDeleted > 0) {
    SpreadsheetApp.getUi().alert(`✅ Синхронизация завершена.\nНайдено и сброшено удаленных вакансий: ${foundDeleted}.\nТеперь вы можете снова запустить "Шаг 2", чтобы их перегенерировать.`);
  } else {
    SpreadsheetApp.getUi().alert("Синхронизация не выявила удаленных вакансий. Все ID на месте.");
  }
}

// ============================================
// AI MANAGEMENT & REQUESTS
// ============================================

function getCurrentProvider() {
  return "deepseek";
}

/**
 * Получает API ключ для DeepSeek
 */
function getApiKey() {
  return PropertiesService.getScriptProperties().getProperty("DEEPSEEK_API_KEY");
}

/**
 * Сохраняет API ключ DeepSeek
 */
function setApiKey(key) {
  PropertiesService.getScriptProperties().setProperty("DEEPSEEK_API_KEY", key);
}

/**
 * Возвращает информацию о состоянии ключа для UI
 */
function getKeysInfo() {
  const deepseekKey = getApiKey();
  
  return {
    deepseek: deepseekKey ? "✅ настроен" : "❌ не настроен"
  };
}

function AI_REQUEST(prompt, maxTokens, temperature) {
  const API_KEY = getApiKey();
  
  if (!API_KEY) {
    return null;
  }
  
  maxTokens = maxTokens || 2000;
  temperature = temperature !== undefined ? temperature : 0.7;
  
  const payload = {
    model: AI_MODELS.deepseek,
    messages: [{
      role: "user",
      content: prompt
    }],
    max_tokens: maxTokens,
    temperature: temperature
  };
  
  const options = {
    method: 'post',
    contentType: 'application/json',
    headers: { 'Authorization': `Bearer ${API_KEY}` },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  try {
    const response = UrlFetchApp.fetch(DEEPSEEK_API_URL, options);
    const responseCode = response.getResponseCode();
    
    if (responseCode !== 200) {
      Logger.log(`DeepSeek API ошибка ${responseCode}: ${response.getContentText()}`);
      return null;
    }
    
    const result = JSON.parse(response.getContentText());
    return result.choices[0].message.content.trim();
  } catch (e) {
    Logger.log(`Ошибка запроса к ИИ: ${e.message}`);
    return null;
  }
}

/**
 * Генерирует контент вакансии (Title + Description) с помощью AI
 */
function generateAiVacancyContent(profession, address, salary, service, storeType) {
  const template = DESCRIPTION_TEMPLATES[profession] || { duties: [], advantages: [] };
  
  // Маппинг типа магазина для ИИ
  let storeContext = "Магазин";
  if (storeType === "ГМ" || storeType === "ЦП") {
    storeContext = "Гипермаркет (крупный формат)";
  } else if (storeType === "МФ") {
    storeContext = "Магазин у дома / Супермаркет (малый формат)";
  }

  // Выбираем случайные фрагменты из шаблонов для вдохновения (если они есть)
  const randomDuty = template.duties.length > 0 
    ? template.duties[Math.floor(Math.random() * template.duties.length)] 
    : "";
  const randomAdv = template.advantages.length > 0 
    ? template.advantages[Math.floor(Math.random() * template.advantages.length)] 
    : "";

  const tones = ["Дружелюбный и заботливый", "Энергичный и драйвовый", "Профессиональный и лаконичный", "Теплый и человечный"];
  const randomTone = tones[Math.floor(Math.random() * tones.length)];

  const prompt = `Ты — опытный HR-копирайтер. Твоя задача — написать уникальное название и описание вакансии для Авито СТРОГО про указанную профессию.
  
КРИТИЧЕСКИЙ КОНТЕКСТ:
1. Тип объекта: "${storeContext}". Используй соответствующую терминологию (например, "в наш гипермаркет" или "в магазин у дома").
2. Специфика услуги: "${service || 'Не указана'}". 
   Если в услуге указано использование техники/оборудования или специфические условия — ОБЯЗАТЕЛЬНО отрази это. 

ДАННЫЕ ДЛЯ КОНТЕКСТА:
Профессия: ${profession}
Локация: ${address}
Зарплата/Ставка: ${salary}
Тональность текста: ${randomTone}

ИНФОРМАЦИЯ ДЛЯ ВДОХНОВЕНИЯ (используй факты отсюда, но перефразируй):
Обязанности: ${randomDuty.replace(/<[^>]*>/g, '')}
Преимущества: ${randomAdv.replace(/<[^>]*>/g, '')}

ИНСТРУКЦИИ ПО СОДЕРЖАНИЮ:
1. Используй СТРОГО только профессию "${profession}".
2. Сгенерируй ОДИН вариант названия (Title) и ОДИН вариант описания (Description).
3. Название должно быть коротким, привлекательным и включать "${profession}".
4. КРИТИЧЕСКИ ВАЖНО: ЗАПРЕЩЕНО указывать зарплату, ставку или фразы вроде "выплаты каждый день" в НАЗВАНИИ (Title).
5. **ЗАПРЕЩЕНО использовать символ "|" в тексте.**
6. **Описание должно быть длинным (не менее 600 символов).**
7. Текст должен быть живым, в стиле "${randomTone}". Выделяй выгоды.
8. **УНИКАЛЬНОСТЬ:** В конце описания обязательно добавь одно из двух (на свой выбор):
   - Либо интересный/необычный факт об этой профессии.
   - Либо очень теплое, нестандартное пожелание кандидату.
9. В самом конце добавь короткий call-to-action.

ЗАПРЕЩЕНА ДИСКРИМИНАЦИЯ ПО СОСТОЯНИЮ ЗДОРОВЬЯ:
Категорически запрещено упоминать любые требования или ограничения по состоянию здоровья.
НЕ ИСПОЛЬЗУЙ фразы: "медицинская справка", "хорошее здоровье", "физически здоровым", "крепкое здоровье" и т.д.

ПРАВИЛА ОФОРМЛЕНИЯ:
- Описание должно содержать HTML теги: <p>, <strong>, <ul>, <li>.
- Используй эмодзи.
- ОТВЕТ В JSON: {"title": "...", "description": "..."}`;

  try {
    const aiResponse = AI_REQUEST(prompt, 2000, 0.9); // Чуть выше температура для креатива
    if (!aiResponse) return { title: null, description: null };

    let cleaned = aiResponse
      .replace(/```json/g, "")
      .replace(/```/g, "")
      .replace(/html'''|'''/g, "") 
      .trim();

    const parsed = JSON.parse(cleaned);
    
    if (parsed.title) {
      parsed.title = parsed.title.replace(/\|/g, "").replace(/\s+/g, " ").trim();
    }
    if (parsed.description) {
      parsed.description = parsed.description.replace(/html'''|'''/g, "").replace(/\|/g, "").trim();
    }

    return parsed;
  } catch (e) {
    Logger.log("Ошибка generateAiVacancyContent: " + e.message);
    return { title: null, description: null };
  }
}

// ============================================
// UI Handlers
// ============================================

function setupAiKeys() {
  const html = HtmlService.createHtmlOutput(`
    <style>body{font-family:sans-serif;padding:10px}input{width:90%;padding:5px;margin:5px 0}button{padding:8px;margin-top:10px}</style>
    <h3>Настройка DeepSeek</h3>
    <label>DeepSeek API Key:</label><br>
    <input type="password" id="d_key" placeholder="sk-..." /><br>
    <button onclick="save()">Сохранить</button>
    <script>
      function save() {
        const d = document.getElementById('d_key').value;
        google.script.run.saveKeysHandler(d);
        google.script.host.close();
      }
    </script>
  `).setWidth(350).setHeight(180);
  SpreadsheetApp.getUi().showModelessDialog(html, 'Настройка ключей');
}

function saveKeysHandler(d) {
  if (d) setApiKey(d);
  SpreadsheetApp.getActiveSpreadsheet().toast('Ключ DeepSeek сохранен!');
}


// ============================================
// ШАГ 1: ПАРСИНГ И ПОДГОТОВКА (ИМПОРТ -> ВАКАНСИИ)
// ============================================

/**
 * Генерирует уникальный ID с префиксом города
 */
function generateUniqueId(city) {
  const cityMap = {
    'Москва': 'M',
    'Московская область': 'MO',
    'Санкт-Петербург': 'SP',
    'Ленинградская область': 'LO',
    'Курск': 'K',
    'Орел': 'O',
    'Нижний Новгород': 'NN',
    'Не определено': 'X'
  };
  
  const prefix = cityMap[city] || 'X';
  const randomNum = Math.floor(100000000 + Math.random() * 900000000);
  
  return `${prefix}${randomNum}`;
}

/**
 * Определяет город из адреса (сначала поиск, потом AI)
 */
function detectCity(address, city) {
  const combinedText = `${address} ${city}`.toLowerCase();
  
  // 1. Простая проверка по списку
  for (const allowedCity of ALLOWED_CITIES) {
    if (combinedText.includes(allowedCity.toLowerCase())) {
      return allowedCity;
    }
  }
  
  // 2. Спец. логика МО
  const moscowRegionKeywords = ['область', 'д.', 'деревня', 'село', 'поселок', 'пос.'];
  if (combinedText.includes('москв') && moscowRegionKeywords.some(kw => combinedText.includes(kw))) {
    return "Московская область";
  }
  
  // 3. AI проверка (DeepSeek/MiMo)
  try {
    const prompt = `Определи город СТРОГО из списка: ${ALLOWED_CITIES.join(', ')}

Адрес: "${address}"
Город из данных: "${city}"

ПРАВИЛА:
- Если есть "д." (деревня), "село", "поселок" + Московская область → "Московская область"
- Если упоминается только город из списка → верни этот город
- Если не можешь определить точно → "Не определено"

ВЕРНИ ТОЛЬКО НАЗВАНИЕ ГОРОДА ИЗ СПИСКА. БЕЗ ПОЯСНЕНИЙ.`;
    
    // Используем малую температуру для точности
    const result = AI_REQUEST(prompt, 30, 0.1);
    if (!result) return "Не определено";
    
    const detectedCity = result.trim();
    if (ALLOWED_CITIES.includes(detectedCity)) {
      return detectedCity;
    }
  } catch (error) {
    Logger.log(`Ошибка определения города: ${error.message}`);
  }
  
  return "Не определено";
}

/**
 * Нормализация адреса через AI
 */
function normalizeAddress(address, originalCity, detectedCity) {
  const combinedAddress = `${address || ''} ${originalCity || ''}`.trim();
  
  if (!combinedAddress) {
    return 'НЕТ АДРЕСА';
  }
  
  const prompt = `Нормализуй адрес БЕЗ упоминания города.

ИСХОДНЫЕ ДАННЫЕ:
Адрес: ${address}
Город: ${originalCity}
Определенный город: ${detectedCity}

ПРАВИЛА ФОРМАТИРОВАНИЯ:
1. НЕ ДОБАВЛЯЙ название города в начало адреса
2. Сокращения: "улица" → "ул.", "проспект" → "пр.", "площадь" → "пл.", "шоссе" → "ш.", "дом" → "д.", "строение" → "стр."
3. Сохраняй названия ТЦ, деревень, сёл как есть
4. Если есть деревня/село, формат: "д. Название, далее адрес"
5. Убери лишние пробелы и дубликаты
6. Если адрес содержит ТЦ, оставь "ТЦ Название"

ПРИМЕРЫ:
Вход: "Коминтерна ул., 11 Нижний Новгород"
Выход: "ул. Коминтерна, д. 11"

Вход: "Энтузиастов ш., 80, ТЦ МаксСити Москва"
Выход: "ш. Энтузиастов, д. 80, ТЦ МаксСити"

ВЕРНИ ТОЛЬКО АДРЕС БЕЗ ГОРОДА. БЕЗ ПОЯСНЕНИЙ.`;

  try {
    const result = AI_REQUEST(prompt, 150, 0.1);
    if (!result) return cleanAddressManually(address, originalCity, detectedCity);
    
    const normalized = result.trim();
    
    // Проверка на галлюцинации (если AI вернул пустую строку или добавил город)
    if (normalized && !normalized.toLowerCase().startsWith(detectedCity.toLowerCase())) {
      return normalized;
    }
    
    // Очистка если город все-таки прилип
    const withoutCity = normalized.replace(new RegExp(`^${detectedCity},?\\s*`, 'i'), '').trim();
    return withoutCity || normalized;
    
  } catch (error) {
    Logger.log(`Ошибка нормализации адреса: ${error.message}`);
    return cleanAddressManually(address, originalCity, detectedCity);
  }
}

/**
 * Fallback: Ручная очистка адреса, если AI упал
 */
function cleanAddressManually(address, originalCity, detectedCity) {
  let cleaned = address || '';
  
  cleaned = cleaned.replace(new RegExp(detectedCity, 'gi'), '');
  cleaned = cleaned.replace(new RegExp(originalCity, 'gi'), '');
  
  cleaned = cleaned
    .replace(/улица/gi, 'ул.')
    .replace(/проспект/gi, 'пр.')
    .replace(/площадь/gi, 'пл.')
    .replace(/шоссе/gi, 'ш.')
    .replace(/\bдом\b/gi, 'д.')
    .replace(/строение/gi, 'стр.')
    .replace(/\s+/g, ' ')
    .replace(/,\s*,/g, ',')
    .replace(/^[,\s]+|[,\s]+$/g, '')
    .trim();
  
  return cleaned || address;
}

/**
 * Функция для стандартизации адресов на листе "Настройки"
 * Использует Google Maps Geocoder и AI для приведения адреса к единому виду.
 */
function standardizeSettingsAddresses() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const settingsSheet = ss.getSheetByName("Настройки");
  
  if (!settingsSheet) {
    SpreadsheetApp.getUi().alert("Ошибка: Лист 'Настройки' не найден");
    return;
  }

  const lastRow = settingsSheet.getLastRow();
  // Начинаем со 2-й строки, так как 1-я — это заголовок
  if (lastRow < 2) {
    SpreadsheetApp.getUi().alert("Нет данных для обработки на листе 'Настройки'");
    return;
  }

  // Столбцы: C (адрес), D (город/регион), F (результат)
  const dataRange = settingsSheet.getRange(2, 3, lastRow - 1, 2); // C-D
  const data = dataRange.getValues();
  const outputRangeF = settingsSheet.getRange(2, 6, lastRow - 1, 1); // F
  const existingResults = outputRangeF.getValues();
  
  const startTime = new Date().getTime();
  const MAX_TIME = 5.5 * 60 * 1000; // 5.5 минут
  let geocoderLimitReached = false;
  let processedCount = 0;
  let skippedCount = 0;

  for (let i = 0; i < data.length; i++) {
    const rowNum = i + 2;
    
    // 1. ПРОВЕРКА ТАЙМ-АУТА
    if (new Date().getTime() - startTime > MAX_TIME) {
      SpreadsheetApp.getUi().alert(`⌛ ВРЕМЯ ПОЧТИ ВЫШЛО\nОбработано за сеанс: ${processedCount}. Нажмите кнопку снова, чтобы продолжить.`);
      return;
    }

    // Пропускаем, если в столбце F уже есть значение
    if (existingResults[i][0]) {
      skippedCount++;
      continue;
    }

    const address = data[i][0] ? data[i][0].toString().trim() : "";
    const city = data[i][1] ? data[i][1].toString().trim() : "";
    
    if (!address && !city) continue;

    // 2. ЗАПРОС К GEOCODER (если не достигнут лимит)
    let googleResult = "";
    let statusText = "";

    if (!geocoderLimitReached) {
      try {
        const gResponse = Maps.newGeocoder()
          .setLanguage('ru')
          .setRegion('ru')
          .geocode(`ТЦ Лента ${address}, ${city}`);
        
        if (gResponse.status === 'OK' && gResponse.results.length > 0) {
          googleResult = gResponse.results[0].formatted_address;
          statusText = googleResult;
        } else if (gResponse.status === 'OVER_QUERY_LIMIT') {
          geocoderLimitReached = true;
          statusText = "⚠️ Лимит Google исчерпан";
          Logger.log("Google Geocoder limit reached. Switching to AI-only mode.");
        } else {
          statusText = `Ошибка: ${gResponse.status}`;
        }
      } catch (e) {
        Logger.log("Google Geocoder error: " + e.message);
        statusText = "Ошибка сервиса";
      }
    } else {
      statusText = "⏸️ Пропуск (лимит квоты)";
    }

    // Ссылка на поиск для ручной проверки
    const searchQuery = encodeURIComponent(`ТЦ Лента ${address} ${city}`);
    const searchUrl = `https://www.google.com/search?q=${searchQuery}`;
    const searchFormula = `=HYPERLINK("${searchUrl}"; "🔍 Проверить")`;

    // 3. ИИ ФОРМАТИРОВАНИЕ (работает всегда)
    const prompt = `Ты — эксперт по географии РФ и магазинам "Лента".
Твоя задача — выдать стандартизированный адрес. Используй свои знания, если Geocoder не ответил.

ДАННЫЕ:
Объект: ТЦ Лента
Ввод: "${address}, ${city}"
Geocoder: "${googleResult || "ДАННЫЕ ОТСУТСТВУЮТ (используй свои знания)"}"

ПРАВИЛА (СТРОГО):
1. ФОРМАТ: Регион, Населенный пункт, Город, Улица, Номер дома.
2. БЕЗ ДУБЛИКАТОВ: Название города или региона НЕ должно повторяться в строке. Если город совпадает с регионом (как в Питере), пиши только один раз.
3. МОСКВА / САНКТ-ПЕТЕРБУРГ: Пиши ТОЛЬКО "г. Москва" или "г. Санкт-Петербург". НЕ добавляй область или повторы.
4. ЗНАНИЯ (БАЛАШИХА): Если в вводе есть "Пригородная 90" в МО, ты ЗНАЕШЬ, что это г. Балашиха. Добавь город сам!
5. ОБЯЗАТЕЛЬНО: Оставляй деревни (д.), поселки (пос.), села (с.), микрорайоны (мкр.).
6. УДАЛИ: "Россия", индекс, English.
7. ВЕРНИ: Только одну строку. Без лишних слов.

ПРИМЕРЫ:
- Санкт-Петербург, Пискарёвский пр-кт -> г. Санкт-Петербург, Пискарёвский пр-кт, д. 59А
- Балашиха, Пригородная 90 -> Московская обл., г. Балашиха, Пригородная ул., д. 90
- Марушкино, ул. Полевая, 5 -> Московская обл., д. Марушкино, Полевая ул., д. 5

ВЕРНИ ТОЛЬКО СТРОКУ АДРЕСА:`;

    const standardized = AI_REQUEST(prompt, 180, 0.1);
    const finalValue = standardized ? standardized.trim() : (googleResult || `${address}, ${city}`);
    
    // Записываем СРАЗУ
    settingsSheet.getRange(rowNum, 6).setValue(finalValue);        // F - Стандартизированный
    settingsSheet.getRange(rowNum, 7).setValue(statusText);         // G - Статус Google
    settingsSheet.getRange(rowNum, 8).setFormula(searchFormula);    // H - Поиск
    
    SpreadsheetApp.flush();
    processedCount++;
    Utilities.sleep(300);
  }

  // Заголовок для H (если нет)
  if (settingsSheet.getRange(1, 8).getValue() !== "Поиск") {
    settingsSheet.getRange(1, 8).setValue("Поиск").setFontWeight("bold");
  }

  const limitMsg = geocoderLimitReached ? "\n⚠️ В процессе достигнут лимит Google, далее работал только ИИ." : "";
  SpreadsheetApp.getUi().alert(`✅ Готово\nДобавлено: ${processedCount}\nПропущено: ${skippedCount}${limitMsg}`);
}

/**
 * Уточняет адрес через Яндекс.Карты (без API key)
 */
function getClarifiedAddressYandex(address, city) {
  if (!address) return 'Ошибка: нет адреса';
  
  try {
    const query = city ? `ТЦ Лента ${address}, ${city}` : `ТЦ Лента ${address}`;
    const encodedQuery = encodeURIComponent(query);
    
    // Яндекс.Геокодер позволяет запросы без ключа (с лимитами)
    const url = `https://geocode-maps.yandex.ru/1.x/?apikey=&geocode=${encodedQuery}&format=json&lang=ru_RU`;
    
    const options = {
      muteHttpExceptions: true
    };
    
    const response = UrlFetchApp.fetch(url, options);
    const result = JSON.parse(response.getContentText());
    
    if (result.response && result.response.GeoObjectCollection && 
        result.response.GeoObjectCollection.featureMember.length > 0) {
      const geoObject = result.response.GeoObjectCollection.featureMember[0].GeoObject;
      return geoObject.metaDataProperty.GeocoderMetaData.text;
    }
    return 'Адрес не найден';
  } catch (e) {
    Logger.log(`Yandex Geocode Error: ${e.message}`);
    return null;
  }
}

/**
 * Создает массив данных для записи в лист
 */
function createVacancyRow(city, normalizedAddress, originalCity, position, schedule, level, tkType, service) {
  const uniqueId = generateUniqueId(city);
  
  return [
    uniqueId,          // A - ID
    city,              // B - Город
    normalizedAddress, // C - Адрес
    position || service, // D - Должность
    schedule,          // E - График
    level,             // F - Уровень
    null,              // G - Зарплата (формула)
    tkType,            // H - Тип ТК
    service,           // I - Услуга
    null,              // J - Оклад Мин (формула)
    null               // K - Оклад Макс (формула)
  ];
}

/**
 * Обрабатывает одну строку с повторными попытками (Retry Logic)
 */
function parseVacancyRow(rowData, sourceRowNumber) {
  const maxRetries = 3;
  let attempt = 0;
  
  while (attempt < maxRetries) {
    try {
      attempt++;
      
      const tk = rowData[0] || '';
      const address = rowData[1] || '';
      const city = rowData[2] || '';
      const position = rowData[3] || '';
      const level = rowData[4] || ''; // В оригинальном сниппете index 5, но в листе Вакансии это F (индекс 5). В Импорте это может быть по-другому. 
                                      // Сверяемся с логикой: в Импорте 10 столбцов.
                                      // Данные из dataRange.getValues(): 2-я строка, 1-й столбец, lastRow-1 строк, 10 столбцов.
                                      // Индексы в rowData (0-9):
                                      // 0 - ТК, 1 - Адрес, 2 - Город, 3 - Должность, 4 - Уровень?, 5 - График?
                                      // В сниппете: level = rowData[5], schedule = rowData[6], type = rowData[8], service = rowData[9].
      const schedule = rowData[6] || '';
      const type = rowData[8] || '';
      const service = rowData[9] || '';
      
      // 1. Используем город как есть (без AI)
      const detectedCity = city;
      
      // 2. Используем адрес как есть (без AI, так как он уже нормализован)
      const normalizedAddress = address;
      
      // 3. Собираем результат
      return createVacancyRow(
        detectedCity,
        normalizedAddress,
        city,
        position,
        schedule,
        rowData[5], // level (индекс 5 согласно сниппету)
        type,
        service
      );
      
    } catch (error) {
      Logger.log(`Попытка ${attempt} не удалась для строки ${sourceRowNumber}: ${error.message}`);
      if (attempt < maxRetries) {
        Utilities.sleep(1000 * attempt);
      } else {
        throw error;
      }
    }
  }
}

function processAllVacancies() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  let importSheet = ss.getSheetByName(IMPORT_SHEET_NAME);
  if (!importSheet) {
    ui.alert('❌ Ошибка', `Лист "${IMPORT_SHEET_NAME}" не найден!`, ui.ButtonSet.OK);
    return;
  }
  
  const confirm = ui.alert(
    '🚀 Запуск обработки (Шаг 1)',
    `Обработка данных (быстрый режим).\n\nНажмите ДА для старта обработки.\nДанные будут добавляться в лист "${OUTPUT_SHEET_NAME}".`,
    ui.ButtonSet.YES_NO
  );
  
  if (confirm !== ui.Button.YES) return;
  
  let outputSheet = ss.getSheetByName(OUTPUT_SHEET_NAME);
  if (!outputSheet) {
    outputSheet = ss.insertSheet(OUTPUT_SHEET_NAME);
  }

  // Проверяем наличие заголовков (если первая ячейка пустая или не равна 'ID')
  if (outputSheet.getLastRow() === 0 || outputSheet.getRange(1, 1).getValue() !== 'ID') {
    outputSheet.clear(); // На всякий случай очищаем, если там мусор
    outputSheet.getRange(1, 1, 1, 11).setValues([[
      'ID', 'Город', 'Адрес', 'Должность', 'График',
      'Уровень ЧТС', 'Зарплата', 'Тип ТК', 'Услуга', 'Оклад мин', 'Оклад макс'
    ]]);
    outputSheet.getRange(1, 1, 1, 11).setFontWeight('bold').setBackground('#4a86e8').setFontColor('#ffffff');
  }
  
  const statusCol = 11; // K
  if (importSheet.getRange(1, statusCol).getValue() !== 'Статус') {
    importSheet.getRange(1, statusCol).setValue('Статус').setFontWeight('bold');
  }
  
  const lastRow = importSheet.getLastRow();
  if (lastRow < 2) return;
  
  const dataRange = importSheet.getRange(2, 1, lastRow - 1, 10);
  const values = dataRange.getValues();
  const statusRange = importSheet.getRange(2, statusCol, lastRow - 1, 1);
  const statuses = statusRange.getValues();
  
  let processed = 0;
  let errors = 0;
  
  for (let i = 0; i < values.length; i++) {
    if (statuses[i][0] === '✅') continue;
    
    const rowNumber = i + 2;
    
    try {
      if (processed > 0 && processed % 10 === 0) SpreadsheetApp.flush();
      
      const vacancy = parseVacancyRow(values[i], rowNumber);
      let outputRow = outputSheet.getLastRow() + 1;
      if (outputRow < 2) outputRow = 2; // Защита от перезаписи шапки
      outputSheet.getRange(outputRow, 1, 1, 11).setValues([vacancy]);
      
      // Формулы (предполагаем наличие функции ZP)
      outputSheet.getRange(outputRow, 7).setFormula(`=ZP(B${outputRow};H${outputRow};I${outputRow};F${outputRow})`);
      outputSheet.getRange(outputRow, 10).setFormula(`=IF(ISERROR(G${outputRow});"по договоренности";IF(OR(B${outputRow}="Москва";B${outputRow}="Санкт-Петербург");G${outputRow}*8;G${outputRow}*8))`);
      outputSheet.getRange(outputRow, 11).setFormula(`=IF(ISERROR(G${outputRow});"по договоренности";IF(OR(B${outputRow}="Москва";B${outputRow}="Санкт-Петербург");G${outputRow}*12;G${outputRow}*11))`);
      
      importSheet.getRange(rowNumber, statusCol).setValue('✅').setBackground('#b7e1cd');
      processed++;
      
      Utilities.sleep(1500);
      
    } catch (e) {
      importSheet.getRange(rowNumber, statusCol).setValue(`❌ ${e.message}`).setBackground('#f4c7c3');
      errors++;
    }
    
    if (processed % BATCH_SIZE === 0 && processed > 0) {
      const cont = ui.alert('⏸️ Пауза', `Обработано: ${processed}. Ошибок: ${errors}. Продолжить?`, ui.ButtonSet.YES_NO);
      if (cont !== ui.Button.YES) break;
    }
  }
  
  ui.alert('✅ Готово', `Шаг 1 завершен!\nОбработано: ${processed}\nОшибок: ${errors}`, ui.ButtonSet.OK);
}

function continueProcessing() {
  processAllVacancies();
}

function resetStatuses() {
  const ui = SpreadsheetApp.getUi();
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(IMPORT_SHEET_NAME);
  if (!sheet) return;
  
  if (ui.alert('⚠️ Сброс', 'Сбросить статусы обработки? Это приведет к повторной обработке всех строк.', ui.ButtonSet.YES_NO) === ui.Button.YES) {
    const lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      sheet.getRange(2, 11, lastRow - 1, 1).clearContent().setBackground(null);
      ui.alert('Статусы сброшены.');
    }
  }
}

/**
 * Add custom menu when spreadsheet opens.
 * Добавляет пользовательское меню при открытии таблицы.
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('🤖 AdsGen')
    .addItem('Шаг 1: Подготовить базу (Импорт -> Вакансии)', 'importDataFromSheet')
    .addItem('Шаг 2: Сгенерировать объявления', 'fillVacanciesWork')
    .addSeparator()
    .addItem('🚀 Запустить авто-генерацию (каждые 10 мин)', 'startAutoProcessing')
    .addItem('🛑 Остановить авто-генерацию', 'stopAutoProcessing')
    .addSeparator()
    .addItem('Тест: Сгенерировать одну вакансию', 'fillOneVacancyTest')
    .addItem('Синхронизация удаленных вакансий', 'syncDeletedVacancies')
    .addSeparator()
    .addItem('Настройка API ключей', 'setupAiKeys')
    .addSeparator()
    .addItem('ℹ️ Справка', 'showHelp')
    .addToUi();
}

/**
 * Показывает справку о состоянии ключей
 */
function showHelp() {
  const info = getKeysInfo();
  SpreadsheetApp.getUi().alert(`🤖 ПАРСЕР v10.0
  
  Текущая сеть: DeepSeek
 DeepSeek ключ: ${info.deepseek}

Как использовать:
1. Заполните лист "Импорт"
2. Меню: 1️⃣ Подготовить базу
3. Проверьте лист "Вакансии"
4. Меню: 2️⃣ Сгенерировать финал

v10.0 | 2025`);
}
