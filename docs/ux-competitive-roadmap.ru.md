# TelegramResenderBot: UX/UI тестирование, конкуренты и roadmap

Дата среза: 2026-06-12.

Этот документ написан как рабочее задание для следующей LLM. Он фиксирует текущее
поведение репозитория, проверенные команды, конкурентный контекст, UX/UI баги и
итерационный план следующих релизов.

Статус после релиза `1.2.0`: раздел 7 использован как acceptance baseline для
bugfix/UX hardening релиза, а `v1.2.0` реализовал guided request flow:
шаблонную заявку, required-field validation, preview/confirm и общий request id.
Дальнейшая итерационная разработка начинается с `v1.3.0`.

## 1. Что это за приложение

`TelegramResenderBot` - self-hosted Telegram-бот на Python/aiogram. Его текущая
задача узкая: принимать текстовые заявки от разрешенных Telegram-пользователей и
пересылать их в один заданный чат или группу.

Текущий поток:

1. Пользователь пишет боту текст.
2. `app.incoming_from_message` приводит объект aiogram к доменной модели.
3. `ResenderService.handle_text` проверяет `username` по CSV whitelist.
4. Если пользователь разрешен, бот формирует текст через `MessageFormatter` и
   отправляет его в `TELEGRAM_RESENDER_FORWARD_CHAT_ID`.
5. Пользователь получает короткий ответ об успехе или отказе.

Текущие команды:

- `/start` - статическая инструкция на английском.
- `/help` - статическая помощь на английском.
- `/avto` - статический ответ "Vehicle request mode is enabled...", без реального
  состояния режима.

Важное позиционирование: это не универсальный "Telegram forwarding platform".
Сейчас это минимальный частный intake-бот для заявок, ближе к "форма в Telegram с
ручным whitelist", чем к Junction Bot, AutoForward или TeleFeed.

## 2. Проверки запуска и качества

Среда проверки:

- Рабочая папка: `C:\Users\KRT\Documents\GitHub\TelegramResenderBot`.
- Remote: `https://github.com/krotname/TelegramResenderBot.git`.
- Ветка: `master`, синхронизирована с `origin/master`.
- Теги: `v1.0.1`, `v1.0.0`.
- Python: `3.14.5`.
- `gh auth status`: токен аккаунта `krotname` в keyring недействителен. Для
  authenticated GitHub CLI операций нужно выполнить `gh auth refresh -h github.com`.

Команды и результаты:

- `git fetch --prune --tags` - успешно.
- `python -m pytest` - 16 тестов прошли, coverage 97.94%.
- `python -m ruff check .` - успешно.
- `python -m mypy src tests` - ошибка:
  `tests\unit\test_cli.py:27: Module "telegram_resender.cli" does not explicitly export attribute "asyncio" [attr-defined]`.
- `python -m telegram_resender` без полной конфигурации - сырой traceback Pydantic
  с отсутствующим `TELEGRAM_RESENDER_FORWARD_CHAT_ID`.
- `python -m telegram_resender` с фиктивными `BOT_TOKEN`, `FORWARD_CHAT_ID` и
  `whitelist.example.csv` не падает на локальной валидации, но без реального
  Telegram token полноценный polling не был подтвержден. Команда была остановлена
  по timeout.

## 3. UX/UI тестирование

У приложения нет web UI. Поэтому UI/UX проверялся как Telegram conversational UI,
CLI startup UX и operator/admin UX.

Проверенные пользовательские сценарии:

1. Первый запуск без `.env`.
2. Первый запуск с неполным `.env`.
3. Запуск с полной, но фиктивной конфигурацией.
4. `/start`, `/help`, `/avto`.
5. Разрешенный пользователь отправляет текст.
6. Неизвестный пользователь отправляет текст.
7. Пользователь без Telegram username отправляет текст.
8. Пользователь отправляет пустой или бессодержательный текст.
9. Пользователь отправляет не текст: фото, документ, стикер, голосовое.
10. Администратор получает пересланную заявку.
11. Оператор меняет whitelist.

