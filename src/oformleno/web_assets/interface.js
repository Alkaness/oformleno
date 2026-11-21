// No file bytes enter persistent component state. Uploads are one-shot triggers.
export default function ({ parentElement, data, setTriggerValue }) {
  // Streamlit calls this renderer again on data changes without unmounting it.
  const disposeKey = Symbol.for("oformleno.interface.dispose");
  parentElement[disposeKey]?.();
  document.documentElement.lang = "uk";
  const platformSkip = document.querySelector('[data-testid="stSkipToContent"]');
  if (platformSkip) {
    platformSkip.textContent = "Перейти до основного вмісту";
    platformSkip.setAttribute("aria-label", "Перейти до основного вмісту");
  }
  const root = parentElement.querySelector("#oformleno-root");
  let selected = null;
  let reader = null;
  let active = true;
  let downloadUrl = null;
  const dispose = () => {
    if (!active) return;
    active = false;
    selected = null;
    if (reader && reader.readyState === FileReader.LOADING) reader.abort();
    reader = null;
    if (downloadUrl) URL.revokeObjectURL(downloadUrl);
    downloadUrl = null;
    if (parentElement[disposeKey] === dispose) {
      root.replaceChildren();
      delete parentElement[disposeKey];
    }
  };
  parentElement[disposeKey] = dispose;

  const button = (text, action, className = "") => {
    const element = document.createElement("button");
    element.type = "button";
    element.textContent = text;
    element.className = className;
    element.addEventListener("click", action);
    return element;
  };
  const reset = () => {
    dispose();
    setTriggerValue("reset", true);
  };

  if (data.report) {
    // HTML comes only from the escaping Python renderer, never from an upload.
    const parsed = new DOMParser().parseFromString(data.report, "text/html");
    root.replaceChildren();
    const styles = document.createElement("style");
    styles.textContent = parsed.querySelector("style").textContent;
    root.append(styles, ...Array.from(parsed.body.childNodes));
    root.querySelector(".brand .wrap").append(button("Перевірити інший документ", reset, "app-reset"));
    root.querySelector(".brand .wrap").style.justifyContent = "space-between";
    const summary = root.querySelector(".summary");
    const actions = document.createElement("div");
    actions.className = "app-report-action";
    const note = document.createElement("p");
    note.textContent = "Копію готуємо під час обробки, щоб одразу видалити завантаження. Оригінал не змінюється.";
    if (data.can_reveal) {
      actions.append(button("Переглянути виправлену копію", () => setTriggerValue("reveal", true)), note);
    }
    if (data.ready && data.download) {
      const status = document.createElement("p");
      status.className = "app-ready";
      status.textContent = "Виправлена копія готова. Нижче — результат її повторної перевірки.";
      const bytes = Uint8Array.from(atob(data.download), (character) => character.charCodeAt(0));
      downloadUrl = URL.createObjectURL(new Blob([bytes], {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      }));
      const download = document.createElement("a");
      download.href = downloadUrl;
      download.download = "Виправлена_копія.docx";
      download.className = "app-download";
      download.textContent = "Завантажити виправлену копію";
      actions.append(status, download, note);
    }
    if (data.error) {
      const error = document.createElement("p");
      error.className = "app-error";
      error.setAttribute("role", "alert");
      error.textContent = data.error;
      actions.append(error);
    }
    const privacy = document.createElement("p");
    privacy.textContent = "Ручні пункти й помилки без автовиправлення залишаються у звіті. Очистіть результат після завантаження.";
    actions.append(privacy, button("Очистити результат", reset, "app-reset"));
    summary.querySelector(".counts").after(actions);
    root.querySelectorAll('a[href^="#"]').forEach((link) => {
      link.addEventListener("click", (event) => {
        const target = root.querySelector(link.getAttribute("href"));
        if (target) {
          event.preventDefault();
          for (let ancestor = target; ancestor && ancestor !== root; ancestor = ancestor.parentElement) {
            if (ancestor.tagName === "DETAILS") ancestor.open = true;
          }
          const focusTarget = target.tagName === "DETAILS" ? target.querySelector("summary") : target;
          if (focusTarget.tagName !== "SUMMARY") focusTarget.tabIndex = -1;
          focusTarget.focus({ preventScroll: true });
          target.scrollIntoView({ behavior: "instant", block: "start" });
        }
      });
    });
  } else {
    root.innerHTML = `
      <a class="app-skip" href="#app-main">Перейти до перевірки</a>
      <header class="app-header"><div class="app-wrap"><span class="app-wordmark">Оформлено</span></div></header>
      <main class="app-wrap app-body" id="app-main">
        <section aria-labelledby="upload-title">
          <h1 id="upload-title">Перевірка документа</h1>
          <p class="app-lead">Завантажте .docx до 20 МБ. Оформлено перевірить його за вибраною методичкою.</p>
          <div class="app-fields">
            <div><div class="app-field-label">Методичка</div><div class="app-field-value">Кафедра ЕОМ · 2026</div></div>
            <div><div class="app-field-label">Тип роботи</div><div class="app-field-value">Лабораторна робота</div></div>
          </div>
          <div class="app-mode">
            <label class="app-field-label" for="body-text-mode">Режим основного тексту</label>
            <select id="body-text-mode" class="app-field-value" aria-describedby="body-text-help">
              <option value="ordinary">Звичайний текст</option>
              <option value="styles">За стилями документа</option>
            </select>
            <p id="body-text-help" class="app-meta">Для тексту без стилів кафедри. Звичайні абзаци перевіряємо як основний текст; заголовки, підписи й таблиці мають окремі вимоги.</p>
          </div>
          <div class="app-dropzone" aria-label="Завантаження документа">
            <p class="app-file-type">.docx</p>
            <p>Перетягніть документ сюди</p><p class="app-meta">або оберіть файл на пристрої</p>
            <input class="app-file" type="file" accept=".docx" aria-label="Обрати документ .docx" hidden>
          </div>
          <p class="app-selected" aria-live="polite"></p>
          <p class="app-error" role="alert" hidden></p>
          <p class="app-status" role="status" aria-live="polite"></p>
          <p class="app-meta">Оригінал не змінюється. Під час обробки готуємо окрему виправлену копію й видаляємо завантаження.</p>
        </section>
        <aside aria-labelledby="scope-title">
          <h2 id="scope-title">Вимоги кафедри ЕОМ</h2>
          <p>НУ «Львівська політехніка»<br>Профіль оформлення 2026 року.</p>
          <ul class="app-scope"><li>Формат сторінки та поля</li><li>Шрифт і міжрядковий інтервал</li>
            <li>Заголовки, рисунки й таблиці</li><li>Нумерація сторінок</li></ul>
          <h2>Межі перевірки</h2>
          <p>Якщо роль елемента або його форматування неможливо визначити надійно, звіт попросить перевірити його вручну.</p>
          <p class="app-meta">Перевірка оформлення не оцінює зміст чи плагіат. Звіт і копія доступні в цій вкладці до очищення результату.</p>
        </aside>
      </main>`;
    const input = root.querySelector(".app-file");
    const zone = root.querySelector(".app-dropzone");
    const caption = root.querySelector(".app-selected");
    const error = root.querySelector(".app-error");
    const status = root.querySelector(".app-status");
    const mode = root.querySelector("#body-text-mode");
    const modeHelp = root.querySelector("#body-text-help");
    mode.addEventListener("change", () => {
      modeHelp.textContent = mode.value === "ordinary"
        ? "Для тексту без стилів кафедри. Звичайні абзаци перевіряємо як основний текст; заголовки, підписи й таблиці мають окремі вимоги."
        : "Основний текст визначаємо за відомими стилями Word. Звичайні абзаци без підтвердженої ролі потребують ручного перегляду.";
    });
    const choose = button("Обрати файл", () => input.click());
    zone.append(choose);
    const check = button("Перевірити документ", async () => {
      if (!selected || reader) return;
      check.disabled = true;
      choose.disabled = true;
      mode.disabled = true;
      status.textContent = "Перевіряємо документ і готуємо окрему копію…";
      reader = new FileReader();
      reader.onerror = () => {
        if (!active) return;
        selected = null;
        input.value = "";
        reader = null;
        status.textContent = "";
        error.textContent = "Не вдалося прочитати файл. Оберіть його ще раз.";
        error.hidden = false;
        choose.disabled = false;
        mode.disabled = false;
      };
      reader.onload = () => {
        if (!active) return;
        const payload = { name: selected.name, content: reader.result.split(",", 2)[1],
          body_text_mode: mode.value };
        selected = null;
        input.value = "";
        caption.textContent = "";
        reader = null;
        setTriggerValue("upload", payload);
      };
      reader.readAsDataURL(selected);
    }, "app-check");
    check.disabled = true;
    caption.before(check);
    const select = (files) => {
      if (reader) return;
      selected = null;
      check.disabled = true;
      caption.textContent = "";
      error.hidden = true;
      if (!files || files.length !== 1) {
        error.textContent = "Оберіть один файл .docx.";
      } else if (!/\.docx$/i.test(files[0].name)) {
        error.textContent = "Підтримуються лише файли формату .docx.";
      } else if (files[0].size > 20 * 1024 * 1024) {
        error.textContent = "Розмір файлу перевищує 20 МБ.";
      } else {
        selected = files[0];
        caption.textContent = `${selected.name} · ${(selected.size / (1024 * 1024)).toLocaleString("uk-UA", { maximumFractionDigits: 2 })} МБ`;
        check.disabled = false;
        return;
      }
      input.value = "";
      error.hidden = false;
    };
    input.addEventListener("change", () => { if (input.files.length) select(input.files); });
    zone.addEventListener("dragover", (event) => { event.preventDefault(); zone.classList.add("dragover"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone.addEventListener("drop", (event) => {
      event.preventDefault(); zone.classList.remove("dragover"); select(event.dataTransfer.files);
    });
    if (data.error) { error.textContent = data.error; error.hidden = false; }
  }
  // The platform already provides the first keyboard skip link in the live app.
  if (platformSkip) root.querySelector(".app-skip, .skip-link")?.remove();
  return dispose;
}
