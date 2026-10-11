# Windows acceptance checklist — CaveDepths / Cyber Classroom 8.1

Този checklist е ръчен и opt-in. Изпълнете го на конкретния presentation компютър преди урок. Не използвайте личен браузърен профил или чувствителни отворени документи.

## Подготовка

- [ ] Windows 10/11, Python 3.10+ и Pillow са записани в протокола.
- [ ] Резолюция 1366 × 768: панелът се scroll-ва и всички controls са достижими.
- [ ] 100%, 150% и 200% display scaling: dismiss/Stop controls остават в work area и над taskbar.
- [ ] При един и два монитора списъкът е точен; browser, fullscreen сцени и toast се отварят върху избрания презентационен монитор, а панелът може да остане на другия.
- [ ] Windows 10/11 профилът и BG/EN системният език са разпознати и системните контроли използват съответния вариант.
- [ ] „Провери готовността“ отчита temp storage, hotkeys, browser policy, Pillow, монитори и Windows Notification Center честно.
- [ ] Sensitive windows са затворени преди screen snapshot сцената.
- [ ] Тест без интернет: шестте localhost страници и бутоните им работят; няма external requests от supplied content.
- [ ] При включено „Windows известия“ се появява локален toast в Notification Center; при изключена отметка не се изпраща. Stop/изход премахва само записите от собствената `classroom-demo` група. Проверете и при Focus Assist / Do Not Disturb.
- [ ] Windows 11 показва различими compact/warning/scan/recovery adaptive toasts; Windows 10 използва четим text fallback. Няма неработещи action бутони.

## Emergency controls

- [ ] `Ctrl+Alt+P` pause/resume работи при фокус в Edge/Chrome.
- [ ] `Ctrl+Alt+Q` освобождава desktop и затваря само owned browser session.
- [ ] `Esc`, `F6` и `F11` работят от installer button, terminal EDIT и scanner button focus.
- [ ] Нито една сцена не блокира Alt+Tab, Task Manager или нормалния close control.
- [ ] При заети global hotkeys immersive демонстрацията отказва да стартира.
- [ ] В началото има ясно потвърждение за учебната симулация; по време на историята аварийните клавиши остават активни.

## Native scenes

- [ ] UAC reconstruction: Unknown publisher, details и Yes/No; не се появява истински secure desktop или elevation prompt.
- [ ] Installer: Welcome → Options → Installing → Completed; Back, Next, Cancel, Finish; Cancel спира progress.
- [ ] Firewall warning: private/public choices и action result; няма ново firewall правило.
- [ ] Task Manager classroom view: synthetic CPU/Disk/Network/GPU values и End demo task; не се четат реални процеси.
- [ ] Runtime updater: staged progress, Cancel и Completed; не се инсталира компонент.
- [ ] Toast: не взема focus, има timestamp, Details и dismiss; stacking остава в profile cap.
- [ ] Tray helper: временната икона има работещи Open status и Exit helper; изчезва при Stop, recovery и изход.
- [ ] Tray info/warning/error balloons имат различни икони и tooltip/status; нито един tray callback не променя UI от чужд thread.
- [ ] Taskbar progress/paused/error/attention се виждат само върху собствените прозорци и се изчистват при Pause, Stop и затваряне.
- [ ] Warning: Show/Hide details реално resize-ва и показва/скрива съдържанието.
- [ ] Error wall: виждат се поне четирите варианта без infinite replacement.
- [ ] Terminal: resizable, bounded output, pauses with scenario clock, никакъв shell process.
- [ ] Scanner: Pause/Resume, Stop, Details/Summary и Completed имат видим резултат.
- [ ] Protection History, File Properties и offline Network Activity са различими и използват същите процеси/детекции.
- [ ] Ransomware прозорец: movable/closable, nonpayable ID, locked count 0–8 и Check recovery status.
- [ ] Recovery връща максимум едно собствено име на стъпка; при конфликт спира без overwrite и отваря папката за проверка.

## Истории и разклонения

- [ ] 10-, 15- и 20-минутните preset-и имат различен брой и набор от сцени и приключват точно на заявената продължителност.
- [ ] Стандартният 15-минутен сценарий следва: сайт → download → UAC → installer → helper → symptoms → detection → осем файла → ransom → recovery → debrief.
- [ ] В автоматичен режим историята следва компрометирания път след естественото изчакване.
- [ ] В учителски режим UAC No, Cancel, firewall block и End task показват резултат и чакат „Приеми резултата“ или „Покажи компрометирания път“.
- [ ] „Приеми резултата“ при безопасно действие преминава към debrief; „Покажи компрометирания път“ продължава причинната история.
- [ ] Replay на глава преди/по време/след файловото въздействие синхронизира прозорците, броя `.locked` имена, tray и scanner state.