### Найденные баги и UX-проблемы

#### TRB-UX-001 - сырой traceback при ошибках конфигурации

Серьезность: high.

Текущее поведение: при отсутствии обязательных переменных окружения пользователь
видит Python traceback и Pydantic internals. Это выглядит как авария приложения.

Ожидаемое поведение: CLI должен печатать короткую понятную ошибку:

```text
Configuration error: TELEGRAM_RESENDER_FORWARD_CHAT_ID is required.
Create .env from .env.example and fill BOT_TOKEN, FORWARD_CHAT_ID, WHITELIST_PATH.
```

Acceptance criteria:

- `telegram-resender` ловит `ValidationError`, `FileNotFoundError` и ошибки
  авторизации Telegram на верхнем уровне.
- Exit code для ошибок конфигурации: `2`.
- В stderr нет traceback, если не включен `TELEGRAM_RESENDER_LOG_LEVEL=DEBUG`.
- Добавлены unit-тесты CLI.

#### TRB-UX-002 - язык интерфейса не совпадает с русским README и целевым пользователем

Серьезность: medium.

Текущее поведение: README основной на русском, но все сообщения бота на английском.
Пользователь, который пришел из русской документации, получает чужой язык в боте.

Ожидаемое поведение: язык должен быть явно выбран. Для текущего репозитория
рекомендуется сделать русский дефолтом и оставить английский через настройку
`TELEGRAM_RESENDER_LOCALE=en`.

Acceptance criteria:

- Все дефолтные пользовательские сообщения доступны на `ru` и `en`.
- README содержит пример настройки locale.
- Тесты проверяют оба языка.

#### TRB-UX-003 - не текстовые сообщения игнорируются молча

Серьезность: high.

Текущее поведение: router обрабатывает только `F.text`. Если пользователь отправит
фото пропуска, документ, голосовое или стикер, он может не получить никакого ответа.

Ожидаемое поведение: бот отвечает, что принимает только текстовую заявку, и дает
пример формата.

Acceptance criteria:

- Добавлен fallback handler для unsupported message types.
- Ответ локализован.
- Conversation-тест покрывает отправку не текстового сообщения.

#### TRB-UX-004 - команда `/avto` обещает режим, которого нет

Серьезность: medium.

Текущее поведение: `/avto` отвечает "Vehicle request mode is enabled", но никакой
режим не включается. Следующее сообщение обрабатывается тем же общим handler.

Ожидаемое поведение: либо команда переименована в `/template` и просто показывает
шаблон, либо реализуется настоящий диалоговый режим с состоянием.

Рекомендация для следующего релиза: переименовать смысл в "показать шаблон", без
state machine. State machine отложить до v1.2.0.

#### TRB-UX-005 - бот принимает любую строку как заявку

Серьезность: high.

Текущее поведение: whitelisted пользователь может отправить `hi`, и это уйдет
администратору как принятая заявка. README и `/start` говорят о здании, времени,
модели авто и номере, но код это не проверяет.

Ожидаемое поведение: на первом этапе бот должен хотя бы показывать шаблон и
предупреждать о неполной заявке. В следующей итерации - валидировать обязательные
поля.

Acceptance criteria для bugfix-релиза:

- `/start` и `/template` показывают пример.
- Если текст короче минимального порога или похож на приветствие, бот просит
  заполнить заявку по шаблону и не пересылает ее.

#### TRB-UX-006 - отказ пользователю без username непонятен

Серьезность: medium.

Текущее поведение: если `username` отсутствует, пользователь получает общий отказ
"Ask an administrator to add your Telegram username". Но username у него может не
быть создан.

Ожидаемое поведение: отдельное сообщение:

```text
У вас не задан Telegram username. Создайте username в Telegram Settings или
попросите администратора включить доступ по chat id: <id>.
```

Acceptance criteria:

- Причины `missing_username` и `unknown_username` имеют разные тексты.
- В сообщении для `missing_username` есть `chat_id`.
- Тесты покрывают обе причины.

