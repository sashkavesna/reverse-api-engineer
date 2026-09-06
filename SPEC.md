# SPEC: Модульный конвейер разведки (Recon) и автономной регистрации (Replay)

## 1. Контекст и цели
Проект `reverse-api-engineer` предназначен для автоматизации реверс-инжиниринга веб-интерфейсов и создания сверхлегких модулей автономной регистрации/постинга для экосистемы Life OS (`temp_mail`, `boat-content-factory`, `link-selling-factory`).

### 🎯 Цели:
1. **Быстрая разведка (Recon):** Пользователь один раз проходит регистрацию/действие вручную в локальном браузере; модуль перехватывает и очищает сетевой трафик (HAR).
2. **Синтез рецепта (Synthesizer):** Преобразование сетевого дампа в декларативный рецепт (`ServiceRecipe`) с определением эндпоинтов, CSRF-токенов, динамических заголовков и типа подтверждения почты.
3. **Автономное воспроизведение (Runner/Replay):** Легковесный запуск регистрации сотен аккаунтов на базе `curl_cffi` (обход Cloudflare на уровне TLS-отпечатка) и API почты `temp_mail` без поднятия браузеров.
4. **Управление сессиями (State Vault):** Сохранение полученных cookies и авторизационных данных в изолированное хранилище профилей (`~/.reverse-api/profiles`).

---

## 2. Архитектура и компоненты

```
[Пользователь] 
      │ (1 раз руками)
      ▼
[Recon Engine] ────────> [Чистый HAR/JSON лог]
                              │
                              ▼
                    [Recipe Synthesizer] (Gemini Flash)
                              │
                              ▼
                     [Service Recipe] (.json/.py)
                              │
       ┌──────────────────────┴──────────────────────┐
       ▼                                             ▼
[temp_mail API]                            [Autonomous Runner]
(получение почты,                                    │ (curl_cffi, Chrome TLS)
 ожидание OTP/ссылок)                                ▼
       │                                     [Целевой сервис]
       └─────────────────────────────────────────────┘
                              │
                              ▼
                     [State Vault Manager]
                   (~/.reverse-api/profiles)
```

### Компоненты:
1. **`recon.py`**: Запуск браузера с перехватом трафика. Фильтрует статический шум (шрифты, CSS, изображения, аналитику Яндекс/Google) и сохраняет последовательность запросов.
2. **`synthesizer.py`**: Анализирует перехваченные запросы, находит точку отправки формы (POST/PUT), связывает параметры с полученными ранее токенами/куками.
3. **`temp_mail.py`**: Клиент к API временной почты (`http://mail.expertcore.ru:8000`): создание ящиков, опрос входящих писем, извлечение OTP-кодов и ссылок активации.
4. **`runner.py`**: Автономный исполнитель, использующий `curl_cffi.requests.Session(impersonate="chrome120")` для выполнения шагов рецепта.
5. **`vault.py`**: Менеджер локальных профилей браузера и сессий (cookies + metadata).

---

## 3. Инварианты и ограничения

### 🛡️ Позитивные инварианты:
* **INV-1 (Local First for Traffic):** Разведка и запись сессий проводятся локально на рабочей машине пользователя, минимизируя передачу сырых авторизационных данных.
* **INV-2 (Headless Fallback):** Если целевой ресурс использует неразрешимую на уровне HTTP защиту (сложная интерактивная капча), задача переключается на легковесный стелс-браузер (Camoufox).
* **INV-3 (Minimal Memory Footprint):** Процесс автономного воспроизведения не должен потреблять более 50 МБ RAM на поток на сервере.

### 🚫 Антипаттерны и запрещенные действия (Negative Invariants):
* **ANTI-1 (No Heavy Browsers on Production Replay):** Категорически запрещено запускать Chromium/Playwright для массового воспроизведения запросов, если эндпоинт доступен через HTTP.
* **ANTI-2 (No Plain HTTP Clients on Protected Endpoints):** Запрещено использовать стандартные библиотеки `requests` или `httpx` без маскировки TLS-отпечатка для защищенных WAF сервисов. Использовать строго `curl_cffi`.
* **ANTI-3 (No Hardcoded Secrets/Cookies):** Запрещено коммитить в git любые реальные токены, пароли или файлы сохраненных профилей. Все профили живут строго в `~/.reverse-api/profiles/`.
* **ANTI-4 (No Monolithic Bloat):** Запрещено подключать тяжелые внешние агентские демоны (OpenCode сервер, Claude SDK subprocesses) в код автономного воркера.

---

## 4. Контракты данных

### Спецификация рецепта (`ServiceRecipe`):
```json
{
  "name": "example_service",
  "base_url": "https://example.com",
  "auth_type": "email_password",
  "verification_mode": "otp_code",
  "steps": [
    {
      "name": "get_initial_csrf",
      "method": "GET",
      "url": "/register",
      "extract": {
        "csrf_token": {"type": "regex", "pattern": "name=\"csrf\" value=\"(.*?)\""}
      }
    },
    {
      "name": "submit_registration",
      "method": "POST",
      "url": "/api/v1/auth/register",
      "headers": {
        "X-CSRF-Token": "{{csrf_token}}"
      },
      "payload": {
        "email": "{{email}}",
        "password": "{{password}}",
        "csrf": "{{csrf_token}}"
      }
    }
  ]
}
```

---

## 5. План верификации (Acceptance Criteria)

* **E1 (Code Written):** Модули `temp_mail.py`, `recon.py`, `synthesizer.py`, `runner.py` написаны с полной типизацией и обработкой ошибок.
* **E2 (Service Responsive):** Клиент `temp_mail.py` успешно создает ящик и опрашивает API `mail.expertcore.ru`.
* **E3 (Integration Verified):** Модуль `recon.py` перехватывает тестовую отправку формы (`httpbin.org/post` или локальный мок), а `synthesizer.py` формирует валидный рецепт.
* **E4 (End-to-End Replay):** Автономный `runner.py` регистрирует тестовый аккаунт, используя сгенерированный рецепт и `temp_mail`, и сохраняет валидную сессию в `vault.py`.
