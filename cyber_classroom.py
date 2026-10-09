"""Дигитални детективи 5.0 — демонстрация върху истинския Windows.

Windows 10/11 + Python 3.10+ с tkinter. Стартиране: py cyber_classroom.py
Преди първо стартиране: py -m pip install pillow
Не са нужни администраторски права.
Ctrl+Alt+P: глобална пауза / продължаване.
Ctrl+Alt+Q: спира ефектите, затваря учебния браузър и излиза.
Esc: спиране от наш активен прозорец. F6: следваща глава. F11: цял екран.
Продължителност: 5, 8 или 12 минути, без времето в пауза.

Използва реален Edge/Chrome с нов временен профил и до 20 локални раздела.
Вграден HTTP сървър слуша САМО на 127.0.0.1, със случаен адресен префикс.
Страниците не водят към външни сайтове и не приемат пароли или плащания.
Браузърът е в отделен Windows Job; никога не се затварят процеси по име.
Организационна UserDataDir политика не се заобикаля; браузърната сцена се отказва.

Създава точно 8 учебни текстови файла в нова временна папка и отваря тази папка
в истинския File Explorer. Само създадените файлове получават суфикс .locked.
При спиране връща имената им, ако съдържанието е непроменено и няма конфликт.
Няма шифроване. Папката и прозорецът на File Explorer остават за преглед.
Графичната сцена взема еднократна снимка на основния монитор САМО в RAM.
Разкъсва, разтича и повтаря тези пиксели в собствен прозорец върху Windows.
Снимката не се записва или изпраща; оригиналният работен плот е непокътнат.
Няма четене на лични файлове, запис на клавиши, достъп до камера/микрофон,
изключване на защита, промяна на настройки, автозареждане или реален срив.
Pegasus сцената е условна учебна илюстрация на мобилно наблюдение.

Документация: Chromium user_data_dir.md; Microsoft RegisterHotKey,
CreateProcessW, AssignProcessToJobObject и JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
https://pillow.readthedocs.io/en/stable/reference/ImageGrab.html
https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setprocessdpiawarenesscontext
"""

import ctypes
from ctypes import wintypes
import math
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import queue
import random
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from PIL import Image, ImageChops, ImageGrab, ImageTk
    PILLOW_ERROR = None
except ImportError as exc:
    Image = ImageChops = ImageGrab = ImageTk = None
    PILLOW_ERROR = str(exc)

LOG = logging.getLogger('CyberClassroom')
LOG.addHandler(logging.NullHandler())
LOG_PATH = None


def configure_logging():
    """Only application events and exceptions; never screen images or file contents."""
    global LOG_PATH
    directory = Path(tempfile.mkdtemp(prefix='CyberClassroom-LOG-'))
    LOG_PATH = directory / 'cyber_classroom.log'
    handler = RotatingFileHandler(LOG_PATH, maxBytes=512_000, backupCount=1, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    LOG.addHandler(handler)
    LOG.setLevel(logging.INFO)
    LOG.info('Version 5.0; Python %s; platform %s; Pillow available=%s',
             sys.version.split()[0], sys.platform, Image is not None)


def enable_dpi_awareness():
    """Align Tk coordinates with physical screen pixels; call before creating Tk."""
    if sys.platform != 'win32':
        return
    try:
        user = ctypes.WinDLL('user32', use_last_error=True)
        if hasattr(user, 'SetProcessDpiAwarenessContext'):
            fn = user.SetProcessDpiAwarenessContext
            fn.argtypes = [ctypes.c_void_p]
            fn.restype = ctypes.c_int
            if fn(ctypes.c_void_p(-4)):
                return
            if ctypes.get_last_error() == 5:  # Already set by the host's manifest.
                return
        user.SetProcessDPIAware.argtypes = []
        user.SetProcessDPIAware.restype = ctypes.c_int
        user.SetProcessDPIAware()
    except (OSError, AttributeError):
        LOG.exception('DPI initialization failed; using the host default')


class GlobalHotkeys:
    """Dedicated Win32 message thread; only recognized hotkeys enter the queue."""
    WM_HOTKEY = 0x0312
    WM_QUIT = 0x0012

    def __init__(self, events):
        self.events = events
        self.stopping = threading.Event()
        self.thread_id = None
        self.user32 = None
        self.thread = threading.Thread(target=self.run, name='ClassroomHotkeys', daemon=True)
        self.thread.start()

    def run(self):
        registered = []
        try:
            u = ctypes.WinDLL('user32', use_last_error=True)
            k = ctypes.WinDLL('kernel32', use_last_error=True)
            u.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            u.RegisterHotKey.restype = wintypes.BOOL
            u.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            u.UnregisterHotKey.restype = wintypes.BOOL
            u.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                     wintypes.UINT, wintypes.UINT]
            u.GetMessageW.restype = ctypes.c_int  # -1 must not be treated as a normal message.
            u.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                      wintypes.UINT, wintypes.UINT, wintypes.UINT]
            u.PeekMessageW.restype = wintypes.BOOL
            u.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT,
                                           wintypes.WPARAM, wintypes.LPARAM]
            u.PostThreadMessageW.restype = wintypes.BOOL
            k.GetCurrentThreadId.restype = wintypes.DWORD
            self.user32 = u
            self.thread_id = k.GetCurrentThreadId()
            msg = wintypes.MSG()
            u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # Create message queue.
            if self.stopping.is_set():
                return
            modifiers = 0x0001 | 0x0002 | 0x4000  # ALT | CONTROL | NOREPEAT
            for identity, key in [(1, 'P'), (2, 'Q')]:
                if not u.RegisterHotKey(None, identity, modifiers, ord(key)):
                    error = ctypes.get_last_error()
                    self.events.put(('hotkeys_error',
                        f'Ctrl+Alt+{key} не може да се регистрира (Windows код {error}). '
                        'Затворете друга отворена версия или освободете комбинацията и натиснете „Провери отново“.'))
                    return
                registered.append(identity)
            self.events.put(('hotkeys_ready', None))
            while not self.stopping.is_set():
                result = u.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == -1:
                    self.events.put(('hotkeys_error', 'Прекъсната връзка с клавишните комбинации. Ефектите са спрени.'))
                    break
                if result == 0:
                    if not self.stopping.is_set():
                        self.events.put(('hotkeys_error', 'Клавишното управление е прекратено. Ефектите са спрени.'))
                    break
                if msg.message == self.WM_HOTKEY:
                    action = {1: 'pause', 2: 'quit'}.get(msg.wParam)
                    if action:
                        self.events.put((action, None))
        except Exception as exc:
            self.events.put(('hotkeys_error', f'Глобалните комбинации не са готови: {exc}'))
        finally:
            if self.user32 is not None:
                for identity in registered:
                    self.user32.UnregisterHotKey(None, identity)

    def close(self):
        self.stopping.set()
        if self.thread_id is not None and self.user32 is not None:
            self.user32.PostThreadMessageW(self.thread_id, self.WM_QUIT, 0, 0)
        self.thread.join(timeout=1.0)


FILES = [
    ('Доклад_история.docx', 'Документ на Word', '48 KB'),
    ('Класна_снимка.jpg', 'JPEG изображение', '3 214 KB'),
    ('Презентация.pptx', 'Презентация', '2 781 KB'),
    ('Проект.py', 'Python файл', '12 KB'),
    ('График.xlsx', 'Работна книга', '26 KB'),
    ('Плакат.png', 'PNG изображение', '1 908 KB'),
    ('Бележки.txt', 'Текстов документ', '4 KB'),
    ('Архив_клуб.zip', 'ZIP архив', '8 432 KB'),
]
TERMINAL_LINES = [
    'Microsoft Windows [Version 10.0.22631.0000]',
    '(c) Microsoft Corporation. All rights reserved.',
    '', r'C:\Users\Student\Downloads> SuperMod_Setup.exe /install',
    '[bootstrap] loading package ... OK',
    '[update_helper] worker process ready',
    '[notice] unexpected child process detected',
    '[network] connection attempt blocked',
    '[worker] indexing document names ...',
    '[worker] queue: 8 documents',
    '[worker] processing item 01/08 ...',
    '[worker] processing item 02/08 ...',
    '[worker] processing item 03/08 ...',
    '[worker] processing item 04/08 ...',
    '[worker] processing item 05/08 ...',
    '[worker] processing item 06/08 ...',
    '[worker] processing item 07/08 ...',
    '[worker] processing item 08/08 ...',
    '[worker] all queued items marked LOCKED',
    '[notice] recovery instructions pending',
]

# Eight-minute master timeline, scaled to the selected total duration.
TIMELINE = [
    (0, 'browser'), (20, 'installer'), (35, 'tabs'),
    (48, 'notification'), (62, 'advert'), (77, 'warning'), (87, 'scanner'),
    (100, 'errorwall'), (125, 'scanner'),
    (145, 'terminal_chapter'), (160, 'warning'),
    (180, 'glitch'), (215, 'files_chapter'), (240, 'error'),
    (255, 'ransom'), (310, 'blue'), (335, 'reboot'),
    (350, 'spyware'), (445, 'debrief'), (480, 'finish'),
]
CHAPTERS = [(0, 'Безплатната програма'), (35, 'Браузърът полудява'),
            (100, 'Лавина от грешки'), (145, 'Непознат процес'),
            (180, 'Повреден екран'), (215, 'Изчезващите документи'),
            (255, 'WannaCry: откуп'), (310, 'Срив и рестартиране'),
            (350, 'Pegasus: невидимо наблюдение'), (445, 'Какво научихме')]
SOURCE_NOTES = {
    'Pegasus': 'https://citizenlab.ca/research/million-dollar-dissident-iphone-zero-day-nso-group-uae/',
    'WannaCry': 'https://www.microsoft.com/en-us/security/blog/2017/05/12/wannacrypt-ransomware-worm-targets-out-of-date-systems/',
}


