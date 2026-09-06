# TASKS: Бэклог задач конвейера Recon & Replay

## Статусы задач
- ⏳ `PENDING` — ожидает выполнения
- 🔄 `IN_PROGRESS` — в работе
- ✅ `DONE` — завершено, подтверждено проверками (E1–E4)

---

### [TASK-001] Инициализация канона, Branch Guard и окружения
- **Статус:** ✅ `DONE`
- **Ветка:** `feature/recon-replay-pipeline`
- **Requires:** нет
- **Inputs:** `implementation_plan.md`, решение `dec-2026-0905`
- **Outputs:** `SPEC.md`, `TASKS.md`, обновленный `.gitignore`, зеленый запуск существующих тестов (`test_vault.py`).
- **Разрешенные пути:** `SPEC.md`, `TASKS.md`, `.gitignore`
- **Запреты:** прямые коммиты в `main`.
- **Критерий приемки (E1–E2):** Спецификация и задачи зафиксированы, `pytest` установлен и подтверждает работоспособность `tests/test_vault.py` (19/19 тестов зеленые).

---

### [TASK-002] Клиент временной почты `temp_mail.py`
- **Статус:** ✅ `DONE`
- **Requires:** `TASK-001`
- **Inputs:** Спецификация API `temp_mail` (`http://mail.expertcore.ru:8000`)
- **Outputs:** `src/reverse_api/temp_mail.py`, `tests/test_temp_mail.py`
- **Разрешенные пути:** `src/reverse_api/temp_mail.py`, `tests/test_temp_mail.py`
- **Запреты:** тяжелые зависимости, сторонние платные сервисы SMS/email.
- **Критерий приемки (E1–E3):** Unit-тесты с моками проверяют создание ящика, таймаут ожидания письма, регулярные выражения для OTP (4-8 цифр) и ссылок активации (8/8 тестов зеленые).

---

### [TASK-003] Движок полуручной разведки `recon.py`
- **Статус:** ✅ `DONE`
- **Requires:** `TASK-001`
- **Inputs:** URL целевого сервиса
- **Outputs:** `src/reverse_api/recon.py`, `tests/test_recon.py`
- **Разрешенные пути:** `src/reverse_api/recon.py`, `tests/test_recon.py`
- **Запреты:** сохранение паролей и токенов в открытом виде в репозиторий.
- **Критерий приемки (E1–E3):** Перехватчик запускает браузер, слушает сетевые запросы, отфильтровывает картинки, CSS и внешнюю аналитику, сохраняя структурированный лог запросов отправки форм (5/5 тестов зеленые).

---

### [TASK-004] Синтезатор рецептов `synthesizer.py`
- **Статус:** ⏳ `PENDING`
- **Requires:** `TASK-003`
- **Inputs:** Очищенный сетевой лог сессии от `recon.py`
- **Outputs:** `src/reverse_api/synthesizer.py`, `tests/test_synthesizer.py`
- **Разрешенные пути:** `src/reverse_api/synthesizer.py`, `tests/test_synthesizer.py`
- **Запреты:** жесткая привязка к форматам одного сервиса.
- **Критерий приемки (E1–E3):** Корректное выделение эндпоинта отправки формы, сопоставление полей (login, email, password), поиск CSRF-токена в предшествующих GET-ответах и формирование валидного JSON-рецепта `ServiceRecipe`.

---

### [TASK-005] Автономный исполнитель `runner.py` на `curl_cffi`
- **Статус:** ⏳ `PENDING`
- **Requires:** `TASK-002`, `TASK-004`
- **Inputs:** `ServiceRecipe`, `temp_mail.py`, `vault.py`
- **Outputs:** `src/reverse_api/runner.py`, `tests/test_runner.py`
- **Разрешенные пути:** `src/reverse_api/runner.py`, `tests/test_runner.py`
- **Запреты:** использование Chromium/Playwright на этапе повтора (ANTI-1); использование голого `httpx` без TLS-эмуляции (ANTI-2).
- **Критерий приемки (E1–E4):** Исполнитель выполняет HTTP-шаги через `curl_cffi`, запрашивает почту, подтверждает OTP и сохраняет профиль в `vault.py`. Потребление памяти < 50 МБ.

---

### [TASK-006] CLI интеграция команд
- **Статус:** ⏳ `PENDING`
- **Requires:** `TASK-003`, `TASK-005`
- **Inputs:** CLI модуль
- **Outputs:** `src/reverse_api/cli.py`
- **Разрешенные пути:** `src/reverse_api/cli.py`
- **Запреты:** раздувание TUI и блокировка неинтерактивных сценариев.
- **Критерий приемки (E1–E4):** Поддержка команд `reverse-api-engineer recon <url>` и `reverse-api-engineer run-recipe <recipe.json>`.
