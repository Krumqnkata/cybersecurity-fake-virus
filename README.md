# Дигитални детективи — Cyber Classroom 7.0

Учителско приложение за визуална демонстрация на признаци, които могат да се срещнат при компютърен инцидент. Сцените изглеждат като отделни Windows приложения, но не извършват зловредни действия.

> Това е видимо обозначена учебна симулация. Няма реален WannaCry, шифроване, сканиране, инсталиране, срив или рестартиране.

Платформа: Windows 10/11, Python 3.10+ и български учителски интерфейс. Не са нужни администраторски права.

## Стартиране

```powershell
py -m pip install pillow
py cyber_classroom.py
```

`Pillow` е единствената допълнителна зависимост. Ако липсва, native сцените продължават да работят, а сцената с кадър от работния плот използва безопасна статична алтернатива.

Преди урок:

1. Натиснете **„Провери готовността“**.
2. Проверете глобалните комбинации, временната папка, браузъра и Pillow.
3. Изберете ресурсен профил. **„Училищен безопасен“** е препоръчаният и стандартен избор.
4. Изберете продължителност **8, 12 или 15 минути**. Стандартната свързана история е 12 минути.
5. Изберете **„Автоматично“** или **„Учителско темпо“**.
6. Преди RAM-only кадъра затворете чувствителни прозорци на работния плот.
7. Направете пълна проба на конкретния демонстрационен компютър.

## Ресурсни профили

| Профил | Локални browser tabs | Живи effect прозорци общо | Screenshot FPS | Вътрешен image target |
| --- | ---: | ---: | ---: | ---: |
| Училищен безопасен (по подразбиране) | 4 | 6 | до 8 | до 960 × 540 |
| Балансиран (изричен избор) | 6 | 8 | до 12 | до 1280 × 720 |

Абсолютният лимит е 8 tabs и 8 effect прозореца. Fullscreen stage се брои като един effect прозорец. Контролният панел не се брои. Затварящите се, но още живи Win32 прозорци продължават да се броят и не се заменят преждевременно.

Има wall-clock ограничения независимо от скоростта на историята:

- поне 3 секунди между реални browser launches;
- поне около 1 секунда между нови effect прозорци;
- най-много една скъпа визуална сцена;
- без наваксващ burst след пауза или забавяне.

Това е умишлено намаление спрямо стария лимит от 20 tabs и 12 popup прозореца. Реализмът идва от различни интерфейси и свързано поведение, не от натоварване.

## Управление

| Контрол | Действие |
| --- | --- |
| `Ctrl+Alt+P` | Глобална пауза/продължаване, включително при фокусиран браузър. |
| `Ctrl+Alt+Q` | Глобално спиране, cleanup и изход. |
| `Esc` | Спиране от Tk или native Win32 прозорец. |
| `F6` | Следваща глава от Tk или native Win32 прозорец. |
| `F11` | Fullscreen toggle от Tk или native Win32 прозорец. |
| **Повтори глава** | Инвалидира старите callbacks и стартира текущата глава отначало. |
| **Спри / изчисти** | Идемпотентно спиране и двуфазно освобождаване. |

При пауза учителят избира дали сцените да останат видими за обсъждане, или да се скрият. Един pause-aware часовник замразява timers, reveals, progress, sound, spawning и browser actions. В **„Учителско темпо“** историята спира на границите между главите и продължава с **Next/F6**.

## Тематични звуци

Опцията **„Тематичен звук“** включва 19 кратки различими WAV сигнала, включително отделни cues за browser/download, UAC, CaveDepths installer, firewall, Task Manager, runtime updater, scan, error, terminal, ransomware reconstruction, crash, reboot и debrief. **„Тест“** просвирва пример преди урок. Генерираните файлове са включени в `sounds`, без download, микрофон или външна библиотека. Ако някой липсва, приложението синтезира временен безопасен fallback и премахва кеша при изход.

Всеки сигнал може да бъде заменен: поставете PCM WAV файл с точното име в папка `sounds` до `cyber_classroom.py`. Поддържаните имена и препоръките са описани в [sounds/README.md](sounds/README.md). При пауза, **„Спри / изчисти“**, изключване на отметката или изход текущият звук спира веднага.

Опцията **„Windows известия“** е включена по подразбиране и изпраща ясно означени учебни toast известия през локалния Windows Notification Center при подозрителната активност, края на фалшивото сканиране и края на runtime update сцената. Те нямат бутони, линкове или команди, rate-limited са и изтичат след около 20 минути. Изключването на отметката оставя само вътрешната визуална notification сцена. Focus Assist, Do Not Disturb или училищна групова политика може да скрие банера, без да прекъсне историята.

## Различните учебни интерфейси