QUESTIONS = [
    ('01 / Следата в браузъра',
     'Сайт: minecraft-bonus.example\n„Безплатен мод! Изключи защитата, за да го инсталираш.“\nИзтеглен файл: SuperMod_Setup.exe',
     ['Изпълнявам файла — пише, че е безплатен.',
      'Спирам: искането да изключа защитата е тревожен знак.',
      'Вярвам му, защото страницата има красиво лого.'], 1,
     'Искането за изключване на защитата е сериозен предупредителен знак.\nКрасивият дизайн и думата „безплатно“ не доказват надеждност.'),
    ('02 / Следата в пощата',
     'От: support@school-check.example\n„Профилът ти ще бъде изтрит след 10 минути!\nПотвърди паролата си през този линк.“',
     ['Проверявам съобщението през познат канал с училището.',
      'Изпращам паролата си в отговор.',
      'Отварям линка, защото времето изтича.'], 0,
     'Спешността и заплахата за загуба на профила подтикват към прибързано действие.\nОтвори познатия официален адрес самостоятелно; не давай паролата си по имейл.'),
    ('03 / Компютърът показва признаци на заразяване',
     'Появяват се непознати прозорци и файловете уж се заключват.\nНамираш се в училищна компютърна зала. Как реагираш?',
     ['Инсталирам „чистачката“, предложена в рекламата.',
      'Продължавам да работя и се надявам да отмине.',
      'Прекъсвам Wi-Fi/кабела и уведомявам учителя или администратора.'], 2,
     'Изолирането от мрежата може да ограничи разпространението, но не премахва заразата.\nУведоми отговорния човек и следвай процедурата на училището.'),
    ('04 / Обещанието за спасение',
     'На екрана се иска откуп срещу обещание за връщане на файловете.\nКое твърдение е вярно?',
     ['Плащането гарантира възстановяване.',
      'Няма гаранция; търсим компетентна помощ и проверени резервни копия.',
      'Преименуването на файловете винаги ги възстановява.'], 1,
     'Обещанието на нападателя не е гаранция. Възстановяването зависи от случая.\nРезервните копия трябва да са проверени и защитени от същия инцидент.'),
    ('05 / Какво доказаха ефектите?',
     'Видяхме реклами, терминал и син екран.\nДоказва ли всеки такъв екран наличието на вирус?',
     ['Да — всеки син екран означава вирус.',
      'Да — всеки терминал означава хакер.',
      'Не — нужни са проверка и контекст, а тук всичко беше симулация.'], 2,
     'Син екран може да е причинен и от драйвер или хардуер. Терминалът е нормален инструмент.\nСимптомът е повод за проверка, а не самостоятелно доказателство за зараза.'),
    ('06 / Невидимото наблюдение',
     'При сцената за Pegasus телефонът изглеждаше нормално.\nКаква е основната разлика спрямо искането за откуп?',
     ['Шпионският софтуер се стреми да събира данни незабелязано.',
      'Pegasus винаги се показва като прозорец с обратно броене.',
      'Ако няма реклами, устройството със сигурност е защитено.'], 0,
     'Pegasus е мобилен шпионски софтуер. Скритото наблюдение се различава от видимото искане за откуп.\nПоказаният екран беше условен учебен модел, а не действителен интерфейс на Pegasus.'),
    ('07 / Какво беше истинско?',
     'Видяхме браузърни раздели и файлове с променени имена.\nКакво действително направи тази програма?',
     ['Прочете личните ми файлове и записа камерата.',
      'Шифрова документите ми, но после ги възстанови.',
      'Отвори локални страници в истински браузър и преименува само създадените учебни файлове.'], 2,
     'Браузърът и учебната папка са истински. Съдържанието е специално създадено за този урок.\nЛичните файлове, камерата и микрофонът не се използват. Няма шифроване.'),
]


class Effect:
    def __init__(self, app, title, width, height, bg='#f3f3f3', position='random'):
        self.app = app
        self.born = app.clock
        self.closed = False
        self.update_view = lambda elapsed: None
        self.limit = None
        self.win = tk.Toplevel(app.root)
        self.win.withdraw()
        self.win.title(title)
        self.win.configure(bg=bg)
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        # Keep the full window within the primary screen, including decorations.
        width, height = min(width, sw-50), min(height, sh-100)
        if position == 'center':
            x, y = (sw-width)//2, max(15, (sh-height)//2-35)
        elif position == 'toast':
            x, y = sw-width-22, max(20, sh-height-85)
        else:
            x = app.rng.randint(20, max(20, sw-width-30))
            y = app.rng.randint(25, max(25, sh-height-90))
        self.win.geometry(f'{width}x{height}+{x}+{y}')
        self.win.resizable(False, False)
        self.win.protocol('WM_DELETE_WINDOW', self.close)
        self.win.attributes('-topmost', True)
        self.win.deiconify()

    def tick(self):
        if self.closed:
            return
        elapsed = self.app.clock-self.born
        if self.limit is not None and elapsed >= self.limit:
            self.close()
        else:
            self.update_view(elapsed)

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.win.destroy()
        except tk.TclError:
            pass


def label(parent, text, size=11, color='#222222', bg=None, bold=False, **kwargs):
    options = dict(text=text, fg=color, bg=bg or parent.cget('bg'),
                   font=('Segoe UI', size, 'bold' if bold else 'normal'),
                   anchor='w', justify='left')
    options.update(kwargs)
    return tk.Label(parent, **options)


class JobBasicLimits(ctypes.Structure):
    _fields_ = [('ProcessTime',ctypes.c_int64),('JobTime',ctypes.c_int64),
                ('LimitFlags',ctypes.c_uint32),('MinWorkingSet',ctypes.c_size_t),
                ('MaxWorkingSet',ctypes.c_size_t),('ActiveProcesses',ctypes.c_uint32),
                ('Affinity',ctypes.c_size_t),('Priority',ctypes.c_uint32),('Scheduling',ctypes.c_uint32)]


class JobExtendedLimits(ctypes.Structure):
    _fields_ = [('Basic',JobBasicLimits),('Io',ctypes.c_uint64*6),
                ('ProcessMemory',ctypes.c_size_t),('JobMemory',ctypes.c_size_t),
                ('PeakProcessMemory',ctypes.c_size_t),('PeakJobMemory',ctypes.c_size_t)]


class StartupInfo(ctypes.Structure):
    _fields_ = [('cb',ctypes.c_uint32),('reserved',ctypes.c_wchar_p),
                ('desktop',ctypes.c_wchar_p),('title',ctypes.c_wchar_p),
                ('x',ctypes.c_uint32),('y',ctypes.c_uint32),('cx',ctypes.c_uint32),
                ('cy',ctypes.c_uint32),('cxchars',ctypes.c_uint32),('cychars',ctypes.c_uint32),
                ('fill',ctypes.c_uint32),('flags',ctypes.c_uint32),('show',ctypes.c_uint16),
                ('reserved2size',ctypes.c_uint16),('reserved2',ctypes.c_void_p),
                ('stdin',ctypes.c_void_p),('stdout',ctypes.c_void_p),('stderr',ctypes.c_void_p)]


class ProcessInfo(ctypes.Structure):
    _fields_ = [('process',ctypes.c_void_p),('thread',ctypes.c_void_p),
                ('pid',ctypes.c_uint32),('tid',ctypes.c_uint32)]