#### TRB-UX-007 - whitelist нельзя обновить без операционного трения

Серьезность: medium.

Текущее поведение: whitelist загружается при старте. Для добавления пользователя
оператор должен править файл и перезапускать процесс.

Ожидаемое поведение для ближайших версий: reload без рестарта или admin-команда.

Acceptance criteria для v1.1.0:

- Добавить `--check-config`/`doctor`, который показывает путь whitelist и число
  загруженных пользователей.
- В README явно описать, что после изменения файла нужен restart.

Acceptance criteria для v1.3.0:

- Admin-команда `/reload_whitelist`.
- Admin-команды доступны только `TELEGRAM_RESENDER_ADMIN_IDS`.

#### TRB-UX-008 - админское сообщение слишком бедное для обработки заявок

Серьезность: medium.

Текущее поведение: формат содержит заголовок, пользователя, source chat и текст.
Нет времени заявки, id сообщения, статуса обработки, нормализованного шаблона,
признака неполных полей.

Ожидаемое поведение: администратор должен быстро понять, кто, когда, что просит и
что делать дальше.

Acceptance criteria:

- В forward message добавить `Submitted at`, `Request id`, `Telegram user`.
- Сохранить совместимость старого формата в тестах через snapshot или отдельный
  formatter version.

#### TRB-UX-009 - нет диагностического режима

Серьезность: medium.

Текущее поведение: чтобы понять, готов ли бот к запуску, нужно стартовать polling.

Ожидаемое поведение: команда `telegram-resender doctor` или
`python -m telegram_resender doctor`:

- проверяет обязательные переменные;
- проверяет наличие whitelist;
- показывает число пользователей;
- проверяет формат token без вывода token;
- опционально проверяет доступ к target chat, если есть флаг `--telegram-check`.

#### TRB-UX-010 - несоответствие лицензии в metadata

Серьезность: medium для репозитория, low для end-user UX.

Текущее поведение: `LICENSE` и README говорят GPL-3.0, а `pyproject.toml` содержит
`license = "MIT"`.

Ожидаемое поведение: выбрать одну лицензию. Если GPL-3.0 остается намеренно,
обновить `pyproject.toml` и package metadata.

Acceptance criteria:

- `pyproject.toml` и `LICENSE` согласованы.
- Добавлен тест/CI grep или packaging check.

## 4. Рейтинг конкурентов

Методика: это не официальный рейтинг рынка. Оценка составлена по публичным
признакам: полнота функций, наличие UI, масштаб/популярность, активность
развития, надежность, документация и близость к задаче пересылки Telegram-сообщений.

### 4.1 Коммерческие и hosted продукты

1. Junction Bot
   - Позиция: лидер по ширине функций и зрелости workflow.
   - Доказательства: продукт заявляет работу с 2017 года, 20 000+ пользователей и
     1M+ сообщений в день. Поддерживает account connection, history copying,
     filtering, text modification, GPT processing, manual moderation, topic mapping
     и folder forwarding.
   - Источники: `https://www.junctionbot.io/`,
     `https://www.junctionbot.io/features/message-forwarding`,
     `https://www.junctionbot.io/documentation/getting-started`.

2. AutoForward For Telegram / Auto Forward Messages
   - Позиция: сильный массовый конкурент с mobile/web UI и cloud-подходом.
   - Доказательства: есть iOS, Android, Web App, cloud processing, free/premium
     plans, AI Mode, rewrite/translate/summarize/OCR, 600 msg/min и 99.9% uptime по
     self-claim. App Store показывает рейтинг 5.0 по 18 оценкам и подробный version
     history.
   - Важное ограничение: Trustpilot содержит негативные отзывы, поэтому лидерство
     по feature velocity не равно доказанной репутационной надежности.
   - Источники: `https://github.com/redf0x1/Auto-Forward-Messages`,
     `https://apps.apple.com/us/app/autoforward-for-telegram/id6447486093`,
     `https://www.trustpilot.com/review/autoforwardtelegram.com`.

