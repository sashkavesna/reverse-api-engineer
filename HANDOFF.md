# Session Handoff: Reverse API Engineer & Mass Registration Pipeline

- **Дата:** 2026-09-07
- **Репозиторий:** `services/reverse-api-engineer` (`https://github.com/sashkavesna/reverse-api-engineer`)
- **Ветка:** `main`
- **Ревизия:** `a43b868` (`feat: merge recon and replay pipeline into main`)
- **Статус дерева:** `clean` (все изменения закоммичены и запушены в `origin/main`)
- **Канон Life OS:** `prj-reverse-api-engineer` обновлён в `40-projects/reverse-api-engineer/PROJECT.md` (коммит `e837b57`).

---

## 1. Достигнутые результаты

1. **Архитектурный поворот от оверинжиниринга к Lean-модульности:**
   - Отказались от зависимости от тяжелых сторонних SDK (`claude-agent-sdk`, фоновый сервер `OpenCode` на 4096).
   - Спроектирован и реализован двухконтурный модульный конвейер:
     - **Контур 1 (Recon):** однократная ручная регистрация в локальном браузере Playwright с перехватом и фильтрацией статического шума и трекеров (`recon.py`).
     - **Синтезатор (Synthesizer):** автоматическое обнаружение эндпоинта отправки формы, связывание динамических CSRF-токенов из предшествующих GET-ответов и генерация `ServiceRecipe` (`synthesizer.py`).
     - **Контур 2 (Replay / Runner):** автономное выполнение регистрации через `curl_cffi` (подмена TLS-отпечатка Chrome 120 для обхода Cloudflare WAF) + клиент временной почты `temp_mail.py` + сохранение сессий в State Vault (`runner.py`).
2. **Интеграция с сервисом временной почты (`temp_mail.py`):**
   - Прямая работа с API сервиса `temp_mail` (`mail.expertcore.ru`): создание ящиков, ожидание входящих писем, извлечение OTP-кодов и ссылок активации.
3. **CLI интеграция (`cli.py`):**
   - Добавлены команды:
     - `reverse-api-engineer recon <url> [--name <svc>]`
     - `reverse-api-engineer run-recipe <recipe.json>`
4. **Инженерные стандарты и канон:**
   - [SPEC.md](file:///c:/Users/sashk/OneDrive/Desktop/Projects/services/reverse-api-engineer/SPEC.md) — зафиксированы цели, контракты, инварианты (INV-1, INV-2, INV-3) и антипаттерны (ANTI-1 ... ANTI-4).
   - [TASKS.md](file:///c:/Users/sashk/OneDrive/Desktop/Projects/services/reverse-api-engineer/TASKS.md) — все 6 задач (TASK-001 ... TASK-006) переведены в статус `DONE`.

---

## 2. Верификация и тесты

- **Уровень доказательств:** **E1–E3** подтверждены (код написан, типизирован, покрыт изолированными тестами с сетевыми моками).
- **Результаты тест-сьюта:** **39/39 тестов пройдены (зеленые):**
  ```powershell
  & .\.venv\Scripts\python.exe -m pytest tests/test_vault.py tests/test_temp_mail.py tests/test_recon.py tests/test_synthesizer.py tests/test_runner.py -v
  ```
  - `tests/test_vault.py`: 19 passed.
  - `tests/test_temp_mail.py`: 8 passed.
  - `tests/test_recon.py`: 5 passed.
  - `tests/test_synthesizer.py`: 4 passed.
  - `tests/test_runner.py`: 3 passed.
- **Линтинг и стиль:** `ruff check` пройден без замечаний по всем новым модулям.

---

## 3. Окружение и инфраструктурные нюансы

- **Виртуальное окружение:** `.venv` (Python 3.12). Установлены `curl_cffi`, `playwright` (Chromium запускается), `pytest`, `pytest-asyncio`, `ruff`.
- **Сервис temp_mail:** API сервиса на VPS привязано к `127.0.0.1:8000` в Docker Compose (`temp-mail`). Для прямого локального обращения к API с рабочей машины Windows требуется либо SSH-проброс порта:
  ```powershell
  ssh -N -L 8000:127.0.0.1:8000 server
  ```
  либо передача кастомного адреса почты через флаг `--email <address>` при отладке без туннеля.

---

## 4. Следующий конкретный шаг (Next Action)

**Боевой сквозной тест (E4):**
1. Выбрать реальную площадку (форум, сервис, блог-платформу-донор).
2. Запустить полуручную разведку формы:
   ```powershell
   & .\.venv\Scripts\python.exe -m reverse_api.cli recon <TARGET_REGISTRATION_URL> --name <service_name>
   ```
3. Пройти форму руками один раз, закрыть браузер, проверить сгенерированный файл `recipes/<service_name>.json`.
4. Запустить автономный прогон регистрации:
   ```powershell
   & .\.venv\Scripts\python.exe -m reverse_api.cli run-recipe recipes/<service_name>.json
   ```
5. Проверить сохранение профиля в хранилище сессий:
   ```powershell
   & .\.venv\Scripts\python.exe -m reverse_api.cli vault list
   ```