class OwnedBrowserJob:
    """Only processes created here are assigned. No process-name-based killing.

    A process is created suspended, assigned to our private job, then resumed.
    If assignment fails, only that newly created, still-suspended process is stopped.
    Browser sandboxing is kept enabled; administrator rights are not requested.
    """
    def __init__(self):
        self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        self.u=ctypes.WinDLL('user32',use_last_error=True)
        signatures={
            'CreateJobObjectW':([ctypes.c_void_p,ctypes.c_wchar_p],ctypes.c_void_p),
            'SetInformationJobObject':([ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32],ctypes.c_int),
            'CreateProcessW':([ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_void_p,ctypes.c_void_p,
                               ctypes.c_int,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_wchar_p,
                               ctypes.POINTER(StartupInfo),ctypes.POINTER(ProcessInfo)],ctypes.c_int),
            'AssignProcessToJobObject':([ctypes.c_void_p,ctypes.c_void_p],ctypes.c_int),
            'ResumeThread':([ctypes.c_void_p],ctypes.c_uint32),
            'TerminateProcess':([ctypes.c_void_p,ctypes.c_uint32],ctypes.c_int),
            'CloseHandle':([ctypes.c_void_p],ctypes.c_int),
            'OpenProcess':([ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32],ctypes.c_void_p),
            'IsProcessInJob':([ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(ctypes.c_int)],ctypes.c_int),
        }
        for name,(args,result) in signatures.items():
            fn=getattr(self.k,name); fn.argtypes=args; fn.restype=result
        self.callback_type=ctypes.WINFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_ssize_t)
        self.u.EnumWindows.argtypes=[self.callback_type,ctypes.c_ssize_t]
        self.u.EnumWindows.restype=ctypes.c_int
        self.u.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32)]
        self.u.GetWindowThreadProcessId.restype=ctypes.c_uint32
        self.u.IsWindowVisible.argtypes=[ctypes.c_void_p]; self.u.IsWindowVisible.restype=ctypes.c_int
        self.u.ShowWindow.argtypes=[ctypes.c_void_p,ctypes.c_int]; self.u.ShowWindow.restype=ctypes.c_int
        self.handle=self.k.CreateJobObjectW(None,None)
        self.hidden=[]
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits=JobExtendedLimits(); limits.Basic.LimitFlags=0x2000  # KILL_ON_JOB_CLOSE
        if not self.k.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            error=ctypes.get_last_error(); self.close(); raise ctypes.WinError(error)

    def launch(self, executable, arguments):
        if not self.handle:
            raise RuntimeError('Браузърната сесия е затворена.')
        info=StartupInfo(); info.cb=ctypes.sizeof(info)
        proc=ProcessInfo()
        cmd=ctypes.create_unicode_buffer(subprocess.list2cmdline([str(executable),*arguments]))
        if not self.k.CreateProcessW(str(executable),cmd,None,None,False,0x00000004,
                                     None,None,ctypes.byref(info),ctypes.byref(proc)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.k.AssignProcessToJobObject(self.handle,proc.process):
                raise ctypes.WinError(ctypes.get_last_error())
            if self.k.ResumeThread(proc.thread)==0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
        except Exception:
            self.k.TerminateProcess(proc.process,1)
            raise
        finally:
            self.k.CloseHandle(proc.thread); self.k.CloseHandle(proc.process)

    def owns_window(self, hwnd):
        if not self.handle:
            return False
        pid=ctypes.c_uint32()
        self.u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        process=self.k.OpenProcess(0x1000,False,pid.value)  # query limited information
        if not process:
            return False
        try:
            belongs=ctypes.c_int()
            return bool(self.k.IsProcessInJob(process,self.handle,ctypes.byref(belongs)) and belongs.value)
        finally:
            self.k.CloseHandle(process)

    def hide(self):
        def visit(hwnd,_):
            if hwnd not in self.hidden and self.u.IsWindowVisible(hwnd) and self.owns_window(hwnd):
                self.hidden.append(hwnd); self.u.ShowWindow(hwnd,0)
            return 1
        callback=self.callback_type(visit)
        self.u.EnumWindows(callback,0)

    def restore(self):
        for hwnd in self.hidden:
            if self.owns_window(hwnd):
                self.u.ShowWindow(hwnd,4)  # show without grabbing focus
        self.hidden.clear()

    def has_window(self):
        found=[False]
        def visit(hwnd,_):
            if (self.u.IsWindowVisible(hwnd) or hwnd in self.hidden) and self.owns_window(hwnd):
                found[0]=True
                return 0
            return 1
        callback=self.callback_type(visit)
        self.u.EnumWindows(callback,0)
        return found[0]

    def close(self):
        if getattr(self,'handle',None):
            self.k.CloseHandle(self.handle)
            self.handle=None
        self.hidden=[]


def find_browser():
    candidates=[]
    for base in ('PROGRAMFILES(X86)','PROGRAMFILES','LOCALAPPDATA'):
        if os.environ.get(base):
            for suffix in ('Microsoft/Edge/Application/msedge.exe','Google/Chrome/Application/chrome.exe'):
                candidates.append(Path(os.environ[base])/suffix)
    if sys.platform=='win32':
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
            for name in ('msedge.exe','chrome.exe'):
                try:
                    with winreg.OpenKey(hive,r'Software\Microsoft\Windows\CurrentVersion\App Paths'+chr(92)+name) as key:
                        candidates.append(Path(winreg.QueryValue(key,None)))
                except OSError:
                    pass
    return next((p for p in candidates if p.is_file()),None)


def check_browser_policy(executable):
    """Do not override an organization's policy or risk reusing a managed profile."""
    import winreg
    vendor=r'Microsoft\Edge' if executable.name.lower()=='msedge.exe' else r'Google\Chrome'
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(hive,'Software\\Policies\\'+vendor,0,winreg.KEY_READ|view) as key:
                    try:
                        value,_=winreg.QueryValueEx(key,'UserDataDir')
                    except FileNotFoundError:
                        continue
                    if value:
                        raise RuntimeError('Браузърът има организационна политика UserDataDir. '
                                           'Изберете друг браузър; тази политика няма да се заобикаля.')
            except FileNotFoundError:
                pass


PAGE_HTML = '''<!doctype html><html lang="bg"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>PAGE_TITLE</title><style>
*{box-sizing:border-box}body{margin:0;background:#eef2f7;color:#20324a;font:19px "Segoe UI",sans-serif}
header{height:72px;background:#172a46;color:white;display:flex;align-items:center;padding:0 7vw;gap:18px}
.dot{height:12px;width:12px;border-radius:50%;background:#90dbbe}.right{margin-left:auto;color:#b8cbe0;font-size:14px}
main{margin:7vh auto 30px;width:min(1000px,88vw);background:white;padding:42px 50px;border-top:8px solid ACCENT;box-shadow:0 16px 60px #29334f18}
h1{font-size:clamp(28px,4vw,48px);line-height:1.15;color:ACCENT;margin:12px 0 25px}p{line-height:1.55}
.tag{font-size:14px;letter-spacing:2px;color:#718299}.timer{font-size:44px;font-weight:700;color:ACCENT;font-variant-numeric:tabular-nums;margin:23px 0}
button{padding:18px 30px;background:ACCENT;color:white;border:0;font:700 19px "Segoe UI",sans-serif;cursor:pointer}
button:disabled{cursor:default;opacity:.72}
.track{height:8px;background:#e6ecf3;margin:30px 0 18px}.bar{height:100%;width:0;background:ACCENT}
footer{margin-top:26px;color:#7e8da0;font-size:14px}#notice{min-height:28px;color:#a0253b;font-size:17px}
body.paused .dot{background:#edc469}.hint{font-size:15px;color:#647991}
</style><header><span class="dot"></span><b>SITE_NAME</b><span class="right">СИСТЕМНО ИЗВЕСТИЕ</span></header>
<main><span class="tag">PAGE_TAG</span><h1>PAGE_TITLE</h1><p>PAGE_BODY</p><div class="timer" id="timer">01:59</div>
<button id="action">PAGE_ACTION</button><div class="track"><div class="bar" id="bar"></div></div>
<p class="hint" id="state">Проверка на състоянието…</p><div id="notice"></div>
<footer>Локална страница за демонстрация. Няма плащане, вход в профил или изтегляне на софтуер.</footer></main>
<script nonce="NONCE">
const actionButton=document.getElementById('action'),notice=document.getElementById('notice');
actionButton.addEventListener('click',async()=>{actionButton.disabled=true;notice.textContent='Стартиране на учебната сцена…';
try{const r=await fetch(ACTION_URL,{method:'POST',cache:'no-store',credentials:'omit'});if(!r.ok)throw new Error();
notice.textContent='Учебното действие е стартирано. Няма реално изтегляне или инсталация.';
}catch(e){notice.textContent='Локалната учебна връзка е прекъсната.';actionButton.disabled=false;}});
async function poll(){try{const r=await fetch(STATE_URL,{cache:'no-store'});if(!r.ok)throw new Error();const s=await r.json();
document.body.classList.toggle('paused',s.paused);let n=Math.max(0,119-Math.floor(s.time)%120);
document.getElementById('timer').textContent=String(Math.floor(n/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0');
document.getElementById('bar').style.width=String(Math.floor(s.time*1.7)%101)+'%';
document.getElementById('state').textContent=s.paused?'Пауза на демонстрацията':('Отворени учебни раздели: '+s.tabs+' • Локалната връзка е активна');
}catch(e){document.getElementById('state').textContent='Демонстрацията е приключила.';}setTimeout(poll,500);}poll();
</script></html>'''
WEB_PAGES = [
    ('SUPERMOD','БЕЗПЛАТЕН МОД','Нов свят за твоята игра.',
     'Нови карти, редки предмети и обещание за повече кадри. „Ако защитата спре инсталацията, изключете я временно.“',
     'ИЗТЕГЛИ БЕЗПЛАТНО','#356fbe'),
    ('BONUS REWARDS','СПЕЦИАЛНА ОФЕРТА','Спечелихте награда!',
     'Избрани сте за специален подарък. Побързайте, защото тази оферта скоро изчезва.',
     'ВЗЕМИ НАГРАДАТА','#7844a6'),
    ('PC DEFENDER','КРИТИЧНО ПРЕДУПРЕЖДЕНИЕ','Открити са 37 заплахи!',
     'Вашите документи може да са в опасност. Предлага се незабавна „проверка“ на компютъра.',
     'ПРОВЕРИ СЕГА','#b1344b'),
    ('ACCOUNT CHECK','ИЗИСКВА СЕ ДЕЙСТВИЕ','Профилът ще бъде спрян.',
     'Съобщението настоява да потвърдите данните си. Не е посочено защо това трябва да става през непознат сайт.',
     'ПОТВЪРДИ ПРОФИЛА','#a36b2d'),
    ('BROWSER UPDATE','ВАЖНА АКТУАЛИЗАЦИЯ','Необходим е нов компонент.',
     'Страницата твърди, че трябва да инсталирате допълнение, за да продължите.',
     'ИНСТАЛИРАЙ UPDATE','#2c638e'),
    ('SPEED BOOST','СИСТЕМНА ДИАГНОСТИКА','Компютърът е твърде бавен!',
     'Едно натискане обещава да реши „всички проблеми“. Резултатите на тази страница са измислени.',
     'ПОПРАВИ ВСИЧКО','#26786c'),
]
PAGE_ACTION_SCENES = ('installer', 'advert', 'scanner', 'warning', 'installer', 'scanner')


class LocalPages:
    """Loopback only, unguessable route, no commands or filesystem serving."""
    def __init__(self):
        self.token=secrets.token_hex(20)
        self.state={'time':0,'paused':False,'tabs':0}
        self.actions=queue.Queue(maxsize=20)
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):
                pass

            def send_payload(self,status,payload,mime):
                self.send_response(status)
                self.send_header('Content-Type',mime+'; charset=utf-8')
                self.send_header('Content-Length',str(len(payload)))
                self.send_header('Cache-Control','no-store')
                self.send_header('Referrer-Policy','no-referrer')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'nonce-"+owner.token+
                                 "'; style-src 'unsafe-inline'; connect-src 'self'; img-src data:; "
                                 "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    # Chromium can cancel an in-flight poll while its owned job is
                    # closing.  On Windows that is commonly WSAECONNABORTED and is
                    # an expected disconnect, not an application error.
                    pass

            def do_GET(self):
                prefix='/'+owner.token+'/'
                if not self.path.startswith(prefix):
                    self.send_error(404); return
                path=self.path[len(prefix):]
                if path=='state':
                    payload=json.dumps(owner.state).encode('utf-8'); mime='application/json'
                elif path.startswith('tab/') and path[4:].isdigit() and 0<=int(path[4:])<20:
                    payload=owner.page(int(path[4:])).encode('utf-8'); mime='text/html'
                else:
                    self.send_error(404); return
                self.send_payload(200,payload,mime)

            def do_POST(self):
                prefix='/'+owner.token+'/action/'
                index=self.path[len(prefix):] if self.path.startswith(prefix) else ''
                try:
                    content_length=int(self.headers.get('Content-Length','0') or 0)
                except ValueError:
                    self.send_error(400); return
                if (not index.isdigit() or not 0<=int(index)<20 or content_length!=0):
                    self.send_error(404); return
                try:
                    owner.actions.put_nowait(int(index))
                    payload=b'{"accepted":true}'
                    self.send_payload(202,payload,'application/json')
                except queue.Full:
                    payload=b'{"accepted":false}'
                    self.send_payload(429,payload,'application/json')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.1),daemon=True)
        self.thread.start()

    def page(self,index):
        site,tag,title,body,action,accent=WEB_PAGES[index%len(WEB_PAGES)]
        page=PAGE_HTML
        for key,value in {'SITE_NAME':site,'PAGE_TAG':tag,'PAGE_TITLE':title,'PAGE_BODY':body,
                          'PAGE_ACTION':action,'ACCENT':accent,'NONCE':self.token,
                          'STATE_URL':json.dumps('/'+self.token+'/state'),
                          'ACTION_URL':json.dumps('/'+self.token+'/action/'+str(index))}.items():
            page=page.replace(key,value)
        return page

    def url(self,index):
        return f'http://127.0.0.1:{self.server.server_port}/{self.token}/tab/{index}'

    def action_url(self,index):
        return f'http://127.0.0.1:{self.server.server_port}/{self.token}/action/{index}'

    def drain_actions(self,limit=4):
        actions=[]
        for _ in range(limit):
            try:
                actions.append(self.actions.get_nowait())
            except queue.Empty:
                break
        return actions

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=1)