- **CaveDepths Mod Setup** — wizard около 600 × 440 с Welcome, Options, Installing и Completed; Back, Next, Cancel и Finish са активни. Неравномерните фази са предварително зададени.
- **User Account Control reconstruction** — topmost consent dialog за CaveDepths с Unknown publisher, file origin, details и работещи Yes/No действия. Това е обикновен application window и не иска elevation.
- **Firewall warning** — свързано предупреждение за `mod_update_helper.exe`, private/public network choices и видим резултат без създаване на firewall rule.
- **Task Manager classroom view** — resizable process table с променящи се CPU, Disk, Network и GPU стойности и работещ `End demo task`. Данните са синтетични; не се изброяват реални процеси.
- **Block Runtime updater** — отделен staged updater с fictional signature check, progress, Cancel и Completed състояние; не инсталира компонент.
- **Notification** — малък `WS_EX_NOACTIVATE` toast до work area, с източник, час, Details и dismiss, плюс опционално истинско известие в Windows Notification Center. И двете са видимо означени като учебна симулация.
- **Security warning** — отделен restrained dialog с fictional process, severity и работещи разширяеми technical details.
- **Application errors** — четири авторски варианта: not responding, missing component, access denied и failed update.
- **Classroom Terminal** — resizable native прозорец, Consolas, bounded prerecorded scrollback и неравномерно време. Не се стартира shell и не се изпълнява команда.
- **PC Defender** — отделно fictional scanner приложение със sidebar, synthetic fixture, Pause/Resume, Stop и Details; състояния scanning, paused, cancelled и completed.
- **Ransomware reconstruction** — независимо movable/closable native приложение с timer, scrollable обяснение, nonpayable demo ID и брой `.locked` имена от текущата сесия.
- **Screen distortion** — един кадър от основния монитор, само в RAM; subtle displacement, tears, melt/tunnel и recovery. Има reduced-motion и static режими.
- **Crash/reboot** — свързана fullscreen възстановка: BSOD прогрес до 100%, декоративен несканируем code element и автоматични `Restarting`, black transition, `Getting Windows ready` и `Welcome` фази. Учебната маркировка и emergency controls остават видими; Windows не се срива и не се рестартира.

Шестте loopback страници разказват една свързана история. Първата прилича на измислен портал за Minecraft Java модове и предлага **CaveDepths** за версия 1.21.1/Fabric, но вместо нормален mod файл показва подозрителен `.exe` installer. След нея се появяват тематично свързани gaming reward, фалшив web scan, предупреждение за игровия акаунт, измислен runtime update и FPS booster. Всеки сайт има различни layout, title, favicon и плътност. Няма painted fake address bar; истинският `127.0.0.1` адрес остава видим и никъде не се прави реален download.

## Браузърна изолация и локални страници

Edge/Chrome се стартира със собствен нов временен `--user-data-dir`. Първият launch е отделен owned window, следващите са `--new-tab`. Процесите се създават suspended, поставят се в частен Windows Job и после се продължават. Cleanup затваря само този Job — никога процеси по име и никога несвързани браузърни прозорци.

Ако организационна `UserDataDir` политика е зададена, сцената отказва да я заобиколи и показва обяснение. Няма fallback към нормалния профил.

Съдържанието се обслужва само на `127.0.0.1` със случаен 40-hex route. CSP забранява външни ресурси; има само inline локални styles/script с nonce и data-URI favicons. Командите са allowlisted, generation-tagged, rate-limited и са само POST с празно body. Видимите страници poll-ват приблизително на 1 секунда, hidden страниците — на 5 секунди, а при прекъсване backoff-ват до 10 секунди.

Chromium flags като `--disable-background-networking` ограничават фоновата работа, но **не са пълна network sandbox**. Самите предоставени страници и assets работят без интернет и нямат външни URL-и. Проверете disconnected operation на конкретната училищна конфигурация; managed browser компоненти могат да имат собствено поведение извън контрола на приложението.

## Осемте учебни файла

В нова временна папка се създават точно 8 истински UTF-8 `.txt` файла. In-memory manifest-ът съдържа имената и SHA-256 на създаденото съдържание, без да добавя девети учебен файл.

Само manifest entries в точната учебна папка могат да бъдат преименувани на `.locked`. Кодът проверява containment, regular file, replacement links, съдържание и conflicts. Не следва symlinks и не презаписва редактиран или конфликтен файл. Съдържанието никога не се шифрова. При normal stop непроменените имена се връщат, а папката остава за проверка.

## Надеждност и emergency cleanup

- `Classroom.events` има отделна недропваща priority пътека за Quit/Stop/hotkey failure, bounded normal queue, coalescing и максимум 12 normal events на tick.
- Всеки `NativeEffect` има собствен Win32 message-loop thread и bounded command queue. Controls се създават в един batch; text/progress/edit updates се coalesce-ват и се изпълняват на owner thread.
- Tk и `ImageTk` остават само на Tk thread. Native callbacks се връщат като controller events. Това отстранява Python 3.13 GIL срива от предишната версия.
- Stop първо прекратява scheduling, маха overlays/topmost поведение и освобождава owned browser. Native joins и file restoration са отделна bounded cleanup фаза.
- Session/chapter generation IDs отхвърлят callbacks от отменен installer, стар tab, затворен прозорец или предишен run.
- Stage пази layout items и променя само dynamic progress/spinner items; static screens не се rebuild-ват на всеки 60 ms controller tick.