## Код и сигнален микс

- [ ] Нов автоматичен Start след Stop създава нов шестзнаков код; „Нов микс“ също го сменя.
- [ ] „Приложи“ приема валиден код без I/O/0/1; невалиден код дава ясно съобщение и не стартира.
- [ ] Един код + един preset възпроизвежда същите текстове, layout-и, икони, звуци и ред; „Повтори глава“ не сменя кода.
- [ ] 10/15/20 минути дават точно 9/13/16 вторични сигнала. Статусът показва доставени/общо.
- [ ] Всеки preset използва browser, in-app, taskbar, tray и Notification Center; няма два съседни сигнала от един канал.
- [ ] Няма съседно повторение на severity, икона или звук и няма повторена layout/text/icon/sound комбинация.
- [ ] Между два сигнала има поне 8 секунди, между Notification Center записи поне 20 секунди и няма повече от два видими едновременно.
- [ ] При забранен toast/tray/taskbar/browser се използва различим in-app fallback, без загуба на следващите събития.

## Browser и failure paths

- [ ] Един owned browser window и максимум 4 tabs в School Safe.
- [ ] Balanced позволява максимум 6 tabs; абсолютният лимит 8 не се надвишава.
- [ ] Между launches има поне 3 wall-clock секунди; няма burst след pause.
- [ ] Нормален личен browser window остава отворен след Stop/Quit.
- [ ] Ръчно затворен owned browser дава useful fallback и не се отваря безконтролно отново.
- [ ] Managed `UserDataDir` policy отказва сцената; няма fallback към default profile.
- [ ] Missing browser и failed launch показват Bulgarian explanation и историята остава контролируема.
- [ ] Controlled browser signals са различими като download shelf, permission chip, account banner и update strip и се махат автоматично.
- [ ] Ръчният „Истинско browser известие“ работи само през localhost, иска Allow едва след учителски клик и обработва отказа видимо.
- [ ] Stop извиква best-effort `.close()` на browser notification обектите преди private Job/profile cleanup; отчетено е, че browser-owned history entry може да остане.

## Files и visual scenes

- [ ] Учебната папка съдържа точно 8 generated `.txt` files преди добавяне на собствен test file.
- [ ] `.locked` е rename, не encryption; Stop връща непроменените имена.
- [ ] Edited file, conflicting plain filename и replacement link не се overwrite-ват/follow-ват.
- [ ] Screen distortion прави един RAM-only capture само на избрания монитор, пази desktop recognizable и завършва с recovery.
- [ ] Reduced motion и Static frame намаляват updates; School Safe internal transform target е до 960 × 540, а presentation покрива целия прозорец.
- [ ] Capture failure преминава към static fallback и връща контролния панел при Stop.
- [ ] Blue/reboot/distortion са само отделни ръчни казуси, не се появяват в ransomware историите и не предизвикват real crash/reboot.

## Повтаряемост и ресурси

- [ ] 10 цикъла Start → Pause → Replay → Next → Stop без останали owned windows/threads.
- [ ] При Pause не се създават нови сигнали, звукът и taskbar attention спират, а Resume не наваксва с burst.
- [ ] 10 цикъла на всяка native сцена; USER/GDI handles се връщат близо до baseline.
- [ ] Python working set и owned browser Job peak са записани; няма монотонен необясним растеж.
- [ ] Event-loop delay остава приемлив на целевия компютър; emergency controls реагират.
- [ ] При симулирана low-memory/threshold конфигурация новото spawning спира и browser cleanup е ownership-scoped.
- [ ] Force-close failure е документиран: папката се проверява ръчно, без опит за overwrite.

## Протокол

- Машина / модел: ____________________
- Windows build: ____________________
- Python / Pillow: ____________________
- Browser / policy: ____________________
- Резолюция / scaling: ____________________
- School Safe peak Python MiB: ____________________
- School Safe browser Job peak MiB: ____________________
- Balanced peak Python MiB: ____________________
- Balanced browser Job peak MiB: ____________________
- Максимален observed render ms / UI delay ms: ____________________
- Забележки и непреминали точки: ________________________________________________