class NativeSession:
    """Own browser profile and eight files we create, with reversible names."""
    MAX_TABS=20

    def __init__(self, executable=None):
        self.executable=executable
        self.root=Path(tempfile.mkdtemp(prefix='CyberClassroom-LAB-'))
        self.profile=self.root/'browser-profile'
        self.folder=self.root/'Учебни файлове'
        self.files=[]
        try:
            self.folder.mkdir()
            for i,title in enumerate(['Доклад_история','Проект_клуб','Бележки','Задачи',
                                      'Списък_материали','График','План_урок','Резервно_копие']):
                path=self.folder/(title+'.txt')
                content=(f'УЧЕБЕН ФАЙЛ {i+1}\nСъздаден специално за демонстрацията.\n'
                         'Този текст не съдържа лични данни.\n').encode('utf-8')
                path.write_bytes(content)
                self.files.append((path,path.with_name(path.name+'.locked'),content))
        except Exception:
            # A half-created lab must not be abandoned when a full disk or an
            # endpoint-protection rule rejects one of the generated files.
            shutil.rmtree(self.root, ignore_errors=True)
            raise
        self.pages=None
        self.job=None
        self.tabs=0
        self.closed=False
        self.last_visibility=0
        self.browser_started=0
        self.browser_ready=False

    def open_tab(self):
        if self.closed or self.tabs>=self.MAX_TABS:
            return
        if not self.executable:
            raise RuntimeError('Не е намерен Edge/Chrome. Изберете msedge.exe или chrome.exe от панела.')
        if self.job is None:
            check_browser_policy(self.executable)
            self.profile.mkdir(exist_ok=True)
            default=self.profile/'Default'; default.mkdir(exist_ok=True)
            (default/'Preferences').write_text(json.dumps({'download':{'default_directory':str(self.root/'Downloads')}}),encoding='utf-8')
            self.pages=LocalPages()
            try:
                self.job=OwnedBrowserJob()
                self.browser_started=time.monotonic()
                self.browser_ready=False
            except Exception:
                self.pages.close(); self.pages=None
                raise
        args=['--user-data-dir='+str(self.profile),'--no-first-run','--no-default-browser-check',
              '--disable-sync','--disable-extensions','--disable-background-networking',
              '--disable-background-mode','--start-maximized']
        if self.tabs==0:
            args.append('--new-window')
        args.append(self.pages.url(self.tabs))
        self.job.launch(self.executable,args)
        self.tabs+=1

    def update(self,clock,paused,hide):
        if self.pages:
            self.pages.state={'time':clock,'paused':paused,'tabs':self.tabs}
        if self.job:
            now=time.monotonic()
            if not self.browser_ready:
                self.browser_ready=self.job.has_window()
                if not self.browser_ready and now-self.browser_started>15:
                    raise RuntimeError('Не се появи отделен браузърен прозорец. Изберете друг Edge/Chrome от панела.')
            if paused and hide and now-self.last_visibility>=.25:
                self.job.hide(); self.last_visibility=now
            elif not paused:
                self.job.restore()

    def drain_page_actions(self):
        return self.pages.drain_actions() if self.pages else []

    def reveal_files(self):
        if sys.platform!='win32':
            raise RuntimeError('За реалния File Explorer е необходим Windows.')
        os.startfile(str(self.folder))

    def lock_files(self,count):
        for plain,locked,content in self.files[:max(0,min(8,count))]:
            if plain.is_file() and not plain.is_symlink() and not locked.exists():
                if plain.read_bytes()==content:
                    plain.rename(locked)

    def restore_files(self):
        issues=[]
        for plain,locked,content in self.files:
            try:
                if locked.is_file() and not locked.is_symlink() and not plain.exists():
                    if locked.read_bytes()==content:
                        locked.rename(plain)
                if locked.exists():
                    issues.append(locked.name)
                elif (not plain.is_file() or plain.is_symlink() or
                      plain.read_bytes()!=content):
                    # Never overwrite a changed file or follow a replacement
                    # symlink.  Report the item instead so the teacher can inspect it.
                    issues.append(plain.name)
            except OSError:
                issues.append(locked.name if locked.exists() else plain.name)
        return issues

    def close_browser(self):
        job, self.job = self.job, None
        pages, self.pages = self.pages, None
        try:
            if job:
                job.close()
        finally:
            if pages:
                pages.close()

    def close(self):
        if self.closed:
            return
        self.closed=True
        notices=[]
        browser_closed=True
        try:
            self.close_browser()
        except Exception:
            LOG.exception('Closing the lesson browser failed')
            browser_closed=False
            notices.append('Учебният браузър може да е останал отворен; затворете го с неговия X.')
        issues=self.restore_files()
        if issues:
            LOG.warning('Lesson files need inspection: %s', ', '.join(issues))
            notices.append('Някои учебни файлове са преместени, променени или имат конфликт; '
                           'вижте учебната папка.')
        # Only our generated browser profile is removed. The visible lesson folder
        # is kept for inspection, including any files a user might have added.
        if browser_closed and self.profile.is_dir() and not self.profile.is_symlink():
            try:
                shutil.rmtree(self.profile)
            except OSError:
                LOG.exception('Removing the temporary browser profile failed: %s', self.profile)
                notices.append('Временният браузърен профил не можа да бъде изтрит; '
                               'пътят е записан в журнала.')
        self.cleanup_notice=' '.join(notices)