Глобалният hotkey receiver пак трябва да съобщи на Tk controller-а; той не е kernel-level watchdog. Архитектурата премахва дългите per-window joins и синхронните cross-thread UI updates, но замръзнал Python процес не може сам да гарантира cleanup. `Ctrl+Alt+Q` не стартира immersive режима, ако hotkeys не са регистрирани.

## Resource status и pressure policy

Панелът показва:

- event-loop delay и последно screenshot render време;
- active effect windows и tabs;
- working set на Python процеса;
- peak memory на owned browser Job, когато Windows я предоставя;
- system available RAM.

„Недостъпно“ означава, че метриката не е върната — не се измисля стойност. След три поредни samples се активира soft pressure режим при ориентировъчно:

- Python working set над 256 MiB;
- owned browser Job peak над 768 MiB;
- свободна физическа RAM под 512 MiB;
- или UI delay над 450 ms.

При pressure се спират новите effect windows, включва се reduced motion, затваря се само owned browser session и animated desktop scene се заменя със static fallback. Това са начални operational thresholds, не обещани или сертифицирани hardware ceilings.

## Тестове

Default regression suite не отваря native прозорци:

```powershell
py -m unittest discover -s tests -v
```

Opt-in Win32 acceptance тестовете създават краткотрайни application-owned прозорци:

```powershell
$env:CYBER_CLASSROOM_NATIVE_TESTS='1'
py -m unittest tests.test_cyber_classroom.NativeEffectAcceptanceTests -v
```

Проверяват се resource caps, wall-clock rate limits, stale generation events, duplicate start, pause clock, chapter indexing, loopback validation/rate limit, six distinct pages, browser-state reset, strict file conflicts, bounded image size, native keyboard bridge, всички native scene builders и regression сценарият Tk mainloop + HTTP thread + ctypes Win32 callback под Python 3.13.

При разработката на 7.0 са изпълнени:

- 28 default-discovery tests: успешно, 4 opt-in Win32 tests пропуснати по дизайн;
- 4 opt-in Win32 tests: успешно, включително 10 native lifecycle цикъла без unbounded USER/GDI handle growth;
- 300 ms реален Tk panel startup/cleanup smoke test: успешно;
- `py -m py_compile`: успешно.

Bounded synthetic Pillow benchmark на наличната development машина (1920 × 1080 synthetic source, 24 mixed frames, без screen capture и без ImageTk upload): School Safe 960 × 540 — mean 86.43 ms, p95 138.22 ms, max 142.64 ms; Balanced 1280 × 720 — mean 155.99 ms, p95 246.40 ms, max 255.43 ms. Началният Python working set беше 49.0 MiB, а наличната system RAM — 15 402 MiB. Owned-browser peak не е измерен, защото реален browser session не беше стартиран от автоматичния тест. Runtime панелът показва действителния Job peak по време на ръчната проба. Benchmark-ът не е гаранция за school hardware.

Тези резултати са от наличния Windows компютър и не доказват поведение на всеки училищен модел. Ръчните проверки са в [WINDOWS_ACCEPTANCE_CHECKLIST.md](WINDOWS_ACCEPTANCE_CHECKLIST.md).

## Ограничения

- Приложението е за Windows 10/11 и не е антивирусен продукт.
- Видим симптом сам по себе си не доказва заразяване.
- Кадърът използва само основния монитор и се пази само докато сцената е активна.
- File Explorer прозорецът и учебната папка остават за обсъждане.
- Force-kill на Python или изключване на компютъра може да прекъсне normal filename restoration.
- Реалният браузър, DPI 200%, taskbar/work-area placement и handle growth трябва да се проверят на конкретната presentation машина.

## Changelog 7.0

- Намалени и централизирани school-safe ресурси.
- Шест отделни browser page designs и поправен локален action feedback.
- Нови wizard/scanner states, четири errors, toast, expandable warning, terminal и native ransomware reconstruction.
- Shared `ScenarioState`, generation guards, teacher-paced mode, Replay и resource indicator.
- Bounded/coalesced queues, owner-thread Win32 updates, aggregate cleanup и browser reset.
- Очакваните Edge/Chrome loopback disconnect-и при затваряне не отпечатват подвеждащи socket tracebacks; другите server грешки остават видими.
- Добавени са локално синтезирани тематични WAV сигнали, preview, pause/stop cleanup и exact-name custom overrides.
- Добавени са opt-out Windows Notification Center известия с учебна маркировка, throttling и автоматично изтичане.
- Историята е разширена до 8/12/15 минути с UAC, firewall, Task Manager и runtime updater етапи и автоматично преминаващ installer.
- Retained fullscreen layouts, bounded internal transforms с full-window presentation, reduced/static motion и pressure fallback.
- Разширени unit и opt-in Windows regression тестове.
