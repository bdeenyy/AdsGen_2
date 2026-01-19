// ═══════════════════════════════════════════════════════════════════════════
// СКРИПТ УДАЛЕНИЯ ДУБЛИКАТОВ ИЗОБРАЖЕНИЙ
// Проверяет столбец F на листе "Работа-Вакансии" и заменяет повторы
// ═══════════════════════════════════════════════════════════════════════════


// Хелпер для нормализации ссылок
function normalizeUrl(url) {
  if (!url) return "";
  return url.replace("https://yadi.sk", "https://disk.yandex.ru");
}

function deduplicateImages() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName("Работа-Вакансии");
  
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Ошибка: лист 'Работа-Вакансии' не найден.");
    return;
  }
  
  const lastRow = sheet.getLastRow();
  if (lastRow < 5) {
    SpreadsheetApp.getUi().alert("Нет данных для обработки (меньше 5 строк).");
    return;
  }
  
  // Читаем данные: Нам нужны Images (F -> index 5) и Profession (W -> index 22)
  // Данные начинаются с 5-й строки (по структуре adsgen.gs)
  // Но лучше прочитать весь диапазон, чтобы индексы совпадали
  // Читаем с 5 строки до конца
  const startRow = 5;
  const numRows = lastRow - startRow + 1;
  const range = sheet.getRange(startRow, 1, numRows, 23); // A(1) to W(23)
  const values = range.getValues();
  
  // Столбцы (в массиве 0-based)
  const COL_IMAGE = 5; // F
  const COL_PROFESSION = 22; // W
  
  // 1. Подсчет использования ссылок
  const urlUsage = new Map();
  
  // Инициализируем счетчик текущими данными
  for (let i = 0; i < values.length; i++) {
    // Нормализуем ссылку при чтении
    const rawUrl = values[i][COL_IMAGE];
    const url = normalizeUrl(rawUrl);
    
    if (url) {
      urlUsage.set(url, (urlUsage.get(url) || 0) + 1);
    }
  }
  
  let changesCount = 0;
  const newImages = []; // Для пакетного обновления
  
  // 2. Проход для замены дубликатов
  // Мы идем сверху вниз. Первое появление ссылки не трогаем, второе и далее - меняем.
  
  // Локальный трекер для этого прохода, чтобы знать, встречали ли мы уже эту ссылку В ЭТОМ проходе
  const seenInThisPass = new Set();
  
  for (let i = 0; i < values.length; i++) {
    const rawUrl = values[i][COL_IMAGE];
    const currentUrl = normalizeUrl(rawUrl);
    const profession = values[i][COL_PROFESSION];
    
    // Если профессии нет или url пустой, просто сохраняем текущий (нормализованный)
    if (!currentUrl || !profession) {
      // Если ссылка изменилась только из-за нормализации, это тоже изменение
      if (rawUrl !== currentUrl) {
         changesCount++;
      }
      newImages.push([currentUrl]);
      continue;
    }
    
    // Если мы уже видели эту ссылку в этом проходе
    if (seenInThisPass.has(currentUrl)) {
      // Это дубликат! Нужно заменить.
      
      // Получаем доступные картинки для профессии из preset.gs
      // (Переменная IMAGES должна быть доступна глобально, так как это файл в том же проекте)
      const availableImages = IMAGES[profession] || [];
      
      if (availableImages.length === 0) {
        // Нет альтернатив
        newImages.push([currentUrl]);
        continue;
      }
      
      // Ищем лучшую замену
      let bestImage = currentUrl;
      let minUsage = Infinity;
      
      // Проверяем все доступные картинки
      for (const rawImg of availableImages) {
        const img = normalizeUrl(rawImg);
        
        // Сколько раз эта картинка уже используется во всем листе?
        // (учитываем обновления, которые мы уже сделали в urlUsage)
        const usage = urlUsage.get(img) || 0;
        
        if (usage < minUsage) {
          minUsage = usage;
          bestImage = img;
        }
        
        // Если нашли картинку с 0 использованием - берем сразу
        if (minUsage === 0) break;
      }
      
      // Применяем замену
      newImages.push([bestImage]);
      
      // Обновляем счетчики
      urlUsage.set(bestImage, (urlUsage.get(bestImage) || 0) + 1);
      
      changesCount++;
      
    } else {
      // Первое вхождение, оставляем (но нормализуем если надо)
      seenInThisPass.add(currentUrl);
      if (rawUrl !== currentUrl) {
         changesCount++; // Считаем за изменение, если нормализовали
      }
      newImages.push([currentUrl]);
    }
  }
  
  // 3. Запись изменений
  if (changesCount > 0) {
    sheet.getRange(startRow, COL_IMAGE + 1, numRows, 1).setValues(newImages);
    SpreadsheetApp.getUi().alert(`Готово! Обновлено строк: ${changesCount} (включая нормализацию ссылок).`);
  } else {
    SpreadsheetApp.getUi().alert("Дубликатов не найдено и ссылки уже нормализованы.");
  }
}