class Classroom:
    MAX_WINDOWS = 12

    def __init__(self, root, enable_hotkeys=True):
        self.root = root
        self.events = queue.Queue()
        self.hotkeys = None
        self.hotkeys_ok = sys.platform != 'win32'
        self.effects = []
        self.stage = None
        self.session = None
        self.last_folder = None
        self.cleanup_notice = ''
        self.browser_path = find_browser()
        self.native_kind = None
        self.native_born = 0
        self.native_count = 0
        self.rng = random.Random()
        self.running = self.paused = self.closed = False
        self.clock = 0.0
        self.mode = None
        self.event_index = 0
        self.last = time.monotonic()
        self.job = None
        self.question = 0
        self.answer = None
        self.rate = 1.0
        self.sound = tk.BooleanVar(value=False)
        self.hide_on_pause = tk.BooleanVar(value=True)
        self.duration = tk.StringVar(value='8 минути')
        self.fullscreen = tk.BooleanVar(value=True)
        self.visual_mode = tk.StringVar(value='Смесени ефекти')
        self.reporting_error = False
        self.status = tk.StringVar(value='Готовност за демонстрация')
        self.key_status = tk.StringVar(value='Проверка на глобалните комбинации…')
        self.build_panel()
        root.report_callback_exception = self.callback_error
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind_all('<Escape>', lambda e: self.stop())
        root.bind_all('<F11>', lambda e: self.toggle_fullscreen())
        root.bind_all('<F6>', lambda e: self.next_chapter())
        # Windows uses ONLY RegisterHotKey; a parallel Tk binding would toggle twice.
        if sys.platform != 'win32':
            root.bind_all('<Control-Alt-p>', lambda e: self.toggle_pause())
            root.bind_all('<Control-Alt-q>', lambda e: self.close())
        if enable_hotkeys:
            self.setup_hotkeys()
        self.tick()

    def build_panel(self):
        r = self.root
        r.title('Дигитални детективи 5.0 — ефекти върху Windows')
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        width, height = min(1000, sw-50), min(810, sh-70)
        r.geometry(f'{width}x{height}+{max(15,(sw-width)//2)}+{max(10,(sh-height)//2-20)}')
        r.configure(bg='#101b2c')
        style = ttk.Style(r)
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('TButton', font=('Segoe UI', 10), padding=(10, 7))
        style.configure('Infect.Horizontal.TProgressbar', background='#c93b4c')
        # Small laptops and Windows text scaling must not clip the controls.
        viewport = tk.Canvas(r, bg='#101b2c', highlightthickness=0)
        scrollbar = ttk.Scrollbar(r, orient='vertical', command=viewport.yview)
        scrollbar.pack(side='right', fill='y')
        viewport.pack(fill='both', expand=True)
        viewport.configure(yscrollcommand=scrollbar.set)
        r = tk.Frame(viewport, bg='#101b2c')
        panel_item = viewport.create_window(0, 0, anchor='nw', window=r)
        r.bind('<Configure>', lambda e: viewport.configure(scrollregion=viewport.bbox('all')))
        viewport.bind('<Configure>', lambda e: viewport.itemconfigure(panel_item, width=e.width))
        self.root.bind('<MouseWheel>', lambda e: viewport.yview_scroll(-int(e.delta/120), 'units'))
        label(r, 'ДИГИТАЛНИ ДЕТЕКТИВИ / 5.0', 23, '#e9f1fc', bold=True).pack(anchor='w', padx=25, pady=(15, 4))
        label(r, 'Твоят Windows • истински Edge/Chrome • до 20 раздела • учебна папка във File Explorer',
              11, '#9bb2cc').pack(anchor='w', padx=26, pady=(0, 14))
        keys = tk.Frame(r, bg='#1c314b')
        keys.pack(fill='x', padx=25)
        label(keys, 'Ctrl + Alt + P     Пауза / продължаване', 14, '#80e2c4', bold=True).pack(anchor='w', padx=16, pady=(12, 3))
        label(keys, 'Ctrl + Alt + Q     Спиране, затваряне на учебния браузър и изход', 13, '#ffb5bc', bold=True).pack(anchor='w', padx=16, pady=3)
        label(keys, 'Esc: спиране и панел   |   F11: цял екран   |   F6: следваща глава (в наш прозорец)',
              10, '#c3d1e2').pack(anchor='w', padx=16, pady=(3, 12))
        row = tk.Frame(r, bg='#101b2c')
        row.pack(fill='x', padx=25, pady=(12, 0))
        label(row, '', 10, '#9bb2cc', textvariable=self.key_status, wraplength=590).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Провери отново', command=self.setup_hotkeys).pack(side='right')
        ttk.Button(row, text='Избор на браузър', command=self.choose_browser).pack(side='right', padx=6)
        ttk.Button(row, text='Журнал', command=self.show_log).pack(side='right')
        settings = tk.Frame(r, bg='#101b2c')
        settings.pack(fill='x', padx=25, pady=9)
        label(settings, 'Продължителност:', 11, '#e9f1fc').pack(side='left')
        ttk.Combobox(settings, textvariable=self.duration, width=11, state='readonly',
                     values=['5 минути', '8 минути', '12 минути']).pack(side='left', padx=8)
        tk.Checkbutton(settings, text='Цял екран', variable=self.fullscreen, bg='#101b2c', fg='#e9f1fc',
                       selectcolor='#20354b', activebackground='#101b2c', activeforeground='white').pack(side='left', padx=5)
        tk.Checkbutton(settings, text='Звук', variable=self.sound, bg='#101b2c', fg='#e9f1fc',
                       selectcolor='#20354b', activebackground='#101b2c', activeforeground='white').pack(side='left', padx=15)
        tk.Checkbutton(settings, text='Скривай ефектите при пауза', variable=self.hide_on_pause,
                       bg='#101b2c', fg='#e9f1fc', selectcolor='#20354b',
                       activebackground='#101b2c', activeforeground='white').pack(side='left')
        visuals = tk.Frame(r, bg='#101b2c')
        visuals.pack(fill='x', padx=25, pady=(0, 8))
        label(visuals, 'Ефект върху екрана:', 11, '#e9f1fc').pack(side='left')
        ttk.Combobox(visuals, textvariable=self.visual_mode, width=20, state='readonly',
                     values=['Смесени ефекти', 'Разкъсване', 'Разтичане', 'Безкраен екран']).pack(side='left', padx=8)
        label(visuals, 'Еднократен кадър от основния монитор, само в RAM', 10, '#9bb2cc').pack(side='left')
        self.start_button = ttk.Button(r, text='▶  СТАРТИРАЙ ЦЯЛАТА ИСТОРИЯ',
                                       command=lambda: self.start('auto'))
        self.start_button.pack(fill='x', padx=25, pady=(0, 10))
        manual = tk.Frame(r, bg='#101b2c')
        manual.pack(fill='x', padx=25)
        for i, (title, mode) in enumerate([
            ('Много браузърни раздели', 'tabs'), ('Лавина от грешки', 'errorwall'),
            ('Изкривяване на екрана', 'glitch'), ('Подозрителен терминал', 'terminal_chapter'),
            ('Файлове и „криптиране“', 'files_chapter'), ('WannaCry: откуп', 'ransom'),
            ('Син екран', 'blue'), ('Pegasus: учебен модел', 'spyware'),
            ('Реклами и предупреждения', 'advert'), ('Фалшиво сканиране', 'scanner'),
            ('Сравнение на заплахите', 'debrief'), ('Фалшиво рестартиране', 'reboot')]):
            ttk.Button(manual, text=title, command=lambda m=mode: self.start(m)).grid(
                row=i//3, column=i%3, sticky='ew', padx=(0, 6), pady=3)
        for column in range(3):
            manual.columnconfigure(column, weight=1)
        controls = tk.Frame(r, bg='#101b2c')
        controls.pack(fill='x', padx=25, pady=10)
        self.resume_button = ttk.Button(controls, text='Продължи', command=self.toggle_pause, state='disabled')
        self.resume_button.pack(side='left')
        ttk.Button(controls, text='Спри / изчисти', command=self.stop).pack(side='left', padx=7)
        ttk.Button(controls, text='Разследване с класа', command=self.open_quiz).pack(side='left')
        ttk.Button(controls, text='Следваща глава', command=self.next_chapter).pack(side='left', padx=7)
        ttk.Button(controls, text='Учебна папка', command=self.show_lesson_folder).pack(side='left')
        ttk.Button(controls, text='Изход', command=self.close).pack(side='right')
        label(r, '', 11, '#80e2c4', textvariable=self.status, wraplength=width-55).pack(anchor='w', padx=26, pady=6)
        label(r, 'Истински браузър с отделен временен профил и локални учебни страници.\n'
              'Създава 8 учебни файла. След спиране връща имената им; папката остава за преглед.\n'
              'Личните файлове, камерата, микрофонът и системните настройки не се използват.',
              10, '#9bb2cc', wraplength=width-55).pack(anchor='w', padx=26, pady=(6, 15))

    def show_log(self):
        if LOG_PATH is not None and LOG_PATH.is_file() and sys.platform == 'win32':
            os.startfile(str(LOG_PATH))
        else:
            self.status.set('Журналът се създава при обичайно стартиране с py cyber_classroom.py.')

    def callback_error(self, exc_type, exc, traceback):
        self.report_error('Грешка при управление на демонстрацията', exc, traceback)

    def report_error(self, context, exc, traceback=None):
        LOG.error('%s (mode=%s, clock=%.2f)', context, self.mode, self.clock,
                  exc_info=(type(exc), exc, traceback or exc.__traceback__))
        if self.reporting_error or self.closed:
            return
        self.reporting_error = True
        try:
            self.stop('Ефектите са спрени. Вижте съобщението за грешка и бутона „Журнал“.')
            detail = str(exc)[:650]
            log_note = ('\n\nЖурнал: ' + str(LOG_PATH)) if LOG_PATH else ''
            messagebox.showerror('Дигитални детективи — грешка',
                                 context + '\n\n' + detail + log_note, parent=self.root)
        finally:
            self.reporting_error = False

    def choose_browser(self):
        if self.running:
            self.stop()
        path=filedialog.askopenfilename(parent=self.root,title='Изберете msedge.exe или chrome.exe',
                                        filetypes=[('Браузър за Windows','*.exe')])
        if path:
            chosen=Path(path)
            if chosen.name.lower() not in ('msedge.exe','chrome.exe'):
                self.status.set('Изберете изпълнимия файл msedge.exe или chrome.exe.'); return
            self.browser_path=chosen
            self.status.set('Избран браузър: '+chosen.name)

    def show_lesson_folder(self):
        if self.last_folder is not None and self.last_folder.is_dir() and sys.platform=='win32':
            os.startfile(str(self.last_folder))
        else:
            self.status.set('Учебната папка ще се създаде при стартиране на демонстрацията.')

    def setup_hotkeys(self):
        if self.running:
            self.stop()
        if self.hotkeys is not None:
            self.hotkeys.close()
            self.hotkeys = None
        # Discard events from a previous registration attempt before starting a new one.
        while not self.events.empty():
            try:
                self.events.get_nowait()
            except queue.Empty:
                break
        if sys.platform == 'win32':
            self.hotkeys_ok = False
            self.key_status.set('Проверка на комбинациите…')
            self.hotkeys = GlobalHotkeys(self.events)
        else:
            self.hotkeys_ok = True
            self.key_status.set('Преглед извън Windows: комбинациите работят само в наш активен прозорец.')

    def show_panel(self):
        self.root.deiconify()
        self.root.attributes('-topmost', True)
        self.root.lift()
        self.root.focus_force()

    def hide_panel(self):
        self.root.attributes('-topmost', False)
        self.root.withdraw()

    def start(self, mode):
        if not self.hotkeys_ok:
            self.status.set('Изчакайте успешната регистрация на двете комбинации.')
            return
        self.clear_effects()
        self.close_stage()
        self.close_session()
        self.clock = 0.0
        self.event_index = 0
        self.mode = mode
        self.running = True
        self.paused = False
        self.native_kind=None
        self.rate = 480/(int(self.duration.get().split()[0])*60) if mode == 'auto' else 1.0
        self.last = time.monotonic()
        try:
            if sys.platform!='win32':
                raise RuntimeError('Тази версия работи върху истински Windows 10/11.')
            if mode in ('auto', 'glitch') and Image is None:
                raise RuntimeError('За ефектите върху екрана е нужен Pillow.\n'
                                   'Изпълнете в Terminal: py -m pip install pillow\n'
                                   'След това затворете и стартирайте програмата отново.\n'
                                   + (PILLOW_ERROR or ''))
            self.cleanup_notice = ''
            self.session=NativeSession(self.browser_path)
            self.last_folder=self.session.folder
            self.hide_panel()
            LOG.info('Starting mode=%s, duration=%s, screen=%sx%s', mode, self.duration.get(),
                     self.root.winfo_screenwidth(), self.root.winfo_screenheight())
            self.resume_button.configure(text='Пауза', state='normal')
            if mode == 'auto':
                self.advance(0)
            elif mode == 'advert':
                self.spawn('advert'); self.spawn('warning'); self.spawn('notification')
            else:
                self.spawn(mode)
        except Exception as exc:
            self.report_error('Не успях да стартирам демонстрацията', exc)

    def toggle_pause(self):
        if not self.running:
            self.show_panel()
            return
        self.paused = not self.paused
        self.last = time.monotonic()
        if self.session:
            self.session.update(self.clock,self.paused,self.hide_on_pause.get())
        if self.paused:
            if self.stage is not None:
                self.stage.win.attributes('-topmost', False)
                if self.hide_on_pause.get():
                    self.stage.win.withdraw()
            for effect in self.effects:
                if not effect.closed:
                    effect.win.attributes('-topmost', False)
                    if self.hide_on_pause.get():
                        effect.win.withdraw()
            self.resume_button.configure(text='▶ Продължи')
            self.show_panel()
        else:
            self.hide_panel()
            if self.stage is not None and getattr(self.stage, 'ready', True):
                self.stage.win.deiconify()
                self.stage.win.attributes('-topmost', True)
                self.stage.win.lift()
            for effect in self.effects:
                if not effect.closed:
                    effect.win.deiconify()
                    effect.win.attributes('-topmost', True)
                    effect.win.lift()
            self.resume_button.configure(text='Пауза')
        self.update_status()

    def clear_effects(self):
        for effect in self.effects:
            effect.close()
        self.effects.clear()

    def close_stage(self):
        if self.stage is not None:
            self.stage.close()
            self.stage = None

    def close_session(self):
        self.native_kind=None
        if self.session is not None:
            session,self.session=self.session,None
            try:
                session.close()
                self.cleanup_notice=getattr(session,'cleanup_notice','')
            except Exception:
                LOG.exception('Lesson cleanup failed')
                self.cleanup_notice='Учебната папка е запазена: '+str(session.folder)

    def toggle_fullscreen(self):
        self.fullscreen.set(not self.fullscreen.get())
        if self.stage is not None:
            self.stage.win.attributes('-fullscreen', self.fullscreen.get())

    def next_chapter(self):
        if not self.running or self.mode != 'auto':
            return
        target = next((t for t, _ in CHAPTERS if t > self.clock+0.5), 480)
        if self.paused:
            self.toggle_pause()
        self.clear_effects()
        self.clock = target
        self.event_index = next(i for i, (t, _) in enumerate(TIMELINE) if t >= target)
        try:
            self.advance(0)
        except Exception as exc:
            self.report_error('Не успях да отворя следващата глава', exc)
        self.last = time.monotonic()

    def stop(self, message='Ефектите са спрени. Работният плот е свободен.'):
        self.running = self.paused = False
        self.clear_effects()
        self.close_stage()
        self.close_session()
        self.resume_button.configure(text='Продължи', state='disabled')
        self.status.set(self.cleanup_notice or message)
        self.show_panel()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.running = False
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job = None
        self.clear_effects()
        self.close_stage()
        self.close_session()
        if self.hotkeys is not None:
            self.hotkeys.close()
        self.root.destroy()

    def update_status(self):
        if self.running:
            elapsed = int(self.clock/self.rate)
            chapter = next(name for t, name in reversed(CHAPTERS) if t <= self.clock) if self.mode == 'auto' else 'Отделна сцена'
            self.status.set(f'{"ПАУЗА" if self.paused else "В ход"}  •  '
                            f'{elapsed//60:02}:{elapsed%60:02}  •  '
                            f'{chapter}')

    def tick(self):
        if self.closed:
            return
        self.job = None
        try:
            while True:
                try:
                    action, payload = self.events.get_nowait()
                except queue.Empty:
                    break
                if action == 'quit':
                    self.close()
                    return
                if action == 'pause':
                    self.toggle_pause()
                elif action == 'hotkeys_ready':
                    self.hotkeys_ok = True
                    self.key_status.set('Глобалните Ctrl+Alt+P и Ctrl+Alt+Q са готови.')
                elif action == 'hotkeys_error':
                    LOG.error('Global hotkeys: %s', payload)
                    self.hotkeys_ok = False
                    self.stop()
                    self.key_status.set(payload)
            now = time.monotonic()
            dt, self.last = max(0, now-self.last), now
            self.advance(dt)
            if self.session:
                self.session.update(self.clock,self.paused,self.hide_on_pause.get())
                if self.running and not self.paused:
                    for page_index in self.session.drain_page_actions():
                        self.handle_page_action(page_index)
            self.update_status()
        except Exception as exc:
            # If an effect fails, recover the controller instead of leaving overlays behind.
            self.report_error('Демонстрацията е спряна заради грешка', exc)
        if not self.closed:
            self.job = self.root.after(60, self.tick)

    def advance(self, dt):
        if not self.running or self.paused:
            return
        self.clock += dt*self.rate
        if self.mode == 'auto':
            while self.event_index < len(TIMELINE) and self.clock+1e-7 >= TIMELINE[self.event_index][0]:
                _, name = TIMELINE[self.event_index]
                self.event_index += 1
                if name == 'finish':
                    self.stop('Историята приключи. Обсъдете случилото се или отворете разследването.')
                    return
                self.spawn(name)
        elif self.clock >= 300:
            self.stop('Ръчният ефект приключи след 5 минути.')
            return
        for effect in list(self.effects):
            effect.tick()
        self.effects[:] = [e for e in self.effects if not e.closed]
        self.advance_native()
        if self.stage is not None:
            self.stage.tick()
        if not self.effects and self.stage is None and self.native_kind is None and self.mode != 'auto':
            self.stop()

    def advance_native(self):
        if not self.session or not self.native_kind:
            return
        elapsed=max(0,self.clock-self.native_born)
        if self.native_kind=='tabs':
            target=min(self.session.MAX_TABS,1+int(elapsed/2.7))
            # At most one launch per UI tick, even after a delayed event loop.
            if self.session.tabs<target and self.session.browser_ready:
                self.session.open_tab()
        elif self.native_kind=='errors':
            target=min(24,1+int(elapsed/1.7))
            if self.native_count<target:
                self.spawn('error' if self.native_count%4 else 'warning')
                self.native_count+=1
        elif self.native_kind=='files':
            self.session.lock_files(max(0,int((elapsed-4)/3)))

    def handle_page_action(self,index):
        scene=PAGE_ACTION_SCENES[index%len(PAGE_ACTION_SCENES)]
        LOG.info('Browser action tab=%s scene=%s', index, scene)
        self.spawn(scene)

    def effect(self, title, width, height, **kwargs):
        self.effects[:] = [e for e in self.effects if not e.closed]
        while len(self.effects) >= self.MAX_WINDOWS:
            self.effects.pop(0).close()
        effect = Effect(self, title, width, height, **kwargs)
        self.effects.append(effect)
        return effect

    def spawn(self, kind):
        if self.paused or not self.running:
            return
        LOG.info('Scene=%s, clock=%.2f', kind, self.clock)
        if kind in ('browser', 'tabs', 'errorwall', 'terminal_chapter', 'glitch',
                    'files_chapter', 'ransom', 'blue', 'reboot', 'spyware', 'debrief'):
            self.clear_effects()
            self.close_stage()
            self.native_kind=None
            self.native_born=self.clock
            self.native_count=0
            if self.session and kind not in ('browser','tabs'):
                self.session.close_browser()
        getattr(self, 'scene_'+kind)()
        if self.sound.get() and kind in ('warning', 'error', 'notification'):
            self.root.bell()

    def stage_mode(self, mode):
        if self.stage is None:
            self.stage = Stage(self)
        self.stage.change(mode)

    def scene_browser(self):
        self.native_kind='browser'
        self.session.open_tab()

    def scene_tabs(self):
        self.native_kind='tabs'
        if self.session.tabs==0:
            self.session.open_tab()

    def scene_errorwall(self):
        self.native_kind='errors'

    def scene_terminal_chapter(self):
        self.scene_terminal()

    def scene_glitch(self):
        self.stage=DesktopOverlay(self)

    def scene_files_chapter(self):
        self.native_kind='files'
        self.session.reveal_files()

    def scene_reboot(self):
        self.stage_mode('reboot')

    def scene_spyware(self):
        self.stage_mode('spyware')

    def scene_debrief(self):
        self.stage_mode('debrief')

    def scene_installer(self):
        e = self.effect('SuperMod Setup', 570, 370, position='center')
        label(e.win, 'SuperMod', 25, '#2164a4', bold=True).pack(anchor='w', padx=27, pady=(22, 4))
        label(e.win, 'Installing required components…', 12).pack(anchor='w', padx=28, pady=7)
        label(e.win, 'Please wait while Setup installs SuperMod on your computer.', 10).pack(anchor='w', padx=28, pady=9)
        bar = ttk.Progressbar(e.win, maximum=100)
        bar.pack(fill='x', padx=28, pady=12)
        detail = label(e.win, 'Extracting package…', 10, '#666666')
        detail.pack(anchor='w', padx=28)
        percent = label(e.win, '0%', 10, '#666666')
        percent.pack(anchor='e', padx=28, pady=(0, 4))
        controls = tk.Frame(e.win, bg='#f3f3f3')
        controls.pack(fill='x', padx=28, pady=(8, 20))
        close_button = ttk.Button(controls, text='Cancel', command=e.close)
        close_button.pack(side='right', ipadx=12)
        state = {'complete': False}
        def update(t):
            progress = min(100, int(t/12*100))
            bar['value'] = progress
            percent.configure(text=f'{progress}%')
            if t < 3:
                text = 'Extracting package…'
            elif t < 7:
                text = 'Copying components…'
            elif t < 10:
                text = 'Registering browser helper…'
            elif progress < 100:
                text = 'Finishing installation…'
            else:
                text = 'Installation complete.'
                if not state['complete']:
                    state['complete'] = True
                    close_button.configure(text='Close')
            detail.configure(text=text)
        e.update_view = update
        e.limit = 15

    def scene_notification(self):
        e = self.effect('Известие', 420, 180, bg='#242424', position='toast')
        label(e.win, '⚠  Защита на устройството', 14, 'white', bold=True).pack(anchor='w', padx=21, pady=(20, 8))
        label(e.win, 'Открита е подозрителна активност.\nНепознато приложение се изпълнява във фонов режим.',
              11, '#e2e2e2', wraplength=375).pack(anchor='w', padx=21)
        ttk.Button(e.win, text='Преглед', command=lambda: [e.close(), self.spawn('warning')]).pack(anchor='e', padx=18, pady=13)
        e.limit = 18

    def scene_warning(self):
        e = self.effect('Security Center — Action required', 550, 330)
        top = tk.Frame(e.win, bg='#b72935')
        top.pack(fill='x')
        label(top, '⚠  Threats detected', 23, 'white', bold=True).pack(anchor='w', padx=23, pady=19)
        label(e.win, 'Potentially unwanted software detected', 13, bold=True).pack(anchor='w', padx=24, pady=(17, 10))
        label(e.win, 'Status:   Active\nProcess:  update_helper.exe\nRisk:       High', 11).pack(anchor='w', padx=25)
        label(e.win, 'Your documents may be at risk.', 11, '#a52531').pack(anchor='w', padx=25, pady=12)
        row = tk.Frame(e.win, bg='#f3f3f3'); row.pack(fill='x', padx=22, pady=6)
        ttk.Button(row, text='Scan now', command=lambda: [e.close(), self.spawn('scanner')]).pack(side='left')
        ttk.Button(row, text='Dismiss', command=e.close).pack(side='right')

    def scene_advert(self):
        e = self.effect('Special offer — Browser', 500, 365, bg='white')
        label(e.win, '  https://bonus-rewards.example/claim', 10, '#555555', bg='#ededed').pack(fill='x', ipady=8)
        title, subtitle = self.rng.choice([
            ('ПОЗДРАВЛЕНИЯ!', 'Избрани сте за специална награда!'),
            ('КОМПЮТЪРЪТ Е БАВЕН?', 'Изтеглете нашия „ускорител“ веднага.'),
            ('БЕЗПЛАТНИ БОНУСИ!', 'Офертата изтича след броени минути.')])
        label(e.win, title, 25, '#8523ac', bold=True).pack(pady=(26, 11))
        label(e.win, subtitle, 12, wraplength=445).pack(pady=6)
        countdown = label(e.win, 'Оставащо време: 01:59', 18, '#c02e42', bold=True)
        countdown.pack(pady=15)
        ttk.Button(e.win, text='ВЗЕМИ СЕГА', command=lambda: self.spawn('warning')).pack(ipadx=35, pady=7)
        ttk.Button(e.win, text='Затвори', command=e.close).pack(pady=5)
        def update(t):
            n = max(0, 119-int(t)); countdown.configure(text=f'Оставащо време: {n//60:02}:{n%60:02}')
        e.update_view = update

    def scene_terminal(self):
        e = self.effect(r'C:\Windows\System32\cmd.exe', 810, 455, bg='#0c0c0c')
        text = tk.Text(e.win, bg='#0c0c0c', fg='#c6c6c6', insertbackground='white',
                       font=('Consolas', 11), relief='flat', wrap='word', padx=10, pady=10,
                       state='disabled', takefocus=False)
        text.pack(fill='both', expand=True)
        state = {'count': -1}
        def update(t):
            count = min(len(TERMINAL_LINES), 1+int(t/1.0))
            if count != state['count']:
                text.configure(state='normal')
                text.delete('1.0', 'end')
                text.insert('end', '\n'.join(TERMINAL_LINES[:count])+'\n_')
                text.see('end')
                text.configure(state='disabled')
                state['count'] = count
        e.update_view = update

    def scene_scanner(self):
        e = self.effect('PC Defender — System Scan', 590, 365)
        label(e.win, 'System scan in progress', 23, '#294867', bold=True).pack(anchor='w', padx=25, pady=(21, 12))
        stat = label(e.win, '', 12); stat.pack(anchor='w', padx=25, pady=5)
        bar = ttk.Progressbar(e.win, maximum=100, style='Infect.Horizontal.TProgressbar')
        bar.pack(fill='x', padx=25, pady=15)
        result = label(e.win, '', 18, '#b52c3f', bold=True); result.pack(anchor='w', padx=25, pady=7)
        label(e.win, 'Adware.PopUps\nTrojan.FakeInstaller\nSuspicious.UpdateHelper', 11).pack(anchor='w', padx=25, pady=8)
        ttk.Button(e.win, text='Close', command=e.close).pack(anchor='e', padx=25, pady=12)
        def update(t):
            p = min(1, t/20)
            bar['value'] = p*100
            stat.configure(text=f'Files checked: {int(p*18427):,}    •    {int(p*100)}%')
            result.configure(text=f'Threats found: {min(37, int(t*2))}')
        e.update_view = update

    def scene_error(self):
        e = self.effect('Application Error', 490, 220)
        label(e.win, '×', 40, '#b62435', bold=True).pack(side='left', padx=(20, 5))
        body = tk.Frame(e.win, bg='#f3f3f3'); body.pack(fill='both', expand=True, padx=18, pady=20)
        label(body, 'update_helper.exe has stopped responding', 12, bold=True,
              wraplength=365).pack(anchor='w', pady=(7, 12))
        label(body, 'The operation could not be completed.\nError code: 0x00000005', 10).pack(anchor='w')
        ttk.Button(body, text='OK', command=e.close).pack(anchor='e', pady=17)

    def scene_ransom(self):
        self.stage_mode('ransom')

    def scene_blue(self):
        self.stage_mode('blue')

    def open_quiz(self):
        self.stop()
        self.hide_panel()
        self.mode = 'quiz'
        self.question = 0
        self.answer = None
        e = self.effect('Разследване с класа', 970, 620, bg='#101b2c', position='center')
        self.quiz_effect = e
        self.quiz_body = tk.Frame(e.win, bg='#101b2c')
        self.quiz_body.pack(fill='both', expand=True, padx=28, pady=22)
        e.win.protocol('WM_DELETE_WINDOW', self.stop)
        self.draw_quiz()

    def draw_quiz(self):
        body = self.quiz_body
        for widget in body.winfo_children():
            widget.destroy()
        if self.question >= len(QUESTIONS):
            label(body, 'Разследването приключи', 27, '#80e2c4', bold=True).pack(anchor='w', pady=10)
            label(body, 'Спрете. Проверете. Потърсете помощ.', 22, 'white').pack(anchor='w', pady=22)
            label(body, 'Рекламите, терминалът и синият екран не са сами по себе си доказателство за вирус.\n\n'
                  'Проверявайте източниците и не изключвайте защитата заради непознати програми.\n\n'
                  'При инцидент уведомете учителя или администратора.\n\n'
                  'Защитените и проверени резервни копия са част от подготовката.', 14,
                  '#d4e1f2', wraplength=870).pack(anchor='w', pady=15)
            ttk.Button(body, text='Към панела', command=self.stop).pack(anchor='w', pady=20)
            return
        title, evidence, options, correct, explanation = QUESTIONS[self.question]
        label(body, title, 23, '#80e2c4', bold=True).pack(anchor='w', pady=(0, 16))
        label(body, evidence, 13, '#e9f1fc', wraplength=870).pack(anchor='w', pady=(0, 16))
        for i, option in enumerate(options):
            color = '#28425e'
            if self.answer is not None:
                if i == correct: color = '#17634e'
                elif i == self.answer: color = '#79333f'
            tk.Button(body, text=option, command=lambda n=i: self.choose(n), bg=color, fg='white',
                      activebackground=color, activeforeground='white', font=('Segoe UI', 11),
                      relief='flat', anchor='w', wraplength=840, padx=14, pady=10).pack(fill='x', pady=4)
        if self.answer is not None:
            label(body, 'Точно така.' if self.answer == correct else 'Нека разгледаме защо.',
                  15, '#80e2c4', bold=True).pack(anchor='w', pady=(15, 6))
            label(body, explanation, 11, '#d4e1f2', wraplength=875).pack(anchor='w')
            ttk.Button(body, text='Следваща улика →', command=self.next_question).pack(anchor='e', pady=15)
        else:
            label(body, 'Обсъдете с класа, след което изберете отговор.', 11, '#9bb2cc').pack(anchor='w', pady=16)

    def choose(self, index):
        if self.answer is None:
            self.answer = index
            self.draw_quiz()

    def next_question(self):
        self.question += 1
        self.answer = None
        self.draw_quiz()


class Stage:
    """Only the ransom/crash/reboot and explanatory scenes use a full screen.
    There is deliberately no painted desktop or browser in this version.
    """

    def __init__(self, app):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.withdraw()
        self.win.title('Дигитални детективи — демонстрационен екран')
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.win.geometry(f'{min(1400,sw-60)}x{min(850,sh-90)}+25+25')
        self.win.configure(bg='#102441')
        self.win.attributes('-fullscreen', app.fullscreen.get())
        self.win.attributes('-topmost', True)
        self.win.protocol('WM_DELETE_WINDOW', app.stop)
        self.canvas = tk.Canvas(self.win, bg='#102441', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Button-1>', self.click)
        self.mode = 'blue'
        self.born = app.clock
        self.elapsed = 0
        self.sx = self.sy = self.scale = 1.0
        self.buttons = []
        self.recovery_notice = ''
        self.win.deiconify()
        self.win.lift()
        self.canvas.focus_set()

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass

    def change(self, mode):
        self.mode = mode
        self.born = self.app.clock
        self.elapsed = 0
        self.recovery_notice = ''
        self.win.lift()
        self.render()

    def tick(self):
        self.elapsed = max(0, self.app.clock-self.born)
        self.render()

    def click(self, event):
        if self.app.paused or not self.app.running:
            return
        x, y = event.x/self.sx, event.y/self.sy
        for bx, by, w, h, action in reversed(self.buttons):
            if bx <= x <= bx+w and by <= y <= by+h:
                action()
                if self.app.stage is self:
                    self.render()
                break

    def rect(self, x, y, w, h, fill, outline='', stroke=1):
        return self.canvas.create_rectangle(x*self.sx, y*self.sy, (x+w)*self.sx, (y+h)*self.sy,
                       fill=fill, outline=outline, width=max(1, stroke*self.scale))

    def oval(self, x, y, w, h, fill, outline='', stroke=1):
        return self.canvas.create_oval(x*self.sx, y*self.sy, (x+w)*self.sx, (y+h)*self.sy,
                       fill=fill, outline=outline, width=max(1, stroke*self.scale))

    def line(self, x1, y1, x2, y2, color, width=1):
        return self.canvas.create_line(x1*self.sx, y1*self.sy, x2*self.sx, y2*self.sy,
                                       fill=color, width=max(1,width*self.scale))

    def text(self, x, y, value, size=22, color='#eaf2fb', bold=False, width=1450, family='Segoe UI'):
        return self.canvas.create_text(x*self.sx, y*self.sy, anchor='nw', text=value,
            fill=color, width=width*self.sx,
            font=(family, -max(8, round(size*self.scale)), 'bold' if bold else 'normal'))

    def button(self, x, y, w, h, caption, action, fill='#244b70', color='white', size=19):
        self.rect(x,y,w,h,fill)
        self.text(x+17,y+(h-size)/2-3,caption,size,color,True,width=w-30)
        self.buttons.append((x,y,w,h,action))

    def render(self):
        self.sx = max(1,self.canvas.winfo_width())/1600
        self.sy = max(1,self.canvas.winfo_height())/900
        self.scale = min(self.sx,self.sy)
        self.canvas.delete('all')
        self.buttons = []
        renderer = {'ransom':self.ransom, 'blue':self.blue, 'reboot':self.reboot,
                    'spyware':self.spyware, 'debrief':self.debrief}[self.mode]
        renderer()

    def ransom(self):
        self.rect(0,0,1600,900,'#7a0f20')
        self.rect(0,0,1600,47,'#e0e4eb')
        self.text(18,11,'Wana Decrypt0r — учебна възстановка',20,'#263747')
        self.text(1540,10,'×',22,'#263747')
        self.buttons.append((1520,0,80,47,self.app.stop))
        self.text(358,80,'Ooops, your files have been encrypted!',38,'white',True,width=1155)
        self.oval(89,91,161,161,'#e9d4da')
        self.rect(126,162,88,69,'#7a0f20')
        self.oval(139,126,62,80,'',outline='#7a0f20',stroke=13)
        self.text(38,294,'Payment deadline',25,'#f2db77',True,width=285)
        remaining=max(0,299-int(self.elapsed))
        self.text(57,337,f'{remaining//60:02}:{remaining%60:02}',59,'white',True,width=252)
        self.rect(42,438,249,167,'#620b19',outline='#be7885')
        self.text(61,462,'STATUS',19,'#dea6b1',True)
        self.text(61,505,'FILES LOCKED',24,'white',True,width=215)
        self.text(60,558,'8 documents',20,'#e6b9c4')
        self.rect(351,157,1200,521,'#fcfaf9')
        self.text(387,186,'Какво се случи с моите файлове?',30,'#22252b',True,width=1110)
        self.text(389,248,'Документите, снимките и проектите ви са заключени.\n'
                  'За възстановяване се иска ключ, който нападателят обещава срещу плащане.',
                  24,'#343940',width=1100)
        self.text(388,349,'Може ли да си върна документите?',29,'#22252b',True)
        self.text(389,405,'Таймерът и заплахата ви притискат да действате веднага.\n'
                  'Нападателят иска да повярвате, че плащането е единственият изход.',
                  24,'#343940',width=1100)
        self.text(389,520,'Recovery ID: CLASSROOM-0001',22,'#5e6771')
        self.text(389,565,'Payment address: unavailable',22,'#5e6771')
        self.button(353,710,280,64,'Check recovery key',lambda:self.set_recovery_notice(),
                    '#e6e6e6','#263a4d',20)
        self.rect(659,710,892,64,'#630b1b')
        self.text(685,730,self.recovery_notice or 'No recovery key found.',20,'#eed1d7')
        self.text(358,826,'WannaCry (2017) • възстановка на външния вид • няма шифроване или плащане',19,'#e0a9b5')

    def set_recovery_notice(self):
        self.recovery_notice='Recovery service unavailable. Няма реална операция.'

    def blue(self):
        self.rect(0,0,1600,900,'#0078d7')
        self.text(173,105,':(',145,'white')
        self.text(181,327,'Your device ran into a problem and needs to restart.',38,'white',width=1240)
        self.text(183,401,"We're just collecting some error info, and then we'll restart for you.",
                  30,'white',width=1230)
        self.text(183,533,f'{min(99,int(self.elapsed*3.8))}% complete',34,'white')
        self.text(184,687,'If you call a support person, give them this info:\nStop code: CRITICAL_PROCESS_DIED',
                  23,'white',width=1200)

    def reboot(self):
        self.rect(0,0,1600,900,'#07101b')
        for i in range(4):
            self.rect(736+(i%2)*68,260+(i//2)*68,59,59,'#b1dbf5')
        for i in range(8):
            angle=self.elapsed*1.4+i*math.pi/4
            self.oval(795+28*math.cos(angle),498+28*math.sin(angle),7,7,
                      ['#d3e5f2','#b1c8dc','#8aacc8','#6888a4','#456982','#304b61','#20364a','#172a3e'][i])
        self.text(720,570,'Restarting',28,'#e1eaf5')

    def spyware(self):
        self.rect(0,0,1600,900,'#08141f')
        self.text(55,34,'PEGASUS',39,'#8ddac9',True)
        self.text(58,91,'Когато опасността не се вижда на екрана',24,'#a0b9ce')
        # Left: a quiet, entirely fictional phone, not a claim about Windows infection.
        self.rect(70,151,350,658,'#03080e',outline='#536f85',stroke=3)
        self.rect(84,174,322,600,'#163346')
        self.rect(171,164,145,22,'#03080e')
        self.text(103,204,'09:41',17,'white',True)
        self.text(101,263,'Петък',19,'#a2c5d6')
        self.text(99,300,'Всичко изглежда\nнормално.',32,'white',True,width=290)
        colors=['#598caa','#599d86','#a68f62','#8c7caf','#5d7da1','#966b80']
        for i,name in enumerate(['Чат','Снимки','Бележки','Календар','Камера','Контакти']):
            x=108+(i%3)*98; y=461+(i//3)*105
            self.rect(x,y,65,62,colors[i])
            self.text(x+21,y+12,name[0],30,'#f4f8fd',True)
            self.text(x-3,y+71,name,14,'#d1e3ec',width=96)
        self.rect(168,750,150,5,'#b6ccd9')
        self.text(89,825,'Измислен телефон / DEVICE 01',17,'#739ab0')
        if self.elapsed<12:
            self.text(533,258,'Няма изскачащи реклами.\nНяма червен предупредителен екран.',37,'#e4f1f8',True,width=980)
            self.text(536,407,'Означава ли това, че устройството е защитено?',27,'#90b4ca',width=940)
            self.text(537,536,'След малко ще видите условно какво може да остава скрито.',23,'#628ca5',width=900)
        else:
            self.spyware_reveal()
        self.text(526,822,'Учебен модел с измислени данни; не е действителен интерфейс на Pegasus.',17,'#78a1b6',width=1010)
        self.text(526,855,'Камерата, микрофонът и личните файлове на този компютър не се използват.',17,'#78a1b6',width=1010)

    def spyware_reveal(self):
        elapsed=self.elapsed-12
        self.rect(490,158,1054,63,'#183545')
        self.text(514,176,'СКРИТО СЪБИРАНЕ НА ДАННИ • условна визуализация',23,'#bceadf',True,width=997)
        count=min(128,int(elapsed*4))
        self.rect(490,242,503,236,'#112a3a')
        self.text(514,263,'СЪОБЩЕНИЯ / КОНТАКТИ',19,'#86b7c6',True)
        messages=['Участник А: Срещата е в 15:00.',
                  'Участник Б: Изпрати ли проекта?',
                  'Участник В: Ще закъснея малко.']
        for i,line in enumerate(messages):
            if elapsed >= i*3:
                self.text(514,311+i*39,line,20,'#d2e5ee',width=455)
        self.text(514,434,f'Записи в учебния набор: {count}',17,'#75c7b2')
        self.rect(1014,242,530,236,'#112a3a')
        self.text(1037,263,'МЕСТОПОЛОЖЕНИЕ',19,'#86b7c6',True)
        for i in range(7):
            self.line(1037+i*74,312,1037+i*74,450,'#204355')
        for i in range(5):
            self.line(1037,312+i*34,1517,312+i*34,'#204355')
        x=1117+min(280,elapsed*6)
        self.oval(x,357+math.sin(elapsed/5)*27,15,15,'#80d5bd')
        self.text(1045,442,'Условна схема — без реални координати',14,'#7a9fb4')
        self.rect(490,499,503,230,'#112a3a')
        self.text(514,520,'МИКРОФОН / УСЛОВЕН СИГНАЛ',19,'#86b7c6',True)
        if elapsed>8:
            for i in range(39):
                bar=11+abs(math.sin(i*.7+elapsed*1.6))*72
                self.rect(518+i*11,640-bar/2,5,bar,'#69bea8')
        self.text(514,696,'Анимация; не се записва звук.',16,'#6e9caf')
        self.rect(1014,499,530,230,'#112a3a')
        self.text(1037,520,'КАМЕРА / СХЕМАТИЧЕН КАДЪР',19,'#86b7c6',True)
        if elapsed>16:
            self.rect(1142,558,264,139,'#233c4c')
            self.oval(1241,570,54,54,'#67818e')
            self.oval(1198,631,141,78,'#67818e')
        self.text(1037,699,'Няма достъп до истинска камера.',16,'#6e9caf')
        self.text(518,754,'Мобилният spyware цели незабелязано наблюдение.',25,'#c1e5df',True,width=1000)

    def debrief(self):
        self.rect(0,0,1600,900,'#0a1826')
        self.text(71,62,'ЕДНАКВА ДУМА „ЗАРАЗА“. РАЗЛИЧНИ ЦЕЛИ.',40,'white',True)
        cards=[(71,'РЕКЛАМИ И ИЗМАМИ','#b190ce',
                'Натиск да щракнеш,\nда инсталираш или да платиш.',
                'Красивият сайт и тревожният\nпрозорец не доказват надеждност.'),
               (581,'WANNACRY / РАНСЪМУЕР','#e399a6',
                'Заключва файлове\nи изисква откуп.',
                'Обещанието за ключ\nне гарантира възстановяване.'),
               (1091,'PEGASUS / SPYWARE','#83cbb9',
                'Скрито наблюдение\nна мобилно устройство.',
                'Липсата на видими ефекти\nне доказва липса на заплаха.')]
        for x,title,color,body,note in cards:
            self.rect(x,181,440,413,'#142a3d')
            self.rect(x,181,440,6,color)
            self.text(x+25,216,title,21,color,True,width=390)
            self.text(x+25,282,body,29,'#e9f2fa',True,width=386)
            self.text(x+25,439,note,22,'#8facbf',width=385)
        self.text(78,649,'Екранните изкривявания и синият екран бяха визуални ефекти.',27,'#bacdde')
        self.text(78,698,'По тях сами по себе си не се поставя диагноза за вирус.',25,'#8facbf')
        self.button(80,785,358,64,'Разследване с класа →',self.app.open_quiz,'#226555',size=23)
        self.button(463,785,269,64,'Към панела',self.app.stop,'#233f58',size=23)


class ScreenFrames:
    """Pure, bounded image transforms. No filesystem, network or Windows writes."""
    MODES = {'Разкъсване': 'tear', 'Разтичане': 'melt', 'Безкраен екран': 'tunnel'}

    def __init__(self, snapshot):
        self.original = snapshot.convert('RGB')
        # Limit per-frame work on a school laptop, including a 4K display.
        self.original.thumbnail((1600, 1000), Image.Resampling.LANCZOS)
        self.width, self.height = self.original.size
        self.tunnel_levels = []
        if self.width < 2 or self.height < 2:
            raise RuntimeError('Windows върна празно изображение на екрана.')

    def frame(self, elapsed, selection='Смесени ефекти'):
        elapsed = max(0.0, elapsed)
        phase = elapsed % 12.0
        mode = self.MODES.get(selection, ('tear', 'melt', 'tunnel')[int(elapsed/12) % 3])
        # Fade between chapters instead of flashing or inverting the whole screen.
        mix = min(1.0, phase/1.2, (12.0-phase)/1.2)
        if mix <= 0:
            return self.original.copy()
        changed = getattr(self, mode)(phase)
        return Image.blend(self.original, changed, max(0.0, mix))

    def tear(self, t):
        w, h = self.width, self.height
        result = self.original.copy()
        stripe = max(8, h//32)
        strength = min(1.0, t/3.0)
        for i, y in enumerate(range(0, h, stripe)):
            shift = int(w*.075*strength*(math.sin(t*2.7+i*1.91) + .3*math.sin(t*6+i)))
            band = self.original.crop((0, y, w, min(h, y+stripe)))
            result.paste(ImageChops.offset(band, shift, 0), (0, y))
        red, green, blue = result.split()
        shift = max(1, round(w*.003*strength))
        split = Image.merge('RGB', (ImageChops.offset(red, shift, 0), green,
                                   ImageChops.offset(blue, -shift, 0)))
        return Image.blend(result, split, .65)

    def melt(self, t):
        w, h = self.width, self.height
        result = self.original.copy()
        stripe = max(5, w//70)
        progress = min(.8, t/12.0)
        for i, x in enumerate(range(0, w, stripe)):
            right = min(w, x+stripe)
            speed = .18 + .82*(.5+.5*math.sin(i*1.714+math.sin(i*.31)))
            offset = min(h-1, int(h*progress*speed))
            if offset:
                result.paste(self.original.crop((x, 0, right, h-offset)), (x, offset))
                streak = self.original.crop((x, 0, right, 1)).resize(
                    (right-x, offset), Image.Resampling.NEAREST)
                result.paste(streak, (x, 0))
        return result

    def tunnel(self, t):
        w, h = self.width, self.height
        result = self.original.copy()
        layers = min(22, 1+int(t*2.5))
        if not self.tunnel_levels:
            working = self.original
            for level in range(22):
                scale = .86**(level+1)
                size = max(2, int(w*scale)), max(2, int(h*scale))
                working = working.resize(size, Image.Resampling.BILINEAR)
                self.tunnel_levels.append(working)
        for level in range(layers):
            inset = self.tunnel_levels[level]
            iw, ih = inset.size
            dx = int(math.sin(t*.7+level*.08)*(w-iw)*.16)
            dy = int(math.cos(t*.55+level*.08)*(h-ih)*.13)
            result.paste(inset, ((w-iw)//2+dx, (h-ih)//2+dy))
        return result

    def close(self):
        self.original.close()
        for inset in self.tunnel_levels:
            inset.close()
        self.tunnel_levels.clear()


class DesktopOverlay:
    """Animate the actual desktop snapshot in our own ordinary, closable window.

    Capture once after the panel has disappeared. No screenshot is saved, no
    live input is sent to the hidden desktop, and no other window is modified.
    """
    def __init__(self, app):
        self.app = app
        self.mode = 'glitch'
        self.born = app.clock
        self.elapsed = 0.0
        self.ready = False
        self.closed = False
        self.frames = self.photo = None
        self.image_item = self.badge = None
        self.capture_after = time.monotonic() + .3
        self.next_frame = 0.0
        self.win = tk.Toplevel(app.root)
        try:
            self.win.withdraw()
            self.win.title('Дигитални детективи — екранен ефект')
            sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
            self.win.geometry(f'{min(1400,sw-60)}x{min(850,sh-90)}+25+25')
            self.win.configure(bg='#101015')
            self.win.attributes('-fullscreen', app.fullscreen.get())
            self.win.attributes('-topmost', True)
            self.win.protocol('WM_DELETE_WINDOW', app.stop)
            self.canvas = tk.Canvas(self.win, bg='#101015', highlightthickness=0)
            self.canvas.pack(fill='both', expand=True)
        except Exception:
            self.close()
            raise

    def tick(self):
        if self.closed or self.app.paused:
            return
        now = time.monotonic()
        if not self.ready:
            if now < self.capture_after:
                return
            # The root and overlay are both withdrawn at this point.
            if ImageGrab is None:
                raise RuntimeError('Липсва Pillow. Изпълнете: py -m pip install pillow')
            try:
                snapshot = ImageGrab.grab(all_screens=False, include_layered_windows=True)
            except Exception as exc:
                raise RuntimeError('Не мога да заснема основния монитор за ефекта. '
                                   'Проверете дали работите в отворена Windows сесия. '
                                   'Подробностите са в журнала.') from exc
            try:
                self.frames = ScreenFrames(snapshot)
            finally:
                snapshot.close()
            LOG.info('Screen effect initialized; working image=%sx%s; image held in RAM only',
                     self.frames.width, self.frames.height)
            # Prepaint before showing, to avoid briefly covering the desktop in black.
            self.win.update_idletasks()
            self.render()
            self.ready = True
            self.win.deiconify()
            self.win.lift()
            self.canvas.focus_set()
        elif now >= self.next_frame:
            self.elapsed = max(0.0, self.app.clock-self.born)
            self.render()
        # Rendering is capped rather than catching up with a burst of frames.

    def render(self):
        started = time.monotonic()
        frame = self.frames.frame(self.elapsed, self.app.visual_mode.get())
        try:
            size = (self.canvas.winfo_width(), self.canvas.winfo_height())
            if min(size) < 10:
                if self.app.fullscreen.get():
                    size = (self.win.winfo_screenwidth(), self.win.winfo_screenheight())
                else:
                    size = (min(1400,self.win.winfo_screenwidth()-60),
                            min(850,self.win.winfo_screenheight()-90))
            if frame.size != size:
                resized = frame.resize(size, Image.Resampling.BILINEAR)
                frame.close()
                frame = resized
            self.photo = ImageTk.PhotoImage(frame, master=self.win)
        finally:
            # PhotoImage has copied the pixels into Tcl; release the per-frame PIL
            # buffer immediately instead of waiting for garbage collection.
            frame.close()
        if self.image_item is None:
            self.image_item = self.canvas.create_image(0, 0, anchor='nw', image=self.photo)
            self.badge = self.canvas.create_text(14, 14, anchor='nw',
                text='Ctrl+Alt+P  пауза     Ctrl+Alt+Q  изход',
                font=('Segoe UI', 10, 'bold'), fill='white')
        else:
            self.canvas.itemconfigure(self.image_item, image=self.photo)
        self.next_frame = max(started + 1/12, time.monotonic() + .01)

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.win.destroy()
        except tk.TclError:
            pass
        self.photo = None
        if self.frames is not None:
            self.frames.close()
            self.frames = None


def main():
    try:
        configure_logging()
    except OSError:
        # An unavailable log folder must not prevent the emergency controls.
        pass
    enable_dpi_awareness()
    root = None
    app = None
    try:
        root = tk.Tk()
        app = Classroom(root)
        root.mainloop()
    except Exception as exc:
        LOG.exception('Application startup or main loop failed')
        if app is not None:
            try:
                app.close()
            except Exception:
                LOG.exception('Final cleanup failed')
        detail = 'Програмата не успя да стартира.\n\n' + str(exc)
        if LOG_PATH is not None:
            detail += '\n\nЖурнал: ' + str(LOG_PATH)
        if sys.platform == 'win32':
            # Works even if Tk itself failed to initialize.
            user = ctypes.WinDLL('user32')
            user.MessageBoxW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
            user.MessageBoxW.restype = ctypes.c_int
            user.MessageBoxW(None, detail, 'Дигитални детективи — грешка', 0x10)
        else:
            print(detail, file=sys.stderr)
    finally:
        if app is not None and not app.closed:
            app.close()
        if root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass
        logging.shutdown()


if __name__ == '__main__':
    main()