3. TeleFeed
   - Позиция: сильный hosted forwarding-сервис по производительности и сложным
     источникам.
   - Доказательства: заявляет production since 2019, 10M+ сообщений в день,
     1 000/min per account, 99.98% uptime за 90 дней, filters, translations,
     transformations, protected/restricted content workflows.
   - Источник: `https://telegrambotting.com/tg_feed`.

4. TForwarder / mobile auto-forward apps
   - Позиция: полезные Android/iOS инструменты для личной автоматизации.
   - Доказательства: Google Play описание TForwarder говорит о пересылке из
     выбранных Telegram chats в канал/группу/пользователю, keyword filters и выборе
     скрывать ли источник.
   - Источник: `https://play.google.com/store/apps/details?id=com.blank_paper.app.t_forwarder2`.

5. Generic automation platforms: Make, Zapier, n8n
   - Позиция: конкурируют за бизнес-автоматизацию, но слабее в Telegram-specific
     forwarding, private/restricted chats и сохранении Telegram-native контекста.
   - Использовать как ориентир для UX onboarding и webhooks, но не как прямого
     функционального лидера.

### 4.2 Open-source/self-hosted проекты

1. `aahnik/tgcf`
   - Позиция: open-source лидер по популярности.
   - Доказательства: GitHub показывает 1.6k stars, 870 forks, 24 releases, latest
     v1.1.7 от 2022-12-12. Поддерживает live/past forwarding, bot или user account,
     advanced chat forwarding.
   - Источник: `https://github.com/aahnik/tgcf`.

2. `MrMissx/Telegram_Forwarder`
   - Позиция: популярный self-hosted forwarder.
   - Доказательства: GitHub показывает 637 stars, 475 forks. Есть Docker,
     `chat_list.json`, one-to-many destinations, filters, blacklist, topics.
   - Источник: `https://github.com/MrMissx/Telegram_Forwarder`.

3. `redf0x1/Auto-Forward-Messages`
   - Позиция: open repo как витрина commercial/cloud продукта.
   - Доказательства: GitHub API на 2026-06-12 показал 111 stars и 40 forks. README
     описывает cloud bot, AI mode, mobile/web apps.
   - Источник: `https://github.com/redf0x1/Auto-Forward-Messages`.

4. `MohammadShabib/Telegram-Forwarder-Bot`
   - Позиция: self-hosted CLI/TUI forwarder с большим функциональным охватом, но
     меньшей популярностью.
   - Доказательства: GitHub API на 2026-06-12 показал 52 stars и 44 forks. README
     описывает multi-account support, all message types, live/history forwarding,
     deletion, media downloading, user tracking, rich console interface.
   - Источник: `https://github.com/MohammadShabib/Telegram-Forwarder-Bot`.

5. `Linuxmaster14/TGForwarder`
   - Позиция: небольшой self-hosted проект, но ближе к production-конфигурации, чем
     TelegramResenderBot.
   - Доказательства: README описывает multiple source/target mapping,
     one-to-many/many-to-one, user/bot accounts, optional remove forward signature,
     rate limit handling, env config.
   - Источник: `https://github.com/Linuxmaster14/TGForwarder`.

6. `krotname/TelegramResenderBot`
   - Позиция: не входит в commercial top-5 и не входит в open-source top-5 по
     популярности. Может войти только в нишевый рейтинг "простые private whitelist
     intake bots" благодаря качеству тестов, типизации и security baseline.
   - Доказательства: GitHub API на 2026-06-12 показал 0 stars, 0 forks. Функционально
     есть только один источник - личные сообщения боту, один target chat, текстовые
     сообщения, CSV whitelist.

Вывод по конкурентности:

- Как Telegram forwarding platform проект неконкурентен.
- Как маленький self-hosted private intake bot он имеет здоровую инженерную базу,
  но слабый UX и почти нулевую продуктовую упаковку.
- Реалистичный путь: не пытаться догнать Junction/TeleFeed по универсальной
  пересылке, а занять узкую позицию "приватный бот заявок с whitelist, понятным
  onboarding, audit log и безопасным self-hosted deployment".

