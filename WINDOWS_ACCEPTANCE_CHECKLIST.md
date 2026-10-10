# Windows acceptance checklist — Cyber Classroom 7.0

Този checklist е ръчен и opt-in. Изпълнете го на конкретния presentation компютър преди урок. Не използвайте личен браузърен профил или чувствителни отворени документи.

## Подготовка

- [ ] Windows 10/11, Python 3.10+ и Pillow са записани в протокола.
- [ ] Резолюция 1366 × 768: панелът се scroll-ва и всички controls са достижими.
- [ ] 100%, 150% и 200% display scaling: dismiss/Stop controls остават в work area и над taskbar.
- [ ] „Провери готовността“ отчита temp storage, hotkeys, browser policy, Pillow и Windows Notification Center честно.
- [ ] Sensitive windows са затворени преди screen snapshot сцената.
- [ ] Тест без интернет: шестте localhost страници и бутоните им работят; няма external requests от supplied content.
- [ ] При включено „Windows известия“ се появява ясно означен учебен toast в Notification Center; при изключена отметка не се изпраща. Проверете и при Focus Assist / Do Not Disturb.

## Emergency controls

- [ ] `Ctrl+Alt+P` pause/resume работи при фокус в Edge/Chrome.
- [ ] `Ctrl+Alt+Q` освобождава desktop и затваря само owned browser session.
- [ ] `Esc`, `F6` и `F11` работят от installer button, terminal EDIT и scanner button focus.
- [ ] Нито една сцена не блокира Alt+Tab, Task Manager или нормалния close control.
- [ ] При заети global hotkeys immersive демонстрацията отказва да стартира.

## Native scenes

- [ ] UAC reconstruction: Unknown publisher, details и Yes/No; не се появява истински secure desktop или elevation prompt.
- [ ] Installer: Welcome → Options → Installing → Completed; Back, Next, Cancel, Finish; Cancel спира progress.
- [ ] Firewall warning: private/public choices и action result; няма ново firewall правило.
- [ ] Task Manager classroom view: synthetic CPU/Disk/Network/GPU values и End demo task; не се четат реални процеси.
- [ ] Runtime updater: staged progress, Cancel и Completed; не се инсталира компонент.
- [ ] Toast: не взема focus, има timestamp, Details и dismiss; stacking остава в profile cap.
- [ ] Warning: Show/Hide details реално resize-ва и показва/скрива съдържанието.
- [ ] Error wall: виждат се поне четирите варианта без infinite replacement.
- [ ] Terminal: resizable, bounded output, pauses with scenario clock, никакъв shell process.
- [ ] Scanner: Pause/Resume, Stop, Details/Summary и Completed имат видим резултат.
- [ ] Ransomware reconstruction: movable/closable, nonpayable ID, locked count 0–8, Check key и Restore names.

## Browser и failure paths

- [ ] Един owned browser window и максимум 4 tabs в School Safe.
- [ ] Balanced позволява максимум 6 tabs; абсолютният лимит 8 не се надвишава.
- [ ] Между launches има поне 3 wall-clock секунди; няма burst след pause.
- [ ] Нормален личен browser window остава отворен след Stop/Quit.
- [ ] Ръчно затворен owned browser дава useful fallback и не се отваря безконтролно отново.
- [ ] Managed `UserDataDir` policy отказва сцената; няма fallback към default profile.
- [ ] Missing browser и failed launch показват Bulgarian explanation и историята остава контролируема.

## Files и visual scenes

- [ ] Учебната папка съдържа точно 8 generated `.txt` files преди добавяне на собствен test file.
- [ ] `.locked` е rename, не encryption; Stop връща непроменените имена.
- [ ] Edited file, conflicting plain filename и replacement link не се overwrite-ват/follow-ват.
- [ ] Screen distortion прави един RAM-only capture, пази desktop recognizable и завършва с recovery.
- [ ] Reduced motion и Static frame намаляват updates; School Safe internal transform target е до 960 × 540, а presentation покрива целия прозорец.
- [ ] Capture failure преминава към static fallback и връща контролния панел при Stop.
- [ ] Blue/reboot показват simulation cue и не предизвикват real crash/reboot.

## Повтаряемост и ресурси

- [ ] 10 цикъла Start → Pause → Replay → Next → Stop без останали owned windows/threads.
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