## 5. Что лидеры добавляют в changelog

### Junction Bot

Публичный канал `https://t.me/s/junction_bot_news` показывает направление развития:

- подробные tutorial video по базовой настройке, private chats, filters, link
  replacements, edit sync, folders, Google Drive и multiple accounts;
- AI digests, group digests, trend watching prompts, reactions digest;
- Projects для организации большого числа forwardings;
- digest history для защиты от дублей;
- исправления digest generation и provider reliability;
- cross-posting Telegram to Max.

Что важно для TelegramResenderBot:

- лидеры улучшают не только forwarding, но и "операторскую навигацию";
- акцент смещается к AI-summary, noise filtering, projects/folders и reliability;
- onboarding через tutorial и понятные menu paths считается частью продукта.

### AutoForward For Telegram

App Store version history показывает быстрый feature cadence:

- 1.0.51 - rewards center, addons, minor bug fixes;
- 1.0.50 - publish to other platforms;
- 1.0.49 - UI/UX improvements, performance and stability;
- 1.0.44 - schedule start time, full watermark, higher AI character limits,
  button sender filters, affiliate-id replacement;
- 1.0.34 - reply/reply_regex in whitelist/blacklist, combined user+keyword filters,
  folder list tasks;
- 1.0.33 - AI Mode, smart rewrites and OCR;
- 1.0.28 - watermark, backup/restore account, speed/stability.

Что важно для TelegramResenderBot:

- лидеры превращают правила пересылки в управляемые "tasks";
- whitelist/blacklist развиваются до комбинированных условий;
- UI/UX и performance попадают в changelog как самостоятельная ценность;
- backup/restore и folders - важная часть доверия.

### TeleFeed

Версионированный changelog в открытом доступе не найден в рамках проверки. Но
product page фиксирует стратегические изменения: 7 лет адаптации к Telegram API,
устойчивость к rate limits/FloodWait, protected/restricted content, filters,
translation, transformations, high throughput и status/uptime.

Что важно для TelegramResenderBot:

- даже если проект не конкурирует по масштабу, ему нужен `doctor`, healthcheck и
  понятное поведение при Telegram API ошибках;
- надежность должна быть видна пользователю, а не только существовать в коде.

## 6. В чем TelegramResenderBot уступает лидерам

1. Нет UI для настройки правил. Все через env и CSV.
2. Нет multi-source/multi-destination.
3. Нет web/mobile/Telegram mini-app панели.
4. Нет задач/rules/folders/projects.
5. Нет history forwarding и live/history режима.
6. Нет поддержки media, documents, voice, photos, polls.
7. Нет фильтров по ключевым словам, типам сообщений, пользователям, reply context.
8. Нет transform pipeline: replace, cleanup, header/footer, translate.
9. Нет scheduler, delay, digest, deduplication.
10. Нет AI features.
11. Нет admin-команд и runtime reload.
12. Нет observability: healthcheck, metrics, request log, delivery status.
13. Нет Docker/deploy guide/systemd examples.
14. Нет нормального first-run UX.
15. Нет рынка: stars/forks равны нулю, нет screenshots/video demo/use cases.

Сильные стороны текущего проекта:

1. Простая доменная модель.
2. Хорошая тестовая база для размера проекта.
3. Строгая типизация задумана и частично работает.
4. Секреты вынесены в environment.
5. Есть CI, CodeQL, Scorecard/Best Practices hardening.
6. Узкая private/self-hosted ниша может быть ценностью для организаций, которым не
   подходят hosted forwarding-сервисы.

## 7. Acceptance baseline v1.1.0: Bugfix & UX Hardening

Цель: исправить найденные UX-баги без расширения продукта в универсальный
forwarding platform.

### Обязательные задачи v1.1.0

1. Исправить CLI startup UX.
   - Ловить `ValidationError`, `FileNotFoundError`, Telegram auth/startup errors.
   - Печатать понятные ошибки без traceback.
   - Добавить `--debug` или respect `LOG_LEVEL=DEBUG` для traceback.

2. Добавить диагностический режим.
   - Команда: `telegram-resender doctor`.
   - Проверяет env, whitelist path, whitelist count, polling timeout, locale.
   - Не печатает token.

3. Починить `mypy src tests`.
   - Не обращаться к `cli.asyncio` из теста напрямую или явно экспортировать
     dependency seam.
   - Лучше: вынести `run_async = asyncio.run` или тестировать через monkeypatch
     `asyncio.run` на модуле с корректной типизацией.

4. Локализовать сообщения.
   - Дефолт: `ru`.
   - Поддержать `TELEGRAM_RESENDER_LOCALE=ru|en`.
   - Все тексты команд и ошибок хранить централизованно.

5. Сделать `/avto` честной командой.
   - Вариант для v1.1.0: оставить alias, но ответить шаблоном заявки.
   - Добавить новую команду `/template`.
   - Не писать "mode enabled", пока нет state machine.

6. Добавить fallback для unsupported message types.
   - Ответ: "Пока принимаю только текстовые заявки. Используйте /template".
   - Покрыть тестом.

7. Разделить причины отказа.
   - `missing_username`: объяснить, как задать username, и показать chat id.
   - `unknown_username`: просить администратора добавить username.

8. Улучшить формат админского сообщения.
   - Добавить `Request id`, `Submitted at`, `From`, `Source chat`.
   - Сохранить deterministic tests.

9. Согласовать лицензию.
   - Если проект GPL-3.0, исправить `pyproject.toml`.

10. Обновить README.
    - Реальный first run.
    - `doctor`.
    - Пример `.env`.
    - Пример whitelist.
    - Пример заявки.
    - Ограничение: только текстовые сообщения.

### Definition of Done v1.1.0

- `python -m pytest` проходит.
- `python -m ruff check .` проходит.
- `python -m mypy src tests` проходит.
- `telegram-resender doctor` дает понятный отчет.
- Запуск без `.env` не печатает traceback.
- Conversation-тесты покрывают `/start`, `/help`, `/template`, unknown user,
  missing username, unsupported content, short/invalid request.
- README и CHANGELOG обновлены.

## 8. Patch notes на пять версий после исправления багов

Ниже - план после v1.1.0. Каждая версия должна быть реализуема отдельно и не
ломать предыдущий UX.

### v1.2.0 - Guided Request Flow

Цель: превратить бот из "перешли любой текст" в понятный сценарий подачи заявки.

Планируемые изменения:

- Добавить шаблон заявки с полями:
  - объект/здание;
  - дата и время прибытия;
  - ФИО/контакт, если нужно;
  - модель авто;
  - госномер;
  - комментарий.
- Добавить легкую валидацию обязательных полей.
- Добавить ответ "заявка неполная" с перечислением недостающих полей.
- Добавить preview перед пересылкой, если включено
  `TELEGRAM_RESENDER_CONFIRM_BEFORE_FORWARD=true`.
- Добавить request id, который видит и пользователь, и администратор.
- Обновить conversation tests на успешный и неполный сценарии.

Out of scope:

- Сложная FSM с редактированием каждого поля.
- Web UI.
- AI parsing.

Ожидаемый changelog:

- Added guided request template for vehicle access requests.
- Added basic request validation and missing-field feedback.
- Added optional confirmation before forwarding.
- Added shared request id in user and admin messages.

### v1.3.0 - Admin Operations

Цель: снизить ручной труд администратора и убрать необходимость рестарта для
типовых операций.

Планируемые изменения:

- Добавить `TELEGRAM_RESENDER_ADMIN_IDS`.
- Добавить admin-команды:
  - `/admin_status`;
  - `/reload_whitelist`;
  - `/whitelist_count`;
  - `/whoami`.
- Добавить безопасный reload whitelist с отчетом об ошибках CSV.
- Добавить audit log admin actions в stdout/log.
- Добавить документацию "как узнать chat id/admin id".
- Добавить тесты прав доступа: admin/non-admin.

Out of scope:

- Редактирование whitelist прямо из Telegram.
- База данных.

Ожидаемый changelog:

- Added admin-only operational commands.
- Added runtime whitelist reload without process restart.
- Added whitelist diagnostics and CSV validation feedback.
- Documented admin id setup and operational workflow.

### v1.4.0 - Routing Rules

Цель: перейти от одного target chat к нескольким простым правилам маршрутизации,
не превращая проект в Junction Bot.

Планируемые изменения:

- Добавить optional config file `routes.yml` или `routes.json`.
- Поддержать правила:
  - `name`;
  - `target_chat_id`;
  - `allowed_usernames`;
  - `keywords_any`;
  - `keywords_none`;
  - `template`;
  - `enabled`.
- Сохранить backward compatibility с `TELEGRAM_RESENDER_FORWARD_CHAT_ID`.
- Добавить команду `doctor`, которая валидирует routes config.
- Добавить unit-тесты rule matching.
- Добавить integration-тест нескольких маршрутов.

Out of scope:

- Userbot/account connection.
- Private channel scraping.
- Protected content bypass.

Ожидаемый changelog:

- Added optional multi-route forwarding configuration.
- Added keyword allow/block filters per route.
- Kept single-chat env configuration backward compatible.
- Added route validation to doctor command.

### v1.5.0 - Delivery Reliability

Цель: сделать пересылку проверяемой и устойчивой к Telegram API сбоям.

Планируемые изменения:

- Добавить retry/backoff для `send_message`.
- Добавить обработку rate limit/FloodWait-style ошибок aiogram.
- Добавить SQLite request log:
  - request id;
  - sender;
  - created_at;
  - validation status;
  - delivery status;
  - last error.
- Добавить idempotency: один request id не должен отправляться дважды при retry.
- Добавить `telegram-resender doctor --storage-check`.
- Добавить `telegram-resender export-requests --since YYYY-MM-DD`.
- Добавить тесты retries и delivery log.

Out of scope:

- Полноценная web-панель.
- Distributed queue.

Ожидаемый changelog:

- Added persistent request delivery log.
- Added retry and backoff for transient Telegram send failures.
- Added idempotent delivery by request id.
- Added request export for operators.

### v1.6.0 - Deployment & Operator Experience

Цель: сделать проект удобным для установки и сопровождения.

Планируемые изменения:

- Добавить Dockerfile и docker-compose example.
- Добавить systemd service example.
- Добавить `.env.production.example`.
- Добавить structured logging option: `TEXT` или `JSON`.
- Добавить `/health` через optional lightweight HTTP server или CLI health command,
  если HTTP server нежелателен.
- Добавить screenshots/terminal examples в README.
- Добавить "known limitations" против Junction/AutoForward/TeleFeed:
  - no userbot;
  - no protected chat bypass;
  - no media forwarding;
  - no AI;
  - privacy-first self-hosted scope.

Out of scope:

- Hosted SaaS.
- Mobile app.
- AI paid features.

Ожидаемый changelog:

- Added Docker and systemd deployment examples.
- Added production environment template.
- Added structured logging and health diagnostics.
- Improved README with operator-focused setup examples.

## 9. Дальнейшее позиционирование

Не копировать лидеров один к одному. Junction Bot, AutoForward и TeleFeed уже
занимают рынок универсальной автопересылки. Для `TelegramResenderBot` рациональная
ниша:

"Простой self-hosted Telegram-бот для приватных заявок, где важны whitelist,
понятный UX, audit trail, безопасность и минимальная зависимость от внешних hosted
сервисов."

Критерии успеха через 5 версий:

- Пользователь без чтения кода понимает, как подать заявку.
- Администратор без SSH может проверить статус и reload whitelist.
- Оператор видит request id и delivery status.
- Проект разворачивается через Docker/systemd за 10 минут.
- README честно объясняет, чем проект не является.
- Все проверки `pytest`, `ruff`, `mypy` проходят.
