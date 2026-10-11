"""Дигитални детективи 8.0 — демонстрация върху истинския Windows.

Windows 10/11 + Python 3.10+ с Win32 API, tkinter и Pillow.
Стартиране: py cyber_classroom.py
Преди първо стартиране: py -m pip install pillow
Не са нужни администраторски права.
Ctrl+Alt+P: глобална пауза / продължаване.
Ctrl+Alt+Q: спира ефектите, затваря учебния браузър и излиза.
Esc: спиране от наш активен прозорец. F6: следваща глава. F11: цял екран.
Продължителност: 10, 15 или 20 минути, без времето в пауза.

Използва реален Edge/Chrome с нов временен профил и до 4/6 локални раздела
според избрания ресурсен профил (абсолютен лимит 8).
Вграден HTTP сървър слуша САМО на 127.0.0.1, със случаен адресен префикс.
Страниците не водят към външни сайтове и не приемат пароли или плащания.
Браузърът е в отделен Windows Job; никога не се затварят процеси по име.
Организационна UserDataDir политика не се заобикаля; браузърната сцена се отказва.

Създава точно 8 учебни текстови файла в нова временна папка и отваря тази папка
в истинския File Explorer. Само създадените файлове получават суфикс .locked.
При спиране връща имената им, ако съдържанието е непроменено и няма конфликт.
Няма шифроване. Папката и прозорецът на File Explorer остават за преглед.
Графичната сцена взема еднократна снимка на избрания презентационен монитор САМО в RAM.
Разкъсва, разтича и повтаря тези пиксели в собствен прозорец върху Windows.
Снимката не се записва или изпраща; оригиналният работен плот е непокътнат.
Няма четене на лични файлове, запис на клавиши, достъп до камера/микрофон,
изключване на защита, промяна на настройки, автозареждане или реален срив.

Документация: Chromium user_data_dir.md; Microsoft RegisterHotKey,
CreateProcessW, AssignProcessToJobObject и JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
https://pillow.readthedocs.io/en/stable/reference/ImageGrab.html
https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setprocessdpiawarenesscontext
"""

import ctypes
from ctypes import wintypes
from array import array
import base64
from dataclasses import dataclass
import hashlib
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
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from classroom_core import (
    ABSOLUTE_MAX_EFFECTS, ABSOLUTE_MAX_TABS, BoundedEventBus, DEFAULT_STORY_LABEL,
    PROFILES, RateLimiter, STORY_PRESETS, ScenarioEvent, ScenarioState,
    retained_chapter_index,
)

try:
    from PIL import Image, ImageChops, ImageGrab, ImageTk
    PILLOW_ERROR = None
except ImportError as exc:
    Image = ImageChops = ImageGrab = ImageTk = None
    PILLOW_ERROR = str(exc)

try:
    import winsound
except ImportError:
    winsound = None

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
    LOG.info('Version 8.0; Python %s; platform %s; Pillow available=%s',
             sys.version.split()[0], sys.platform, Image is not None)


class SoundBank:
    """Short local WAV cues; exact-name files in ./sounds override generated audio."""
    RATE = 22_050
    CUES = {
        'browser': ((330, 520, .11, .38), (0, 0, .035, 0), (520, 720, .14, .34)),
        'uac': ((392, 392, .12, .28), (0, 0, .06, 0), (294, 294, .22, .25)),
        'installer': ((440, 560, .10, .34), (560, 700, .10, .34), (700, 880, .18, .30)),
        'tab': ((760, 920, .07, .25), (0, 0, .025, 0), (920, 760, .08, .22)),
        'notification': ((660, 660, .12, .27), (0, 0, .07, 0), (880, 880, .18, .25)),
        'advert': ((620, 940, .09, .30), (940, 1180, .10, .27), (1180, 790, .12, .22)),
        'warning': ((390, 330, .19, .34), (0, 0, .055, 0), (390, 300, .25, .31)),
        'firewall': ((330, 270, .16, .30), (0, 0, .05, 0), (440, 350, .19, .27)),
        'scanner': ((260, 880, .32, .25), (880, 430, .18, .20)),
        'taskmanager': ((520, 680, .07, .17), (0, 0, .035, 0), (680, 520, .08, .15)),
        'updater': ((330, 440, .11, .22), (440, 554, .11, .22), (554, 659, .16, .20)),
        'error': ((220, 180, .22, .36), (0, 0, .04, 0), (180, 145, .28, .34)),
        'terminal': ((520, 510, .055, .19), (0, 0, .035, 0), (620, 610, .055, .17)),
        'glitch': ((170, 760, .10, .25), (690, 130, .13, .26), (120, 510, .10, .22)),
        'files': ((520, 390, .10, .24), (420, 315, .10, .26), (330, 245, .16, .28)),
        'ransom': ((146, 122, .32, .31), (0, 0, .055, 0), (185, 139, .38, .29)),
        'crash': ((330, 92, .48, .30),),
        'reboot': ((196, 294, .16, .22), (294, 440, .17, .22), (440, 659, .24, .20)),
        'debrief': ((392, 392, .12, .23), (494, 494, .12, .23), (587, 587, .12, .23),
                    (784, 784, .28, .22)),
    }
    SCENES = {
        'browser': 'browser', 'uac': 'uac', 'installer': 'installer', 'tabs': 'tab',
        'notification': 'notification', 'advert': 'advert', 'warning': 'warning',
        'firewall': 'firewall', 'scanner': 'scanner', 'taskmanager': 'taskmanager',
        'updater': 'updater', 'error': 'error', 'errorwall': 'error',
        'terminal_chapter': 'terminal', 'glitch': 'glitch', 'files_chapter': 'files',
        'download':'browser','helper':'notification','helper_status':'notification',
        'protection_history':'warning','properties':'notification',
        'network_activity':'terminal','explorer':'files','recovery':'debrief',
        'ransom': 'ransom', 'blue': 'crash', 'reboot': 'reboot', 'debrief': 'debrief',
    }

    def __init__(self, custom_dir=None, cache_dir=None):
        self.custom_dir = Path(custom_dir) if custom_dir else Path(__file__).resolve().parent / 'sounds'
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.owns_cache = cache_dir is None
        self.closed = False

    def _ensure_cache(self):
        if self.cache_dir is None:
            self.cache_dir = Path(tempfile.mkdtemp(prefix='CyberClassroom-SOUNDS-'))
        else:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir

    def prepare(self, name):
        """Resolve a custom cue or synthesize the bundled fallback on demand."""
        if self.closed or name not in self.CUES:
            return None
        custom = self.custom_dir / f'{name}.wav'
        if custom.is_file():
            return custom
        target = self._ensure_cache() / f'{name}.wav'
        if not target.is_file():
            self._write_wave(target, self.CUES[name])
        return target

    @classmethod
    def _write_wave(cls, target, segments):
        samples = array('h')
        phase = 0.0
        for start_hz, end_hz, duration, amplitude in segments:
            count = max(1, int(cls.RATE * duration))
            fade = max(1, min(int(cls.RATE * .012), count // 3))
            for index in range(count):
                if start_hz <= 0 or amplitude <= 0:
                    samples.append(0)
                    continue
                position = index / max(1, count - 1)
                frequency = start_hz + (end_hz - start_hz) * position
                phase += math.tau * frequency / cls.RATE
                envelope = min(1.0, index / fade, (count - 1 - index) / fade)
                tone = (math.sin(phase) + .14 * math.sin(phase * 2.01)) / 1.14
                samples.append(int(max(-1.0, min(1.0, tone * amplitude * envelope)) * 32767))
        if sys.byteorder != 'little':
            samples.byteswap()
        with wave.open(str(target), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(cls.RATE)
            output.writeframes(samples.tobytes())

    def play(self, name):
        if winsound is None or self.closed:
            return False
        try:
            path = self.prepare(name)
            if path is None:
                return False
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            return True
        except (OSError, RuntimeError):
            LOG.exception('Sound cue failed: %s', name)
            return False

    def play_scene(self, scene):
        cue = self.SCENES.get(scene)
        return self.play(cue) if cue else False

    def play_system(self,alias):
        if winsound is None or self.closed:
            return False
        try:
            winsound.PlaySound(alias,winsound.SND_ALIAS|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
            return True
        except RuntimeError:
            LOG.exception('Windows system sound failed: %s',alias)
            return False

    def stop(self):
        if winsound is not None:
            try:
                winsound.PlaySound(None, 0)
            except RuntimeError:
                LOG.exception('Stopping sound playback failed')

    def close(self):
        if self.closed:
            return
        self.stop()
        self.closed = True
        if self.owns_cache and self.cache_dir is not None:
            shutil.rmtree(self.cache_dir, ignore_errors=True)


class WindowsToastNotifier:
    """Best-effort Windows Notification Center delivery through local WinRT APIs."""
    MIN_INTERVAL = 8.0

    def __init__(self):
        self.executable=(shutil.which('powershell.exe') or shutil.which('pwsh.exe')) if sys.platform=='win32' else None
        self.last_sent=-self.MIN_INTERVAL
        self.threads=[]
        self.closed=False

    @property
    def available(self):
        return bool(self.executable) and not self.closed

    @staticmethod
    def _quote(value):
        return "'"+str(value).replace("'","''")+"'"

    @classmethod
    def encoded_script(cls,title,body):
        title=cls._quote(title[:120]);body=cls._quote(body[:300])
        script=f"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.UI.Notifications.ToastTemplateType, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$nodes = $xml.GetElementsByTagName('text')
$nodes.Item(0).AppendChild($xml.CreateTextNode({title})) > $null
$nodes.Item(1).AppendChild($xml.CreateTextNode({body})) > $null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
$toast.Tag = 'cyber-classroom'
$toast.Group = 'classroom-demo'
$toast.ExpirationTime = [DateTimeOffset]::Now.AddMinutes(20)
$appIds = @('Cyber Classroom', 'Microsoft.Windows.PowerShell', 'Windows PowerShell')
foreach ($appId in $appIds) {{
    try {{
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show($toast)
        exit 0
    }} catch {{}}
}}
exit 2
"""
        return base64.b64encode(script.encode('utf-16le')).decode('ascii')

    def show(self,title,body):
        now=time.monotonic()
        if not self.available or now-self.last_sent<self.MIN_INTERVAL:
            return False
        self.last_sent=now
        encoded=self.encoded_script(title,body)
        return self._start(encoded,'delivery')

    def _start(self,encoded,operation):
        if not self.available:
            return False
        def worker():
            try:
                result=subprocess.run(
                    [self.executable,'-NoProfile','-NonInteractive','-EncodedCommand',encoded],
                    stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=7,check=False)
                if result.returncode:
                    LOG.warning('Windows toast %s was not accepted; exit code=%s',operation,result.returncode)
            except (OSError,subprocess.SubprocessError):
                LOG.exception('Windows Notification Center %s failed',operation)
        self.threads[:]=[thread for thread in self.threads if thread.is_alive()]
        thread=threading.Thread(target=worker,name='ClassroomToast',daemon=True)
        self.threads.append(thread);thread.start()
        return True

    def clear(self):
        """Remove only the notification group created by this application."""
        script="""
$ErrorActionPreference = 'SilentlyContinue'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$history = [Windows.UI.Notifications.ToastNotificationManager]::History
foreach ($appId in @('Cyber Classroom', 'Microsoft.Windows.PowerShell', 'Windows PowerShell')) {
    try { $history.RemoveGroup('classroom-demo', $appId) } catch {}
}
exit 0
"""
        encoded=base64.b64encode(script.encode('utf-16le')).decode('ascii')
        return self._start(encoded,'cleanup')

    def close(self):
        self.closed=True
        deadline=time.monotonic()+.35
        for thread in list(self.threads):
            remaining=deadline-time.monotonic()
            if remaining<=0:break
            thread.join(timeout=min(.12,remaining))
        self.threads.clear()


@dataclass(frozen=True)
class WindowsPresentationProfile:
    generation: str
    language: str
    build: int
    font: str
    rounded_corners: bool

    def text(self,bg,en):
        return bg if self.language=='bg' else en


@dataclass(frozen=True)
class MonitorTarget:
    index: int
    device: str
    monitor_rect: tuple[int,int,int,int]
    work_rect: tuple[int,int,int,int]
    primary: bool
    dpi: int=96

    @property
    def label(self):
        left,top,right,bottom=self.monitor_rect
        suffix=' • основен' if self.primary else ''
        return f'{self.index}: {self.device or "Display"} • {right-left}×{bottom-top}{suffix}'


class MonitorInfoExW(ctypes.Structure):
    _fields_=[('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),
              ('rcWork',wintypes.RECT),('dwFlags',wintypes.DWORD),
              ('szDevice',wintypes.WCHAR*32)]


def detect_windows_profile(build=None,language_id=None):
    if build is None:
        try:
            build=sys.getwindowsversion().build if sys.platform=='win32' else 0
        except AttributeError:
            build=0
    if language_id is None and sys.platform=='win32':
        try:
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.GetUserDefaultUILanguage.restype=wintypes.LANGID
            language_id=int(kernel.GetUserDefaultUILanguage())
        except (OSError,AttributeError):
            language_id=0
    language='bg' if int(language_id or 0)&0x3ff==0x02 else 'en'
    windows11=int(build or 0)>=22000
    return WindowsPresentationProfile('windows11' if windows11 else 'windows10',language,
                                      int(build or 0),'Segoe UI Variable' if windows11 else 'Segoe UI',
                                      windows11)


def enumerate_monitors():
    """Return stable monitor/work-area data without changing display settings."""
    if sys.platform!='win32':
        return [MonitorTarget(1,'Preview',(0,0,1280,720),(0,0,1280,680),True,96)]
    try:
        user=ctypes.WinDLL('user32',use_last_error=True)
        callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HANDLE,wintypes.HDC,
                                         ctypes.POINTER(wintypes.RECT),wintypes.LPARAM)
        user.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MonitorInfoExW)]
        user.GetMonitorInfoW.restype=wintypes.BOOL
        user.EnumDisplayMonitors.argtypes=[wintypes.HDC,ctypes.POINTER(wintypes.RECT),callback_type,wintypes.LPARAM]
        user.EnumDisplayMonitors.restype=wintypes.BOOL
        found=[]
        def visit(handle,_dc,_rect,_data):
            info=MonitorInfoExW();info.cbSize=ctypes.sizeof(info)
            if not user.GetMonitorInfoW(handle,ctypes.byref(info)):
                return True
            dpi=96
            try:
                shcore=ctypes.WinDLL('shcore',use_last_error=True)
                xdpi=wintypes.UINT();ydpi=wintypes.UINT()
                shcore.GetDpiForMonitor.argtypes=[wintypes.HANDLE,ctypes.c_int,
                                                  ctypes.POINTER(wintypes.UINT),ctypes.POINTER(wintypes.UINT)]
                shcore.GetDpiForMonitor.restype=ctypes.HRESULT
                if shcore.GetDpiForMonitor(handle,0,ctypes.byref(xdpi),ctypes.byref(ydpi))==0:
                    dpi=int(xdpi.value)
            except (OSError,AttributeError):
                pass
            rect=lambda value:(value.left,value.top,value.right,value.bottom)
            found.append((str(info.szDevice),rect(info.rcMonitor),rect(info.rcWork),bool(info.dwFlags&1),dpi))
            return True
        callback=callback_type(visit)
        if not user.EnumDisplayMonitors(None,None,callback,0):
            raise ctypes.WinError(ctypes.get_last_error())
        found.sort(key=lambda item:(not item[3],item[1][0],item[1][1]))
        return [MonitorTarget(index,*item) for index,item in enumerate(found,1)]
    except (OSError,AttributeError):
        LOG.exception('Monitor enumeration failed; using the primary-screen fallback')
        try:
            user=ctypes.WinDLL('user32',use_last_error=True)
            width,height=user.GetSystemMetrics(0),user.GetSystemMetrics(1)
        except (OSError,AttributeError):
            width,height=1280,720
        return [MonitorTarget(1,'Primary',(0,0,width,height),(0,0,width,height),True,96)]


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
        self.thread.join(timeout=.25)


TERMINAL_LINES = [
    'Microsoft Windows [Version 10.0.22631.0000]',
    '(c) Microsoft Corporation. All rights reserved.',
    '', r'C:\Users\Student\Downloads> CaveDepths_Setup.exe /install',
    '[bootstrap] loading package ... OK',
    '[signature] publisher verification ... UNKNOWN',
    '[consent] elevation request accepted',
    '[runtime] Block Runtime Host registered',
    '[firewall] outbound permission request ... BLOCKED',
    '[ModUpdateHelper] worker process ready',
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

# Compatibility aliases for integrations that inspect the standard story.
# Runtime uses the selected preset directly; presets are not time-scaled clones.
DEFAULT_STORY = STORY_PRESETS[DEFAULT_STORY_LABEL]
TIMELINE = [(beat.at, beat.scene) for beat in DEFAULT_STORY.beats]
MASTER_DURATION = DEFAULT_STORY.duration
CHAPTERS = list(DEFAULT_STORY.chapters)
class NativeWindowClass(ctypes.Structure):
    _fields_ = [('style',wintypes.UINT),('wndproc',ctypes.c_void_p),
                ('class_extra',ctypes.c_int),('window_extra',ctypes.c_int),
                ('instance',wintypes.HINSTANCE),('icon',wintypes.HICON),
                ('cursor',wintypes.HANDLE),('background',wintypes.HBRUSH),
                ('menu_name',wintypes.LPCWSTR),('class_name',wintypes.LPCWSTR)]


class InitCommonControls(ctypes.Structure):
    _fields_ = [('size',wintypes.DWORD),('classes',wintypes.DWORD)]


class Guid(ctypes.Structure):
    _fields_=[('data1',wintypes.DWORD),('data2',wintypes.WORD),('data3',wintypes.WORD),
              ('data4',ctypes.c_ubyte*8)]


class NotifyIconDataW(ctypes.Structure):
    _fields_=[('cbSize',wintypes.DWORD),('hWnd',wintypes.HWND),('uID',wintypes.UINT),
              ('uFlags',wintypes.UINT),('uCallbackMessage',wintypes.UINT),
              ('hIcon',wintypes.HICON),('szTip',wintypes.WCHAR*128),
              ('dwState',wintypes.DWORD),('dwStateMask',wintypes.DWORD),
              ('szInfo',wintypes.WCHAR*256),('uVersion',wintypes.UINT),
              ('szInfoTitle',wintypes.WCHAR*64),('dwInfoFlags',wintypes.DWORD),
              ('guidItem',Guid),('hBalloonIcon',wintypes.HICON)]


class OwnedTrayIcon:
    """One process-owned notification-area icon with bounded, reversible UI."""
    WM_CLOSE=0x0010;WM_DESTROY=0x0002;WM_APP_TRAY=0x8051
    WM_LBUTTONUP=0x0202;WM_LBUTTONDBLCLK=0x0203;WM_RBUTTONUP=0x0205
    NIM_ADD=0;NIM_DELETE=2;NIF_MESSAGE=1;NIF_ICON=2;NIF_TIP=4

    def __init__(self,events,tooltip='Block Runtime Host'):
        self.events=events;self.tooltip=tooltip[:127]
        self.closed=False;self.hwnd=None;self.nid=None;self.callback=None
        self.ready=threading.Event();self.stopping=threading.Event()
        self.thread=threading.Thread(target=self._run,name='ClassroomTray',daemon=True)
        self.thread.start()

    def _run(self):
        if sys.platform!='win32':
            self.closed=True;self.ready.set();return
        user=ctypes.WinDLL('user32',use_last_error=True)
        shell=ctypes.WinDLL('shell32',use_last_error=True)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        callback_type=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,wintypes.HWND,wintypes.UINT,
                                         wintypes.WPARAM,wintypes.LPARAM)
        user.RegisterClassW.argtypes=[ctypes.POINTER(NativeWindowClass)]
        user.RegisterClassW.restype=wintypes.ATOM
        user.CreateWindowExW.argtypes=[wintypes.DWORD,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.DWORD,
                                      ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.HWND,
                                      wintypes.HMENU,wintypes.HINSTANCE,ctypes.c_void_p]
        user.CreateWindowExW.restype=wintypes.HWND
        user.DefWindowProcW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
        user.DefWindowProcW.restype=ctypes.c_ssize_t
        user.LoadIconW.restype=wintypes.HICON
        user.CreatePopupMenu.restype=wintypes.HMENU
        user.TrackPopupMenu.restype=wintypes.UINT
        kernel.GetModuleHandleW.argtypes=[wintypes.LPCWSTR]
        kernel.GetModuleHandleW.restype=wintypes.HMODULE
        shell.Shell_NotifyIconW.argtypes=[wintypes.DWORD,ctypes.POINTER(NotifyIconDataW)]
        shell.Shell_NotifyIconW.restype=wintypes.BOOL
        class_name='CyberClassroomTray-'+secrets.token_hex(4)

        def show_menu(hwnd):
            menu=user.CreatePopupMenu()
            if not menu:return
            try:
                user.AppendMenuW(menu,0,1,'Open status')
                user.AppendMenuW(menu,0,2,'Exit helper')
                point=wintypes.POINT();user.GetCursorPos(ctypes.byref(point))
                user.SetForegroundWindow(hwnd)
                command=user.TrackPopupMenu(menu,0x0100|0x0002,point.x,point.y,0,hwnd,None)
                if command==1:self.events.post('tray_open',coalesce='tray_open')
                elif command==2:self.events.post('tray_exit',priority=True)
            finally:
                user.DestroyMenu(menu)

        def window_proc(hwnd,message,wparam,lparam):
            if message==self.WM_APP_TRAY:
                event=int(lparam)&0xffff
                if event in (self.WM_LBUTTONUP,self.WM_LBUTTONDBLCLK):
                    self.events.post('tray_open',coalesce='tray_open')
                elif event==self.WM_RBUTTONUP:
                    show_menu(hwnd)
                return 0
            if message==self.WM_CLOSE:
                user.DestroyWindow(hwnd);return 0
            if message==self.WM_DESTROY:
                user.PostQuitMessage(0);return 0
            return user.DefWindowProcW(hwnd,message,wparam,lparam)

        self.callback=callback_type(window_proc)
        instance=kernel.GetModuleHandleW(None)
        wc=NativeWindowClass();wc.wndproc=ctypes.cast(self.callback,ctypes.c_void_p).value
        wc.instance=instance;wc.icon=user.LoadIconW(None,ctypes.c_void_p(32516))
        wc.cursor=user.LoadCursorW(None,ctypes.c_void_p(32512));wc.class_name=class_name
        try:
            if not user.RegisterClassW(ctypes.byref(wc)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.hwnd=user.CreateWindowExW(0,class_name,'',0,0,0,0,0,
                                            wintypes.HWND(-3),None,instance,None)
            if not self.hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            self.nid=NotifyIconDataW();self.nid.cbSize=ctypes.sizeof(self.nid)
            self.nid.hWnd=self.hwnd;self.nid.uID=1
            self.nid.uFlags=self.NIF_MESSAGE|self.NIF_ICON|self.NIF_TIP
            self.nid.uCallbackMessage=self.WM_APP_TRAY
            self.nid.hIcon=user.LoadIconW(None,ctypes.c_void_p(32516))
            self.nid.szTip=self.tooltip
            if not shell.Shell_NotifyIconW(self.NIM_ADD,ctypes.byref(self.nid)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.ready.set()
            if self.stopping.is_set():user.PostMessageW(self.hwnd,self.WM_CLOSE,0,0)
            msg=wintypes.MSG()
            while user.GetMessageW(ctypes.byref(msg),None,0,0)>0:
                user.TranslateMessage(ctypes.byref(msg));user.DispatchMessageW(ctypes.byref(msg))
        except Exception as exc:
            LOG.error('Tray icon failed: %s',exc)
            self.events.post('tray_error',str(exc),coalesce='tray_error')
            self.ready.set()
        finally:
            if self.nid is not None:
                shell.Shell_NotifyIconW(self.NIM_DELETE,ctypes.byref(self.nid))
            self.hwnd=None;self.closed=True

    def close(self):
        if self.closed:return
        self.stopping.set();self.ready.wait(timeout=.15)
        if self.hwnd:
            try:ctypes.WinDLL('user32',use_last_error=True).PostMessageW(self.hwnd,self.WM_CLOSE,0,0)
            except OSError:pass
        self.thread.join(timeout=.35)


class NativeEffect:
    """A real Win32 top-level window with standard Windows child controls.

    Every window owns a dedicated Win32 message-loop thread.  Python 3.13 cannot
    safely enter a ctypes WNDPROC from inside Tk's GIL-releasing mainloop on the
    same thread, so button actions cross back through Classroom.events instead.
    """
    CLASS_NAME='CyberClassroomNativeEffectV2'
    registry={}
    registered=False
    wndproc_callback=None
    user32=None
    gdi32=None
    kernel32=None
    comctl32=None

    WM_CLOSE=0x0010
    WM_KEYDOWN=0x0100
    WM_COMMAND=0x0111
    WM_ERASEBKGND=0x0014
    WM_SETFONT=0x0030
    WM_NCDESTROY=0x0082
    WM_CTLCOLOREDIT=0x0133
    WM_CTLCOLORSTATIC=0x0138
    WM_SETICON=0x0080
    WM_USER=0x0400
    WM_APP_COMMAND=0x8001
    WM_APP_FLUSH=0x8002
    PBM_SETPOS=WM_USER+2
    PBM_SETRANGE32=WM_USER+6
    EM_SETSEL=0x00B1
    EM_SCROLLCARET=0x00B7
    BM_CLICK=0x00F5

    WS_CHILD=0x40000000
    WS_VISIBLE=0x10000000
    WS_VSCROLL=0x00200000
    WS_BORDER=0x00800000
    WS_CAPTION=0x00C00000
    WS_SYSMENU=0x00080000
    WS_MINIMIZEBOX=0x00020000
    WS_MAXIMIZEBOX=0x00010000
    WS_THICKFRAME=0x00040000
    WS_POPUP=0x80000000
    WS_EX_TOPMOST=0x00000008
    WS_EX_APPWINDOW=0x00040000
    WS_EX_TOOLWINDOW=0x00000080
    WS_EX_NOACTIVATE=0x08000000
    ES_MULTILINE=0x0004
    ES_AUTOVSCROLL=0x0040
    ES_READONLY=0x0800
    SS_NOPREFIX=0x0080

    @classmethod
    def _key(cls,handle):
        return int(handle or 0)

    @classmethod
    def ensure_registered(cls):
        if cls.registered:
            return
        if sys.platform!='win32':
            raise RuntimeError('Native Win32 прозорците изискват Windows 10/11.')
        cls.user32=ctypes.WinDLL('user32',use_last_error=True)
        cls.gdi32=ctypes.WinDLL('gdi32',use_last_error=True)
        cls.kernel32=ctypes.WinDLL('kernel32',use_last_error=True)
        cls.comctl32=ctypes.WinDLL('comctl32',use_last_error=True)
        u,g,k,c=cls.user32,cls.gdi32,cls.kernel32,cls.comctl32
        callback_type=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,wintypes.HWND,wintypes.UINT,
                                         wintypes.WPARAM,wintypes.LPARAM)

        def dispatch(hwnd,message,wparam,lparam):
            effect=cls.registry.get(cls._key(hwnd))
            if effect is not None:
                try:
                    handled,result=effect.handle_message(message,wparam,lparam)
                    if handled:
                        return result
                except Exception as exc:
                    LOG.exception('Native window callback failed')
                    effect._emit('effect_error',exc,priority=True)
            return u.DefWindowProcW(hwnd,message,wparam,lparam)

        cls.wndproc_callback=callback_type(dispatch)
        signatures={
            'RegisterClassW':([ctypes.POINTER(NativeWindowClass)],wintypes.ATOM),
            'CreateWindowExW':([wintypes.DWORD,wintypes.LPCWSTR,wintypes.LPCWSTR,wintypes.DWORD,
                                ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.HWND,
                                wintypes.HMENU,wintypes.HINSTANCE,ctypes.c_void_p],wintypes.HWND),
            'DefWindowProcW':([wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM],ctypes.c_ssize_t),
            'DestroyWindow':([wintypes.HWND],wintypes.BOOL),
            'IsWindow':([wintypes.HWND],wintypes.BOOL),
            'ShowWindow':([wintypes.HWND,ctypes.c_int],wintypes.BOOL),
            'EnableWindow':([wintypes.HWND,wintypes.BOOL],wintypes.BOOL),
            'SetWindowTextW':([wintypes.HWND,wintypes.LPCWSTR],wintypes.BOOL),
            'SendMessageW':([wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM],ctypes.c_ssize_t),
            'PostMessageW':([wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM],wintypes.BOOL),
            'SetWindowPos':([wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,
                             ctypes.c_int,ctypes.c_int,wintypes.UINT],wintypes.BOOL),
            'GetSystemMetrics':([ctypes.c_int],ctypes.c_int),
            'SystemParametersInfoW':([wintypes.UINT,wintypes.UINT,ctypes.c_void_p,wintypes.UINT],wintypes.BOOL),
            'AdjustWindowRectEx':([ctypes.POINTER(wintypes.RECT),wintypes.DWORD,wintypes.BOOL,
                                   wintypes.DWORD],wintypes.BOOL),
            'GetClientRect':([wintypes.HWND,ctypes.POINTER(wintypes.RECT)],wintypes.BOOL),
            'FillRect':([wintypes.HDC,ctypes.POINTER(wintypes.RECT),wintypes.HBRUSH],ctypes.c_int),
            'LoadIconW':([wintypes.HINSTANCE,ctypes.c_void_p],wintypes.HICON),
            'LoadCursorW':([wintypes.HINSTANCE,ctypes.c_void_p],wintypes.HANDLE),
            'GetMessageW':([ctypes.POINTER(wintypes.MSG),wintypes.HWND,wintypes.UINT,wintypes.UINT],ctypes.c_int),
            'TranslateMessage':([ctypes.POINTER(wintypes.MSG)],wintypes.BOOL),
            'DispatchMessageW':([ctypes.POINTER(wintypes.MSG)],ctypes.c_ssize_t),
            'PostQuitMessage':([ctypes.c_int],None),
        }
        for name,(args,result) in signatures.items():
            fn=getattr(u,name); fn.argtypes=args; fn.restype=result
        if hasattr(u,'GetDpiForSystem'):
            u.GetDpiForSystem.argtypes=[]; u.GetDpiForSystem.restype=wintypes.UINT
        k.GetModuleHandleW.argtypes=[wintypes.LPCWSTR]; k.GetModuleHandleW.restype=wintypes.HMODULE
        g.CreateSolidBrush.argtypes=[wintypes.COLORREF]; g.CreateSolidBrush.restype=wintypes.HBRUSH
        g.DeleteObject.argtypes=[wintypes.HGDIOBJ]; g.DeleteObject.restype=wintypes.BOOL
        g.SetTextColor.argtypes=[wintypes.HDC,wintypes.COLORREF]; g.SetTextColor.restype=wintypes.COLORREF
        g.SetBkColor.argtypes=[wintypes.HDC,wintypes.COLORREF]; g.SetBkColor.restype=wintypes.COLORREF
        g.SetBkMode.argtypes=[wintypes.HDC,ctypes.c_int]; g.SetBkMode.restype=ctypes.c_int
        g.CreateFontW.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,
                                wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,
                                wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,
                                wintypes.LPCWSTR]
        g.CreateFontW.restype=wintypes.HFONT
        controls=InitCommonControls(ctypes.sizeof(InitCommonControls),0x00000020)
        c.InitCommonControlsEx.argtypes=[ctypes.POINTER(InitCommonControls)]
        c.InitCommonControlsEx.restype=wintypes.BOOL
        c.InitCommonControlsEx(ctypes.byref(controls))
        instance=k.GetModuleHandleW(None)
        window_class=NativeWindowClass()
        window_class.wndproc=ctypes.cast(cls.wndproc_callback,ctypes.c_void_p).value
        window_class.instance=instance
        window_class.icon=u.LoadIconW(None,ctypes.c_void_p(32512))
        window_class.cursor=u.LoadCursorW(None,ctypes.c_void_p(32512))
        window_class.background=ctypes.c_void_p(6)  # COLOR_WINDOW + 1
        window_class.class_name=cls.CLASS_NAME
        if not u.RegisterClassW(ctypes.byref(window_class)):
            error=ctypes.get_last_error()
            if error!=1410:  # ERROR_CLASS_ALREADY_EXISTS
                raise ctypes.WinError(error)
        cls.registered=True

    @staticmethod
    def color(value):
        value=value.lstrip('#')
        if len(value)==3:
            value=''.join(character*2 for character in value)
        if len(value)!=6:
            raise ValueError('Win32 color must use #RGB or #RRGGBB')
        red,green,blue=(int(value[i:i+2],16) for i in (0,2,4))
        return red|(green<<8)|(blue<<16)

    def __init__(self,app,title,width,height,bg='#f3f3f3',position='random',
                 role='app',resizable=False,topmost=None):
        self.ensure_registered()
        self.app=app
        self.monitor=getattr(app,'presentation_monitor',None)
        self.born=app.clock
        self.closed=False
        self.closing=False
        self.controls_ready=False
        self.started_wall=time.monotonic()
        self.update_view=lambda elapsed: None
        self.limit=None
        self.callbacks={}
        self.next_control_id=100
        self.fonts={}
        self.brushes={}
        self.control_colors={}
        self.background=self.color(bg)
        self.background_brush=None
        self.hwnd=None
        self.commands=queue.Queue(maxsize=32)
        self.pending_updates={}
        self.update_lock=threading.Lock()
        self.flush_posted=False
        self.ready=threading.Event()
        self.init_error=None
        self.creation=(title,width,height,position,role,resizable,topmost)
        self.thread=threading.Thread(target=self._thread_main,
            name='NativeEffect-'+secrets.token_hex(3),daemon=True)
        self.thread.start()

    def _thread_main(self):
        try:
            self._create_window(*self.creation)
        except Exception as exc:
            self.init_error=exc
            self.closed=True
            self._release_resources()
            self.ready.set()
            self._emit('effect_error',exc,priority=True)
            return
        self.ready.set()
        if self.closing:
            if self.hwnd and self.user32.IsWindow(self.hwnd):
                self.user32.DestroyWindow(self.hwnd)
            return
        # Builders queued by Tk while CreateWindowExW was running execute here in
        # one owner-thread batch; Tk never waits for native initialization.
        self._run_commands()
        msg=wintypes.MSG()
        try:
            while True:
                result=self.user32.GetMessageW(ctypes.byref(msg),None,0,0)
                if result<=0:
                    if result<0:
                        error=ctypes.WinError(ctypes.get_last_error())
                        LOG.error('Native Win32 message loop failed',exc_info=(type(error),error,error.__traceback__))
                    break
                if msg.message==self.WM_KEYDOWN:
                    action={0x1B:'stop',0x75:'next',0x7A:'fullscreen'}.get(int(msg.wParam))
                    if action:
                        self._emit('native_key',action,priority=action=='stop',
                                   coalesce=None if action=='stop' else action)
                        continue
                self.user32.TranslateMessage(ctypes.byref(msg))
                self.user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            hwnd=self.hwnd
            if hwnd and self.user32.IsWindow(hwnd):
                self.user32.DestroyWindow(hwnd)
            self.registry.pop(self._key(hwnd),None)
            self.hwnd=None
            self.closed=True
            self.closing=True
            self._release_resources()

    def _create_window(self,title,width,height,position,role,resizable,topmost):
        self.background_brush=self.gdi32.CreateSolidBrush(self.background)
        if not self.background_brush:
            raise ctypes.WinError(ctypes.get_last_error())
        target=self.monitor
        if target is not None:
            left,top,right,bottom=target.work_rect
            self.dpi=target.dpi
        else:
            sw,sh=self.user32.GetSystemMetrics(0),self.user32.GetSystemMetrics(1)
            work=wintypes.RECT(0,0,sw,sh)
            self.user32.SystemParametersInfoW(0x0030,0,ctypes.byref(work),0)  # SPI_GETWORKAREA
            left,top,right,bottom=work.left,work.top,work.right,work.bottom
            self.dpi=self.user32.GetDpiForSystem() if hasattr(self.user32,'GetDpiForSystem') else 96
        desired_scale=max(1.0,self.dpi/96)
        self.scale=min(desired_scale,(right-left-40)/width,(bottom-top-70)/height)
        self.width=round(width*self.scale)
        self.height=round(height*self.scale)
        if role=='toast':
            style=self.WS_POPUP
            exstyle=self.WS_EX_TOOLWINDOW|self.WS_EX_NOACTIVATE|self.WS_EX_TOPMOST
        else:
            style=self.WS_CAPTION|self.WS_SYSMENU
            if role=='app':
                style|=self.WS_MINIMIZEBOX
            if resizable:
                style|=self.WS_THICKFRAME|self.WS_MAXIMIZEBOX
            exstyle=self.WS_EX_APPWINDOW if role=='app' else self.WS_EX_TOOLWINDOW
            if topmost is True or (topmost is None and role=='dialog'):
                exstyle|=self.WS_EX_TOPMOST
        self.role=role
        self.topmost=bool(exstyle&self.WS_EX_TOPMOST)
        rect=wintypes.RECT(0,0,self.width,self.height)
        if not self.user32.AdjustWindowRectEx(ctypes.byref(rect),style,False,exstyle):
            self._release_resources()
            raise ctypes.WinError(ctypes.get_last_error())
        outer_width,outer_height=rect.right-rect.left,rect.bottom-rect.top
        if position=='center':
            x,y=left+(right-left-outer_width)//2,max(top+8,top+(bottom-top-outer_height)//2)
        elif position=='toast':
            toast_slot=sum(getattr(item,'role',None)=='toast' and not item.closed
                           for item in getattr(self.app,'effects',[]))
            x=right-outer_width-16
            y=max(top+16,bottom-outer_height-16-toast_slot*(outer_height+10))
        else:
            x=self.app.rng.randint(left+12,max(left+12,right-outer_width-18))
            y=self.app.rng.randint(top+16,max(top+16,bottom-outer_height-24))
        instance=self.kernel32.GetModuleHandleW(None)
        self.hwnd=self.user32.CreateWindowExW(exstyle,self.CLASS_NAME,title,style,x,y,
            outer_width,outer_height,None,None,instance,None)
        if not self.hwnd:
            self._release_resources()
            raise ctypes.WinError(ctypes.get_last_error())
        self.registry[self._key(self.hwnd)]=self
        profile=getattr(self.app,'windows_profile',None)
        if getattr(profile,'rounded_corners',False):
            try:
                dwm=ctypes.WinDLL('dwmapi',use_last_error=True)
                preference=ctypes.c_int(2)  # DWMWCP_ROUND
                dwm.DwmSetWindowAttribute(self.hwnd,33,ctypes.byref(preference),ctypes.sizeof(preference))
            except (OSError,AttributeError):
                pass

    def _invoke(self,action,timeout=.75):
        if threading.current_thread() is self.thread:
            return action()
        if not self.ready.wait(timeout=min(timeout,.5)):
            raise RuntimeError('Native Win32 прозорецът не отговори при стартиране.')
        if self.init_error is not None:
            raise self.init_error
        if self.closed or self.closing or not self.hwnd:
            raise RuntimeError('Native Win32 прозорецът вече е затворен.')
        completed=threading.Event()
        result={}
        try:
            self.commands.put_nowait((action,completed,result))
        except queue.Full as exc:
            raise RuntimeError('Native Win32 командната опашка е запълнена.') from exc
        if not self.user32.PostMessageW(self.hwnd,self.WM_APP_COMMAND,0,0):
            raise ctypes.WinError(ctypes.get_last_error())
        if not completed.wait(timeout):
            raise RuntimeError('Native Win32 прозорецът не отговори навреме.')
        if 'error' in result:
            raise result['error']
        return result.get('value')

    def batch(self,builder):
        """Synchronous acceptance-test helper; production uses build_async."""
        return self._invoke(lambda:builder(self))

    def build_async(self,builder,after=None):
        """Queue one nonblocking owner-thread control batch from the Tk controller."""
        def action():
            builder(self)
            self.controls_ready=True
            if after is not None:
                after()
        return self._post_command(action)

    def _post_command(self,action):
        if self.closed or self.closing:
            return False
        try:
            self.commands.put_nowait((action,None,None))
        except queue.Full:
            return False
        if self.hwnd:
            return bool(self.user32.PostMessageW(self.hwnd,self.WM_APP_COMMAND,0,0))
        return True

    def _emit(self,action,payload=None,priority=False,coalesce=None):
        events=getattr(self.app,'events',None)
        if events is None:
            return False
        if hasattr(events,'post'):
            return events.post(action,payload,priority=priority,coalesce=coalesce)
        try:
            events.put_nowait((action,payload))
            return True
        except queue.Full:
            return False

    def _run_commands(self):
        while True:
            try:
                action,completed,result=self.commands.get_nowait()
            except queue.Empty:
                return
            try:
                value=action()
                if result is not None:
                    result['value']=value
            except Exception as exc:
                if result is not None:
                    result['error']=exc
                else:
                    self._emit('effect_error',exc,priority=True)
            finally:
                if completed is not None:
                    completed.set()

    def _post_update(self,key,action):
        if self.closed or self.closing or not self.hwnd:
            return False
        should_post=False
        with self.update_lock:
            self.pending_updates[key]=action
            if not self.flush_posted:
                self.flush_posted=True
                should_post=True
        if should_post and not self.user32.PostMessageW(self.hwnd,self.WM_APP_FLUSH,0,0):
            with self.update_lock:
                self.flush_posted=False
            return False
        return True

    def _flush_updates(self):
        with self.update_lock:
            updates=list(self.pending_updates.values())
            self.pending_updates.clear()
            self.flush_posted=False
        for action in updates[:32]:
            action()

    def _release_resources(self):
        self.callbacks.clear()
        self.control_colors.clear()
        for font in self.fonts.values():
            self.gdi32.DeleteObject(font)
        self.fonts.clear()
        for brush in self.brushes.values():
            self.gdi32.DeleteObject(brush)
        self.brushes.clear()
        if getattr(self,'background_brush',None):
            self.gdi32.DeleteObject(self.background_brush)
            self.background_brush=None

    def _font(self,size=11,bold=False,face='Segoe UI'):
        key=(size,bold,face)
        if key not in self.fonts:
            height=-max(8,round(size*96*self.scale/72))
            font=self.gdi32.CreateFontW(height,0,0,0,700 if bold else 400,0,0,0,1,
                                        0,0,5,0,face)
            if not font:
                raise ctypes.WinError(ctypes.get_last_error())
            self.fonts[key]=font
        return self.fonts[key]

    def _child(self,class_name,text,style,x,y,width,height,control_id=0,
               size=11,bold=False,face='Segoe UI'):
        instance=self.kernel32.GetModuleHandleW(None)
        x,y,width,height=(round(value*self.scale) for value in (x,y,width,height))
        handle=self.user32.CreateWindowExW(0,class_name,text,self.WS_CHILD|self.WS_VISIBLE|style,
            x,y,width,height,self.hwnd,ctypes.c_void_p(control_id) if control_id else None,
            instance,None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.user32.SendMessageW(handle,self.WM_SETFONT,self._font(size,bold,face),1)
        return handle

    def _color_control(self,handle,fg,bg):
        foreground=self.color(fg)
        background=self.color(bg)
        brush=self.brushes.get(background)
        if brush is None:
            brush=self.gdi32.CreateSolidBrush(background)
            if not brush:
                raise ctypes.WinError(ctypes.get_last_error())
            self.brushes[background]=brush
        self.control_colors[self._key(handle)]=(foreground,background,brush)

    def add_label(self,text,x,y,width,height,size=11,bold=False,fg='#202020',bg=None,face='Segoe UI'):
        return self._invoke(lambda:self._add_label(text,x,y,width,height,size,bold,fg,bg,face))

    def _add_label(self,text,x,y,width,height,size,bold,fg,bg,face):
        handle=self._child('STATIC',text,self.SS_NOPREFIX,x,y,width,height,size=size,bold=bold,face=face)
        self._color_control(handle,fg,bg or self._hex_background())
        return handle

    def add_button(self,text,x,y,width,height,callback,default=False):
        return self._invoke(lambda:self._add_button(text,x,y,width,height,callback,default))

    def _add_button(self,text,x,y,width,height,callback,default):
        control_id=self.next_control_id; self.next_control_id+=1
        handle=self._child('BUTTON',text,1 if default else 0,x,y,width,height,
                           control_id=control_id,size=10)
        self.callbacks[control_id]=callback
        return handle

    def add_progress(self,x,y,width,height):
        return self._invoke(lambda:self._add_progress(x,y,width,height))

    def _add_progress(self,x,y,width,height):
        handle=self._child('msctls_progress32','',0,x,y,width,height)
        self.user32.SendMessageW(handle,self.PBM_SETRANGE32,0,100)
        return handle

    def add_edit(self,text,x,y,width,height,size=10,fg='#d6d6d6',bg='#0c0c0c'):
        return self._invoke(lambda:self._add_edit(text,x,y,width,height,size,fg,bg))

    def _add_edit(self,text,x,y,width,height,size,fg,bg):
        style=self.WS_VSCROLL|self.WS_BORDER|self.ES_MULTILINE|self.ES_AUTOVSCROLL|self.ES_READONLY
        handle=self._child('EDIT',text,style,x,y,width,height,size=size,face='Consolas')
        self._color_control(handle,fg,bg)
        return handle

    def _hex_background(self):
        red=self.background&0xff; green=(self.background>>8)&0xff; blue=(self.background>>16)&0xff
        return f'#{red:02x}{green:02x}{blue:02x}'

    def set_text(self,handle,text):
        self._post_update(('text',self._key(handle)),lambda:self._set_text(handle,text))

    def _set_text(self,handle,text):
        if handle and self.user32.IsWindow(handle):
            self.user32.SetWindowTextW(handle,text)

    def set_progress(self,handle,value):
        value=max(0,min(100,int(value)))
        self._post_update(('progress',self._key(handle)),
                          lambda:self._set_progress(handle,value))

    def _set_progress(self,handle,value):
        if handle and self.user32.IsWindow(handle):
            self.user32.SendMessageW(handle,self.PBM_SETPOS,value,0)

    def append_edit(self,handle,text):
        self._post_update(('edit',self._key(handle)),lambda:self._append_edit(handle,text))

    def _append_edit(self,handle,text):
        self._set_text(handle,text)
        if handle and self.user32.IsWindow(handle):
            self.user32.SendMessageW(handle,self.EM_SETSEL,-1,-1)
            self.user32.SendMessageW(handle,self.EM_SCROLLCARET,0,0)

    def set_icon(self,resource=32515):
        return self._invoke(lambda:self._set_icon(resource))

    def _set_icon(self,resource):
        icon=self.user32.LoadIconW(None,ctypes.c_void_p(resource))
        self.user32.SendMessageW(self.hwnd,self.WM_SETICON,0,icon)
        self.user32.SendMessageW(self.hwnd,self.WM_SETICON,1,icon)

    def show(self,activate=True):
        if self.closed or self.closing:
            return
        self._post_command(lambda:self._show(activate))

    def _show(self,activate):
        self.user32.ShowWindow(self.hwnd,5 if activate else 4)
        self._set_topmost(self.topmost,activate)

    def set_topmost(self,enabled,activate=False):
        if self.closed or self.closing:
            return
        self._post_command(lambda:self._set_topmost(enabled,activate))

    def _set_topmost(self,enabled,activate):
        insert_after=ctypes.c_void_p(-1 if enabled else -2)
        self.user32.SetWindowPos(self.hwnd,insert_after,0,0,0,0,
                                 0x0001|0x0002|0x0040|(0 if activate else 0x0010))

    def hide(self):
        if not self.closed and not self.closing:
            self._post_command(lambda:self.user32.ShowWindow(self.hwnd,0))

    def set_visible(self,handle,visible):
        self._post_update(('visible',self._key(handle)),
                          lambda:self.user32.ShowWindow(handle,5 if visible else 0))

    def set_enabled(self,handle,enabled):
        self._post_update(('enabled',self._key(handle)),
                          lambda:self.user32.EnableWindow(handle,bool(enabled)))

    def resize(self,width,height):
        def action():
            rect=wintypes.RECT(0,0,round(width*self.scale),round(height*self.scale))
            style=self.user32.GetWindowLongW(self.hwnd,-16)
            exstyle=self.user32.GetWindowLongW(self.hwnd,-20)
            self.user32.AdjustWindowRectEx(ctypes.byref(rect),style,False,exstyle)
            self.user32.SetWindowPos(self.hwnd,None,0,0,rect.right-rect.left,rect.bottom-rect.top,
                                     0x0002|0x0004|0x0010)
        self._post_command(action)

    def handle_message(self,message,wparam,lparam):
        if message==self.WM_APP_COMMAND:
            self._run_commands()
            return True,0
        if message==self.WM_APP_FLUSH:
            self._flush_updates()
            return True,0
        if message==self.WM_KEYDOWN:
            action={0x1B:'stop',0x75:'next',0x7A:'fullscreen'}.get(int(wparam))
            if action:
                self._emit('native_key',action,priority=action=='stop',
                           coalesce=None if action=='stop' else action)
                return True,0
        if message==self.WM_COMMAND:
            callback=self.callbacks.get(int(wparam)&0xffff)
            notification=(int(wparam)>>16)&0xffff
            if callback is not None and notification==0:  # BN_CLICKED
                self._emit('native_callback',callback)
                return True,0
        elif message==self.WM_CLOSE:
            if self.hwnd and self.user32.IsWindow(self.hwnd):
                self.user32.DestroyWindow(self.hwnd)
            return True,0
        elif message==self.WM_ERASEBKGND:
            rect=wintypes.RECT()
            self.user32.GetClientRect(self.hwnd,ctypes.byref(rect))
            self.user32.FillRect(wparam,ctypes.byref(rect),self.background_brush)
            return True,1
        elif message in (self.WM_CTLCOLORSTATIC,self.WM_CTLCOLOREDIT):
            colors=self.control_colors.get(self._key(lparam))
            if colors:
                foreground,background,brush=colors
                self.gdi32.SetTextColor(wparam,foreground)
                self.gdi32.SetBkColor(wparam,background)
                self.gdi32.SetBkMode(wparam,1)
                return True,self._key(brush)
        elif message==self.WM_NCDESTROY:
            self.registry.pop(self._key(self.hwnd),None)
            self.hwnd=None
            self.closed=True
            self.closing=True
            self._release_resources()
            self.user32.PostQuitMessage(0)
        return False,0

    def tick(self):
        if self.closed:
            return
        if not self.ready.is_set():
            if time.monotonic()-self.started_wall>1.25 and not self.closing:
                self.closing=True
                self._emit('effect_error',RuntimeError(
                    'Native Win32 прозорецът не отговори при стартиране.'),priority=True)
            return
        if not self.controls_ready:
            return
        elapsed=self.app.clock-self.born
        if self.limit is not None and elapsed>=self.limit:
            self.close()
        else:
            self.update_view(elapsed)

    def close(self):
        if self.closed or self.closing:
            return
        self.closing=True
        hwnd=self.hwnd
        if hwnd and self.user32.IsWindow(hwnd):
            if not self.user32.PostMessageW(hwnd,self.WM_CLOSE,0,0):
                error=ctypes.WinError(ctypes.get_last_error())
                LOG.error('Could not close native effect',exc_info=(type(error),error,error.__traceback__))

    def wait_closed(self,timeout=.25):
        if threading.current_thread() is not self.thread:
            self.thread.join(timeout=timeout)
        return not self.thread.is_alive()


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
            'QueryInformationJobObject':([ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p,
                                          ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32)],ctypes.c_int),
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

    def peak_memory_mib(self):
        if not self.handle:
            return None
        limits=JobExtendedLimits()
        returned=ctypes.c_uint32()
        if not self.k.QueryInformationJobObject(self.handle,9,ctypes.byref(limits),
                                                ctypes.sizeof(limits),ctypes.byref(returned)):
            return None
        return limits.PeakJobMemory/(1024*1024)

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


CLIENT_SCRIPT = r'''
const button=document.getElementById('action'),notice=document.getElementById('notice'),state=document.getElementById('state');
if(button)button.addEventListener('click',async()=>{button.disabled=true;notice.textContent='Preparing request…';
try{const r=await fetch(ACTION_URL,{method:'POST',cache:'no-store',credentials:'omit'});if(!r.ok)throw new Error(String(r.status));
notice.textContent='Request accepted. Check the Windows desktop.';
}catch(e){notice.textContent='The request could not be completed.';button.disabled=false;}});
let failures=0;async function poll(){let delay=document.hidden?5000:1000;
try{const r=await fetch(STATE_URL,{cache:'no-store',credentials:'omit'});if(!r.ok)throw new Error();const s=await r.json();failures=0;
document.body.classList.toggle('paused',s.paused);state.textContent=s.paused?'Session paused':('Local session • '+s.tabs+' tabs');
if(s.ended)return;
}catch(e){failures++;state.textContent='Local session unavailable';delay=Math.min(10000,1000*Math.pow(2,failures));}
setTimeout(poll,delay);}poll();'''

WEB_PAGES = [
'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>CaveDepths — Minecraft Java Mod 1.21.1</title><link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Cpath fill='%23549b45' d='M2 2h28v10H2z'/%3E%3Cpath fill='%23734d2b' d='M2 12h28v18H2z'/%3E%3C/svg%3E"><style>*{box-sizing:border-box}body{margin:0;background:#101820;color:#eef7f3;font:16px Segoe UI,sans-serif}nav{height:66px;display:flex;align-items:center;padding:0 5vw;background:#17242c;border-bottom:1px solid #344650}nav b{font-size:22px;color:#80c66a}nav span{margin-left:38px;color:#c3d2d8;word-spacing:18px}.local{margin-left:auto!important;color:#81949d!important;word-spacing:0!important}.hero{display:grid;grid-template-columns:1.25fr .9fr;gap:30px;max-width:1180px;margin:36px auto;padding:0 24px}.art{min-height:445px;background:linear-gradient(#77bce4 0 45%,#62a851 45% 52%,#745034 52%);position:relative;overflow:hidden;box-shadow:inset 0 0 0 1px #56717c}.art:before{content:'';position:absolute;width:110px;height:110px;left:18%;bottom:90px;background:#526d3c;box-shadow:110px -55px 0 #496236,220px 15px 0 #3c5634,330px -85px 0 #597744,440px -20px 0 #3c5634}.art strong{position:absolute;left:28px;bottom:25px;font-size:36px;text-shadow:0 2px 3px #1c2b23}.panel{background:#f5f7f4;color:#263832;padding:28px}.rating{color:#bf7b24;font-weight:700}.version{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:20px 0;padding:15px;background:#e5ebe6;font-size:13px}.notes{border-top:1px solid #ccd6d1;margin-top:20px;padding-top:17px;color:#52665f}button{width:100%;padding:15px;border:0;background:#367b42;color:#fff;font-weight:700;font-size:17px}footer,#state,#notice{font-size:12px;margin-top:13px;color:#657d75}</style></head><body><nav><b>BLOCKFORGE MODS</b><span>MODS MODPACKS MAPS SHADERS</span><span class="local">offline mirror</span></nav><main class="hero"><section class="art"><strong>CAVEDEPTHS</strong></section><aside class="panel"><small>COMMUNITY RELEASE</small><h1>CaveDepths</h1><div class="rating">★★★★★ <span style="color:#697a73;font-weight:400">1.8M downloads</span></div><p>Deep biomes, abandoned mines and new underground creatures for Minecraft Java Edition.</p><div class="version"><b>Game version</b><span>1.21.1</span><b>Loader</b><span>Fabric</span><b>Package</b><span>CaveDepths_Setup.exe</span><b>Updated</b><span>Today</span></div><button id="action">DOWNLOAD MOD</button><div class="notes"><b>Release 4.2</b><br>Crystal caverns · cave villages · performance preset</div><div id="notice"></div><div id="state">Checking…</div><footer>Локален режим • 127.0.0.1 • Minecraft is a Mojang Studios trademark.</footer></aside></main><script nonce="NONCE">CLIENT_SCRIPT</script></body></html>''',
'''<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Lucky Chest Gaming Rewards</title><link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='16' fill='%23703966'/%3E%3Cpath d='M8 11h16v14H8zm8-5v19M8 15h16' stroke='white' stroke-width='2'/%3E%3C/svg%3E"><style>*{box-sizing:border-box}body{margin:0;background:#f1e9df;color:#392b32;font:17px Georgia,serif}.top{text-align:center;padding:22px;letter-spacing:3px;font:13px Segoe UI}.coupon{max-width:870px;margin:28px auto;background:#fff;display:grid;grid-template-columns:2fr 1fr;box-shadow:0 12px 35px #73544d33;border:2px dashed #a5796e}.main{padding:54px}.side{background:#703966;color:white;padding:42px 28px;border-left:2px dashed #f1c7dd}h1{font-size:49px;line-height:1.04}.code{font:700 28px Consolas;border:1px solid #c8afa8;padding:12px;text-align:center;margin:25px 0}button{background:#392b32;color:#fff;border:0;padding:15px 23px;font:700 15px Segoe UI;width:100%}#notice,#state,footer{font:13px Segoe UI;margin-top:14px;color:#755d66}.side #state,.side footer{color:#eadce4}</style></head><body><div class="top">LUCKY CHEST REWARDS • GAMING BONUS</div><div class="coupon"><section class="main"><small>MEMBER DROP • TODAY ONLY</small><h1>Спечелихте 5000 game coins</h1><p>Вашият CaveDepths download отключи ограничена награда. Кодът е запазен за още 02:00 минути.</p><div class="code">CHEST-5000-X7</div><div id="notice"></div></section><aside class="side"><h2>100% REWARD</h2><p>Потвърдете наградата преди сесията да изтече.</p><button id="action">CLAIM GAMING REWARD</button><div id="state">Checking…</div><footer>Локален режим • reward service</footer></aside></div><script nonce="NONCE">CLIENT_SCRIPT</script></body></html>''',
'''<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>SecureGuard Web Scan</title><link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Cpath d='M16 3l11 4v8c0 7-5 12-11 14C10 27 5 22 5 15V7z' fill='%23b32c40'/%3E%3C/svg%3E"><style>*{box-sizing:border-box}body{margin:0;background:#e9edf1;color:#26323f;font:15px Segoe UI}.bar{height:48px;background:#293744;color:white;padding:14px 5vw}.app{max-width:980px;margin:35px auto;background:white;border:1px solid #cad1d8}.alert{background:#b32c40;color:white;padding:25px 32px;display:flex;gap:24px;align-items:center}.alert strong{font-size:25px}.content{display:grid;grid-template-columns:1fr 290px}.results{padding:28px}.row{display:flex;justify-content:space-between;padding:15px;border-bottom:1px solid #e2e5e8}.danger{color:#a22035;font-weight:700}.summary{background:#f5f6f7;padding:28px}button{padding:13px 18px;width:100%;background:#b32c40;color:#fff;border:0;font-weight:700}#notice,#state,footer{font-size:13px;margin-top:14px;color:#66717c}</style></head><body><div class="bar">SECUREGUARD ONLINE SCAN</div><main class="app"><div class="alert"><span style="font-size:40px">!</span><strong>Mod download-ът съдържа 37 заплахи</strong></div><div class="content"><section class="results"><h2>Scan results</h2><div class="row"><span>Downloaded package</span><span class="danger">12 risks</span></div><div class="row"><span>Game launcher</span><span class="danger">9 risks</span></div><div class="row"><span>Saved worlds</span><span class="danger">16 risks</span></div><p>Immediate action is recommended to prevent additional changes.</p></section><aside class="summary"><h3>Action required</h3><p>Run the desktop security scan now.</p><button id="action">RUN SECURITY SCAN</button><div id="notice"></div><div id="state">Checking…</div><footer>Локален режим • web scan</footer></aside></div></main><script nonce="NONCE">CLIENT_SCRIPT</script></body></html>''',
'''<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>GameHub Account Notice</title><link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='11' r='6' fill='%23516f98'/%3E%3Cpath d='M5 29c1-8 5-11 11-11s10 3 11 11' fill='%23516f98'/%3E%3C/svg%3E"><style>*{box-sizing:border-box}body{margin:0;background:#f7f8fa;color:#293849;font:16px Segoe UI}header{padding:20px 7vw;background:white;border-bottom:1px solid #dfe4e9;font-weight:700}.notice{max-width:720px;margin:65px auto;background:white;border:1px solid #d8dee5;padding:42px}.mark{width:45px;height:45px;border-radius:50%;display:grid;place-items:center;background:#f2e8cf;color:#8a6a28;font-size:24px}h1{font-size:29px}.meta{display:grid;grid-template-columns:150px 1fr;background:#f3f5f7;padding:18px;line-height:1.8}.actions{display:flex;align-items:center;gap:16px;margin-top:28px}button{padding:12px 18px;border:1px solid #516f98;background:#516f98;color:white;font-weight:600}#notice,#state,footer{font-size:13px;color:#66788a;margin-top:14px}</style></head><body><header>GAMEHUB ACCOUNT <span style="float:right;color:#8290a0;font-weight:400">Security notice</span></header><main class="notice"><div class="mark">!</div><h1>Игровият профил ще бъде спрян</h1><p>Засечено е непозволено приложение след последния mod download. Прегледайте случая, за да избегнете временно ограничаване.</p><div class="meta"><b>Game profile</b><span>StudentPlayer</span><b>Статус</b><span>Pending review</span><b>Заявка</b><span>GH-41-8820</span></div><div class="actions"><button id="action">REVIEW ACCOUNT NOTICE</button><span>Response required today</span></div><div id="notice"></div><div id="state">Checking…</div><footer>Локален режим • GameHub notice</footer></main><script nonce="NONCE">CLIENT_SCRIPT</script></body></html>''',
'''<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Block Runtime Update</title><link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='13' fill='%23366e99'/%3E%3Cpath d='M16 8v12m-5-4l5 5 5-5M9 25h14' stroke='white' stroke-width='2' fill='none'/%3E%3C/svg%3E"><style>*{box-sizing:border-box}body{margin:0;background:#fff;color:#28323b;font:16px Segoe UI}.wrap{max-width:780px;margin:75px auto;text-align:center;padding:35px}.ring{width:86px;height:86px;border:8px solid #dfe9f0;border-top-color:#366e99;border-radius:50%;margin:auto}h1{font-size:32px;font-weight:500}.version{display:inline-block;background:#f1f4f6;padding:9px 18px;margin:15px}.facts{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:#dfe4e8;margin:28px 0;border:1px solid #dfe4e8}.facts div{background:white;padding:17px}button{background:#366e99;color:white;border:0;padding:13px 28px;font-weight:650}#notice,#state,footer{font-size:13px;color:#6a7883;margin-top:13px}</style></head><body><main class="wrap"><div class="ring"></div><h1>CaveDepths requires Block Runtime</h1><p>Version 4.8 or later is required before the mod can start.</p><div class="version">Available: Block Runtime 4.8.12</div><div class="facts"><div><b>Channel</b><br>automatic</div><div><b>Publisher</b><br>Unknown</div><div><b>Package</b><br>runtime_setup.exe</div></div><button id="action">INSTALL REQUIRED RUNTIME</button><div id="notice"></div><div id="state">Checking…</div><footer>Локален режим • Block Runtime service</footer></main><script nonce="NONCE">CLIENT_SCRIPT</script></body></html>''',
'''<!doctype html><html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>FPS Booster Pro</title><link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Cpath d='M5 22a12 12 0 1122 0' fill='none' stroke='%232a7a6e' stroke-width='5'/%3E%3Cpath d='M16 18l7-7' stroke='%232a7a6e' stroke-width='3'/%3E%3C/svg%3E"><style>*{box-sizing:border-box}body{margin:0;background:#eef3f1;color:#243b37;font:16px Segoe UI}header{background:#fff;padding:19px 6vw;border-bottom:3px solid #2a7a6e;font-size:21px}.dash{max-width:1050px;margin:35px auto}.headline{display:flex;justify-content:space-between;align-items:end}.headline h1{font-size:34px}.meters{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin:25px 0}.meter{background:white;padding:25px;border:1px solid #d6e0dc}.value{font-size:40px;color:#b14a46;font-weight:700}.compare{display:grid;grid-template-columns:1fr 1fr;background:white;border:1px solid #d6e0dc}.compare section{padding:25px}.compare section+section{border-left:1px solid #d6e0dc}button{padding:14px 24px;background:#2a7a6e;color:white;border:0;font-weight:700}#notice,#state,footer{font-size:13px;color:#687c76;margin-top:13px}</style></head><body><header><b>FPS BOOSTER PRO</b><span style="float:right;font-size:13px;color:#788985">Performance dashboard</span></header><main class="dash"><div class="headline"><div><h1>Minecraft ще върви с 240 FPS</h1><p>One-click optimization for CaveDepths and Fabric profiles.</p></div><button id="action">BOOST GAME NOW</button></div><div class="meters"><div class="meter">Current FPS<div class="value">18</div></div><div class="meter">Junk mods<div class="value">47</div></div><div class="meter">Boost score<div class="value">+900%</div></div></div><div class="compare"><section><h3>Before</h3><p>18 FPS · stutter · high latency</p></section><section><h3>After</h3><p>240 FPS · smooth · protected</p></section></div><div id="notice"></div><div id="state">Checking…</div><footer>Локален режим • performance service</footer></main><script nonce="NONCE">CLIENT_SCRIPT</script></body></html>''',
]
PAGE_ACTION_SCENES = ('download', 'advert', 'scanner', 'warning', 'updater', 'taskmanager')


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """Small loopback server with a hard ceiling on concurrent request threads."""
    daemon_threads=True
    block_on_close=False
    request_queue_size=8

    def __init__(self,*args,max_workers=8,**kwargs):
        self._slots=threading.BoundedSemaphore(max_workers)
        super().__init__(*args,**kwargs)

    def process_request(self,request,client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request,client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self,request,client_address):
        try:
            super().process_request_thread(request,client_address)
        finally:
            self._slots.release()

    def handle_error(self,request,client_address):
        # Chromium routinely cancels an in-flight/keep-alive loopback request
        # while a tab or its owned Job is closing.  BaseServer.handle_error prints
        # a frightening traceback to stderr even though this is a normal socket
        # lifecycle event.  Preserve reporting for every other exception.
        error=sys.exc_info()[1]
        if isinstance(error,(ConnectionResetError,ConnectionAbortedError,BrokenPipeError)):
            LOG.debug('Loopback client disconnected: %s',error)
            return
        super().handle_error(request,client_address)


class LocalPages:
    """Loopback only, unguessable route, no commands or filesystem serving."""
    def __init__(self,generation=0,max_tabs=ABSOLUTE_MAX_TABS):
        self.token=secrets.token_hex(20)
        self.generation=generation
        self.max_tabs=max(1,min(ABSOLUTE_MAX_TABS,max_tabs))
        self.state={'time':0,'paused':False,'tabs':0,'ended':False,
                    'generation':generation}
        self.actions=queue.Queue(maxsize=8)
        self.action_lock=threading.Lock()
        self.last_action=0.0
        self.closed=False
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
                elif path.startswith('tab/') and path[4:].isdigit() and 0<=int(path[4:])<owner.max_tabs:
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
                if 0<content_length<=4096:
                    self.rfile.read(content_length)
                if (not index.isdigit() or not 0<=int(index)<owner.max_tabs or content_length!=0):
                    self.send_error(404); return
                now=time.monotonic()
                with owner.action_lock:
                    if now-owner.last_action<1.0:
                        payload=b'{"accepted":false,"reason":"rate-limit"}'
                        self.send_payload(429,payload,'application/json'); return
                    owner.last_action=now
                try:
                    owner.actions.put_nowait((owner.generation,int(index)))
                    payload=b'{"accepted":true}'
                    self.send_payload(202,payload,'application/json')
                except queue.Full:
                    payload=b'{"accepted":false}'
                    self.send_payload(429,payload,'application/json')
        self.server=BoundedThreadingHTTPServer(('127.0.0.1',0),Handler,max_workers=8)
        self.thread=threading.Thread(target=lambda:self.server.serve_forever(poll_interval=.1),daemon=True)
        self.thread.start()

    def page(self,index):
        page=WEB_PAGES[index%len(WEB_PAGES)]
        for key,value in {'NONCE':self.token,'CLIENT_SCRIPT':CLIENT_SCRIPT,
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
        if self.closed:
            return
        self.closed=True
        self.state={**self.state,'ended':True}
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=1)


class NativeSession:
    """Own browser profile and eight files we create, with reversible names."""
    MAX_TABS=ABSOLUTE_MAX_TABS

    def __init__(self, executable=None, max_tabs=4, generation=0, presentation_bounds=None):
        self.executable=executable
        self.max_tabs=max(1,min(self.MAX_TABS,max_tabs))
        self.generation=generation
        self.presentation_bounds=presentation_bounds
        self.root=Path(tempfile.mkdtemp(prefix='CyberClassroom-LAB-'))
        self.profile=self.root/'browser-profile'
        self.folder=self.root/'Учебни файлове'
        self.files=[]
        self.manifest=[]
        try:
            self.folder.mkdir()
            for i,title in enumerate(['Доклад_история','Проект_клуб','Бележки','Задачи',
                                      'Списък_материали','График','План_урок','Резервно_копие']):
                path=self.folder/(title+'.txt')
                content=(f'УЧЕБЕН ФАЙЛ {i+1}\nСъздаден специално за демонстрацията.\n'
                         'Този текст не съдържа лични данни.\n').encode('utf-8')
                path.write_bytes(content)
                self.files.append((path,path.with_name(path.name+'.locked'),content))
                self.manifest.append({'name':path.name,'locked':path.name+'.locked',
                                      'sha256':hashlib.sha256(content).hexdigest()})
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
        self.last_browser_launch=-10.0
        self.last_window_check=0.0

    def _contained_regular(self,path,allow_missing=False):
        try:
            if path.parent.resolve()!=self.folder.resolve():
                return False
            if not os.path.lexists(path):
                return allow_missing
            return path.is_file() and not path.is_symlink()
        except OSError:
            return False

    def open_tab(self):
        now=time.monotonic()
        if self.closed or self.tabs>=self.max_tabs:
            return False
        if self.tabs and now-self.last_browser_launch<3.0:
            return False
        if not self.executable:
            raise RuntimeError('Не е намерен Edge/Chrome. Изберете msedge.exe или chrome.exe от панела.')
        if self.job is None:
            check_browser_policy(self.executable)
            self.profile.mkdir(exist_ok=True)
            default=self.profile/'Default'; default.mkdir(exist_ok=True)
            (default/'Preferences').write_text(json.dumps({'download':{'default_directory':str(self.root/'Downloads')}}),encoding='utf-8')
            self.pages=LocalPages(self.generation,self.max_tabs)
            try:
                self.job=OwnedBrowserJob()
                self.browser_started=time.monotonic()
                self.browser_ready=False
            except Exception:
                self.pages.close(); self.pages=None
                raise
        args=['--user-data-dir='+str(self.profile),'--no-first-run','--no-default-browser-check',
              '--disable-sync','--disable-extensions','--disable-background-networking',
              '--disable-background-mode']
        if self.presentation_bounds:
            left,top,right,bottom=self.presentation_bounds
            args.extend((f'--window-position={left},{top}',
                         f'--window-size={max(800,right-left)},{max(600,bottom-top)}'))
        else:
            args.append('--start-maximized')
        if self.tabs==0:
            args.append('--new-window')
        else:
            args.append('--new-tab')
        args.append(self.pages.url(self.tabs))
        self.job.launch(self.executable,args)
        self.tabs+=1
        self.last_browser_launch=now
        return True

    def update(self,clock,paused,hide):
        if self.pages:
            self.pages.state={'time':clock,'paused':paused,'tabs':self.tabs,'ended':False,
                              'generation':self.generation}
        if self.job:
            now=time.monotonic()
            if not self.browser_ready:
                self.browser_ready=self.job.has_window()
                if not self.browser_ready and now-self.browser_started>15:
                    raise RuntimeError('Не се появи отделен браузърен прозорец. Изберете друг Edge/Chrome от панела.')
            elif now-self.last_window_check>=1.0:
                self.last_window_check=now
                if not self.job.has_window():
                    raise RuntimeError('Учебният браузърен прозорец е затворен. Сцената е изключена безопасно.')
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
        limit=max(0,min(8,count))
        for (plain,locked,content),entry in zip(self.files[:limit],self.manifest[:limit]):
            if plain.name!=entry['name'] or locked.name!=entry['locked']:
                continue
            if (self._contained_regular(plain) and self._contained_regular(locked,allow_missing=True)
                    and not locked.exists()):
                if hashlib.sha256(plain.read_bytes()).hexdigest()==entry['sha256']:
                    plain.rename(locked)

    def restore_files(self):
        issues=[]
        for (plain,locked,content),entry in zip(self.files,self.manifest):
            try:
                if plain.name!=entry['name'] or locked.name!=entry['locked']:
                    issues.append(entry['name']);continue
                if (self._contained_regular(locked) and self._contained_regular(plain,allow_missing=True)
                        and not plain.exists()):
                    if hashlib.sha256(locked.read_bytes()).hexdigest()==entry['sha256']:
                        locked.rename(plain)
                if locked.exists():
                    issues.append(locked.name)
                elif (not plain.is_file() or plain.is_symlink() or
                      hashlib.sha256(plain.read_bytes()).hexdigest()!=entry['sha256']):
                    # Never overwrite a changed file or follow a replacement
                    # symlink.  Report the item instead so the teacher can inspect it.
                    issues.append(plain.name)
            except OSError:
                issues.append(locked.name if locked.exists() else plain.name)
        return issues

    def restore_next_file(self):
        """Restore at most one owned file for a visible, bounded recovery sequence."""
        for (plain,locked,content),entry in zip(self.files,self.manifest):
            try:
                if not locked.exists():
                    continue
                if (plain.name!=entry['name'] or locked.name!=entry['locked'] or
                        not self._contained_regular(locked) or
                        not self._contained_regular(plain,allow_missing=True) or plain.exists()):
                    return False,locked.name
                if hashlib.sha256(locked.read_bytes()).hexdigest()!=entry['sha256']:
                    return False,locked.name
                locked.rename(plain)
                return True,plain.name
            except OSError:
                return False,locked.name
        return None,None

    def close_browser(self):
        job,pages=self.detach_browser()
        try:
            if job:
                job.close()
        finally:
            if pages:
                pages.close()

    def detach_browser(self):
        job,self.job=self.job,None
        pages,self.pages=self.pages,None
        self.tabs=0
        self.browser_started=0
        self.browser_ready=False
        self.last_visibility=0
        self.last_window_check=0
        self.last_browser_launch=-10.0
        return job,pages

    @staticmethod
    def close_detached_browser(job,pages):
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


class MemoryStatusEx(ctypes.Structure):
    _fields_=[('length',wintypes.DWORD),('memory_load',wintypes.DWORD),
              ('total_phys',ctypes.c_uint64),('avail_phys',ctypes.c_uint64),
              ('total_page',ctypes.c_uint64),('avail_page',ctypes.c_uint64),
              ('total_virtual',ctypes.c_uint64),('avail_virtual',ctypes.c_uint64),
              ('avail_extended',ctypes.c_uint64)]


class ProcessMemoryCounters(ctypes.Structure):
    _fields_=[('cb',wintypes.DWORD),('page_faults',wintypes.DWORD),
              ('peak_working_set',ctypes.c_size_t),('working_set',ctypes.c_size_t),
              ('peak_paged_pool',ctypes.c_size_t),('paged_pool',ctypes.c_size_t),
              ('peak_nonpaged_pool',ctypes.c_size_t),('nonpaged_pool',ctypes.c_size_t),
              ('pagefile',ctypes.c_size_t),('peak_pagefile',ctypes.c_size_t)]


def windows_memory_snapshot():
    """Return owned-process and system-memory metrics; unrelated processes are untouched."""
    if sys.platform!='win32':
        return None,None
    try:
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        psapi=ctypes.WinDLL('psapi',use_last_error=True)
        kernel.GetCurrentProcess.restype=ctypes.c_void_p
        kernel.GlobalMemoryStatusEx.argtypes=[ctypes.POINTER(MemoryStatusEx)]
        psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(ProcessMemoryCounters),wintypes.DWORD]
        memory=MemoryStatusEx(); memory.length=ctypes.sizeof(memory)
        process=ProcessMemoryCounters(); process.cb=ctypes.sizeof(process)
        available=None; working=None
        if kernel.GlobalMemoryStatusEx(ctypes.byref(memory)):
            available=memory.avail_phys/(1024*1024)
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(process),process.cb):
            working=process.working_set/(1024*1024)
        return working,available
    except (OSError,AttributeError):
        return None,None


class Classroom:
    EVENT_LIMIT=12

    def __init__(self, root, enable_hotkeys=True):
        self.root = root
        self.events = BoundedEventBus(maxsize=64)
        self.hotkeys = None
        self.hotkeys_ok = sys.platform != 'win32'
        self.effects = []
        self.closing_effects=[]
        self.cleanup_threads=[]
        self.stage = None
        self.session = None
        self.last_folder = None
        self.cleanup_notice = ''
        self.browser_path = find_browser()
        self.native_kind = None
        self.native_born = 0
        self.native_count = 0
        self.rng = random.Random()
        self.scenario=ScenarioState()
        self.story=DEFAULT_STORY
        self.timeline=list(self.story.beats)
        self.chapters=list(self.story.chapters)
        self.limiter=RateLimiter()
        self.windows_profile=detect_windows_profile()
        self.monitors=enumerate_monitors()
        self.tray_icon=None
        self.pending_branch_scene=None
        self.running = self.paused = self.closed = False
        self.clock = 0.0
        self.mode = None
        self.event_index = 0
        self.last = time.monotonic()
        self.job = None
        self.rate = 1.0
        self.teacher_paced=False
        self.chapter_started=0.0
        self.last_tick_started=time.monotonic()
        self.loop_delay_ms=0.0
        self.render_ms=0.0
        self.last_metrics=0.0
        self.pressure=False
        self.pressure_handled=False
        self.sound = tk.BooleanVar(value=False)
        self.sound_bank = SoundBank()
        self.windows_notifications = tk.BooleanVar(value=True)
        self.toast_notifier = WindowsToastNotifier()
        self.hide_on_pause = tk.BooleanVar(value=True)
        self.duration = tk.StringVar(value=DEFAULT_STORY_LABEL)
        self.monitor_choice=tk.StringVar(value=self.monitors[0].label)
        self.fullscreen = tk.BooleanVar(value=True)
        self.visual_mode = tk.StringVar(value='Смесени ефекти')
        self.profile_name=tk.StringVar(value='Училищен безопасен')
        self.presentation_mode=tk.StringVar(value='Автоматично')
        self.reduced_motion=tk.BooleanVar(value=True)
        self.decision_status=tk.StringVar(value='Решение: няма чакащ избор')
        self.reporting_error = False
        self.status = tk.StringVar(value='Готовност за демонстрация')
        self.key_status = tk.StringVar(value='Проверка на глобалните комбинации…')
        self.resource_status=tk.StringVar(value='Ресурси: готови за проверка')
        self.chapter_status=tk.StringVar(value='Глава: —')
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
        r.title('Дигитални детективи 8.0 — интерактивен Windows инцидент')
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        width, height = min(1000, sw-50), min(810, sh-70)
        r.geometry(f'{width}x{height}+{max(15,(sw-width)//2)}+{max(10,(sh-height)//2-20)}')
        r.configure(bg='#101b2c')
        style = ttk.Style(r)
        if 'clam' in style.theme_names():
            style.theme_use('clam')
        style.configure('TButton', font=('Segoe UI', 10), padding=(10, 7))
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
        label(r, 'ДИГИТАЛНИ ДЕТЕКТИВИ / 8.0', 23, '#e9f1fc', bold=True).pack(anchor='w', padx=25, pady=(15, 4))
        label(r, 'Твоят Windows • отделен Edge/Chrome профил • локални страници • учебна папка във File Explorer',
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
        ttk.Button(row, text='Провери готовността', command=self.readiness_check).pack(side='right')
        ttk.Button(row, text='Избор на браузър', command=self.choose_browser).pack(side='right', padx=6)
        ttk.Button(row, text='Журнал', command=self.show_log).pack(side='right')
        settings = tk.Frame(r, bg='#101b2c')
        settings.pack(fill='x', padx=25, pady=9)
        label(settings, 'Профил:', 11, '#e9f1fc').pack(side='left')
        ttk.Combobox(settings,textvariable=self.profile_name,width=21,state='readonly',
                     values=list(PROFILES)).pack(side='left',padx=(7,14))
        label(settings, 'Продължителност:', 11, '#e9f1fc').pack(side='left')
        ttk.Combobox(settings, textvariable=self.duration, width=11, state='readonly',
                     values=list(STORY_PRESETS)).pack(side='left', padx=8)
        tk.Checkbutton(settings, text='Цял екран', variable=self.fullscreen, bg='#101b2c', fg='#e9f1fc',
                       selectcolor='#20354b', activebackground='#101b2c', activeforeground='white').pack(side='left', padx=5)
        tk.Checkbutton(settings, text='Тематичен звук', variable=self.sound, command=self.on_sound_toggle,
                       bg='#101b2c', fg='#e9f1fc', selectcolor='#20354b',
                       activebackground='#101b2c', activeforeground='white').pack(side='left', padx=(15,5))
        ttk.Button(settings, text='Тест', command=self.preview_sound).pack(side='left', padx=(0,8))
        tk.Checkbutton(settings, text='Намалено движение', variable=self.reduced_motion,
                       bg='#101b2c', fg='#e9f1fc', selectcolor='#20354b',
                       activebackground='#101b2c', activeforeground='white').pack(side='left')
        pause_row=tk.Frame(r,bg='#101b2c')
        pause_row.pack(fill='x',padx=25,pady=(0,5))
        label(pause_row,'Режим:',11,'#e9f1fc').pack(side='left')
        ttk.Combobox(pause_row,textvariable=self.presentation_mode,width=18,state='readonly',
                     values=['Автоматично','Учителско темпо']).pack(side='left',padx=8)
        tk.Checkbutton(pause_row, text='Скривай сцените при пауза', variable=self.hide_on_pause,
                        bg='#101b2c', fg='#e9f1fc', selectcolor='#20354b',
                        activebackground='#101b2c', activeforeground='white').pack(side='left',padx=12)
        tk.Checkbutton(pause_row, text='Windows известия', variable=self.windows_notifications,
                       bg='#101b2c', fg='#e9f1fc', selectcolor='#20354b',
                       activebackground='#101b2c', activeforeground='white').pack(side='left',padx=5)
        display_row=tk.Frame(r,bg='#101b2c')
        display_row.pack(fill='x',padx=25,pady=(0,7))
        label(display_row,'Презентационен екран:',11,'#e9f1fc').pack(side='left')
        ttk.Combobox(display_row,textvariable=self.monitor_choice,width=38,state='readonly',
                     values=[monitor.label for monitor in self.monitors]).pack(side='left',padx=8)
        platform_text=(f'{self.windows_profile.generation.replace("windows","Windows ")} • '
                       f'{"BG" if self.windows_profile.language=="bg" else "EN"} system UI')
        label(display_row,platform_text,10,'#9bb2cc').pack(side='left')
        visuals = tk.Frame(r, bg='#101b2c')
        visuals.pack(fill='x', padx=25, pady=(0, 8))
        label(visuals, 'Ефект върху екрана:', 11, '#e9f1fc').pack(side='left')
        ttk.Combobox(visuals, textvariable=self.visual_mode, width=20, state='readonly',
                     values=['Смесени ефекти', 'Разкъсване', 'Разтичане', 'Безкраен екран',
                             'Статичен кадър']).pack(side='left', padx=8)
        label(visuals, 'Еднократен кадър от избрания монитор, само в RAM', 10, '#9bb2cc').pack(side='left')
        self.start_button = ttk.Button(r, text='▶  СТАРТИРАЙ ЦЯЛАТА ИСТОРИЯ',
                                       command=lambda: self.start('auto'))
        self.start_button.pack(fill='x', padx=25, pady=(0, 10))
        decision=tk.Frame(r,bg='#17283c')
        decision.pack(fill='x',padx=25,pady=(0,8))
        label(decision,'',10,'#dce9f6',textvariable=self.decision_status,wraplength=510).pack(
            side='left',fill='x',expand=True,padx=12,pady=8)
        self.accept_choice_button=ttk.Button(decision,text='Приеми резултата',
                                             command=self.accept_student_choice,state='disabled')
        self.accept_choice_button.pack(side='left',padx=4)
        self.compromised_button=ttk.Button(decision,text='Покажи компрометирания път',
                                           command=self.force_compromised_path,state='disabled')
        self.compromised_button.pack(side='left',padx=(4,10))
        manual = tk.Frame(r, bg='#101b2c')
        manual.pack(fill='x', padx=25)
        for i, (title, mode) in enumerate([
            ('Minecraft мод + сайтове', 'tabs'), ('UAC + инсталатор', 'uac'),
            ('Runtime updater', 'updater'), ('Firewall warning', 'firewall'),
            ('Task Manager', 'taskmanager'), ('Protection History', 'protection_history'),
            ('Фалшиво сканиране', 'scanner'), ('File Properties', 'properties'),
            ('Response Console', 'terminal_chapter'), ('Мрежова активност', 'network_activity'),
            ('Файлове и „криптиране“', 'files_chapter'), ('WannaCry: откуп', 'ransom'),
            ('Възстановяване', 'recovery'), ('Изкривяване на екрана', 'glitch'),
            ('Син екран', 'blue'), ('Фалшиво рестартиране', 'reboot'),
            ('Сравнение на заплахите', 'debrief')]):
            ttk.Button(manual, text=title, command=lambda m=mode: self.start(m)).grid(
                row=i//3, column=i%3, sticky='ew', padx=(0, 6), pady=3)
        for column in range(3):
            manual.columnconfigure(column, weight=1)
        controls = tk.Frame(r, bg='#101b2c')
        controls.pack(fill='x', padx=25, pady=10)
        self.resume_button = ttk.Button(controls, text='Продължи', command=self.toggle_pause, state='disabled')
        self.resume_button.pack(side='left')
        ttk.Button(controls, text='Спри / изчисти', command=self.stop).pack(side='left', padx=7)
        ttk.Button(controls, text='Следваща глава', command=self.next_chapter).pack(side='left')
        ttk.Button(controls, text='Повтори глава', command=self.replay_chapter).pack(side='left',padx=7)
        ttk.Button(controls, text='Учебна папка', command=self.show_lesson_folder).pack(side='left')
        ttk.Button(controls, text='Изход', command=self.close).pack(side='right')
        label(r, '', 11, '#80e2c4', textvariable=self.status, wraplength=width-55).pack(anchor='w', padx=26, pady=6)
        label(r,'',10,'#c8d6e7',textvariable=self.chapter_status,wraplength=width-55).pack(anchor='w',padx=26,pady=2)
        label(r,'',10,'#e6c885',textvariable=self.resource_status,wraplength=width-55).pack(anchor='w',padx=26,pady=(2,6))
        chapters='  •  '.join(name for _,name in CHAPTERS)
        label(r,'Глави: '+chapters,9,'#7891aa',wraplength=width-55).pack(anchor='w',padx=26,pady=(0,6))
        label(r, 'Истински браузър с отделен временен профил и локални учебни страници.\n'
              'Създава 8 учебни файла. След спиране връща имената им; папката остава за преглед.\n'
              'Личните файлове, камерата, микрофонът и системните настройки не се използват.',
              10, '#9bb2cc', wraplength=width-55).pack(anchor='w', padx=26, pady=(6, 15))

    @property
    def profile(self):
        return PROFILES.get(self.profile_name.get(),PROFILES['Училищен безопасен'])

    @property
    def presentation_monitor(self):
        chosen=self.monitor_choice.get()
        return next((monitor for monitor in self.monitors if monitor.label==chosen),self.monitors[0])

    def system_text(self,bg,en):
        return self.windows_profile.text(bg,en)

    def preview_sound(self):
        self.sound_bank.play('notification')

    def notify_windows(self,title,body):
        if not self.windows_notifications.get():
            return False
        return self.toast_notifier.show(title,body)

    def ensure_tray_icon(self):
        if self.tray_icon is None or self.tray_icon.closed:
            self.tray_icon=OwnedTrayIcon(self.events,'Block Runtime Host')
        self.scenario.tray_visible=True

    def close_tray_icon(self):
        tray,self.tray_icon=self.tray_icon,None
        self.scenario.tray_visible=False
        if tray is not None:
            tray.close()

    def on_sound_toggle(self):
        if self.sound.get():
            if not self.paused:
                self.preview_sound()
        else:
            self.sound_bank.stop()

    def live_effect_count(self):
        active=sum(not effect.closed for effect in self.effects)
        closing=sum(effect.thread.is_alive() for effect in self.closing_effects)
        return active+closing+(1 if self.stage is not None else 0)

    def guarded(self,callback,include_chapter=True):
        generation=self.scenario.generation
        chapter=self.scenario.chapter_generation if include_chapter else None
        def invoke():
            if self.running and self.scenario.accepts(generation,chapter):
                callback()
        return invoke

    def record_student_choice(self,checkpoint,choice,next_scene=None):
        accepted=self.scenario.apply_event(
            ScenarioEvent.STUDENT_DECISION,
            {'checkpoint':checkpoint,'choice':choice,
             'idempotency_key':f'student:{checkpoint}:{self.scenario.chapter_generation}'},
            generation=self.scenario.generation,
            chapter_generation=self.scenario.chapter_generation)
        if not accepted:
            return False
        self.pending_branch_scene=next_scene
        self.paused=True;self.last=time.monotonic();self.sound_bank.stop()
        if self.session:
            self.session.update(self.clock,True,self.hide_on_pause.get())
        if self.stage is not None:
            self.stage.win.attributes('-topmost',False)
            if self.hide_on_pause.get():self.stage.win.withdraw()
        for effect in self.effects:
            if not effect.closed:
                effect.set_topmost(False)
                if self.hide_on_pause.get():effect.hide()
        self.decision_status.set(f'Решение „{choice}“ при {checkpoint}. Учителят избира развитието.')
        self.accept_choice_button.configure(state='normal')
        self.compromised_button.configure(state='normal')
        self.resume_button.configure(text='▶ Продължи',state='disabled')
        self.show_panel()
        return True

    def _finish_branch_gate(self):
        self.pending_branch_scene=None
        self.decision_status.set('Решение: няма чакащ избор')
        self.accept_choice_button.configure(state='disabled')
        self.compromised_button.configure(state='disabled')
        self.resume_button.configure(text='Пауза',state='normal')

    def accept_student_choice(self):
        if not self.running or not self.scenario.branch_pending:
            return
        safe=self.scenario.student_choice in {'no','cancel','block','stop'}
        if safe:
            self.scenario.apply_event(
                ScenarioEvent.TEACHER_ACCEPTED,
                {'idempotency_key':f'accept:{self.scenario.branch_checkpoint}:{self.scenario.chapter_generation}'})
            self._finish_branch_gate()
            if self.mode=='auto':
                self.status.set('Инцидентът беше предотвратен. Преминаване към разбора.')
                self.seek_chapter(len(self.chapters)-1)
            else:
                self.stop('Инцидентът беше предотвратен от избраното безопасно действие.')
            return
        self.force_compromised_path()

    def force_compromised_path(self):
        if not self.running or not self.scenario.branch_pending:
            return
        scene=self.pending_branch_scene
        self.scenario.apply_event(
            ScenarioEvent.TEACHER_COMPROMISED,
            {'phase':'execution',
             'idempotency_key':f'continue:{self.scenario.branch_checkpoint}:{self.scenario.chapter_generation}'})
        self._finish_branch_gate();self.paused=False;self.last=time.monotonic();self.hide_panel()
        if self.session:self.session.update(self.clock,False,self.hide_on_pause.get())
        if self.stage is not None and getattr(self.stage,'ready',True):
            self.stage.win.deiconify();self.stage.win.attributes('-topmost',True);self.stage.win.lift()
        for effect in self.effects:
            if not effect.closed:effect.show(activate=False)
        if self.mode!='auto' and scene:
            self.limiter.reset('effect-launch');self.spawn(scene)

    def readiness_check(self):
        checks=[]
        try:
            probe=Path(tempfile.gettempdir())/('CyberClassroom-check-'+secrets.token_hex(4)+'.tmp')
            probe.write_text('ok',encoding='utf-8'); probe.unlink()
            checks.append('временна папка ✓')
        except OSError as exc:
            checks.append('временна папка ✗ '+str(exc))
        if self.browser_path and self.browser_path.is_file():
            try:
                check_browser_policy(self.browser_path)
                checks.append(self.browser_path.name+' / изолиран профил ✓')
            except Exception as exc:
                checks.append('браузърна политика ✗ '+str(exc))
        else:
            checks.append('браузър не е избран')
        checks.append('Pillow / RAM кадър ✓' if Image is not None else 'Pillow липсва (само статични сцени)')
        checks.append('тематични WAV звуци ✓' if winsound is not None else 'звуци не се поддържат')
        checks.append('Windows Notification Center ✓' if self.toast_notifier.available
                      else 'Windows известия недостъпни')
        checks.append(f'{len(self.monitors)} монитор(а) ✓')
        checks.append(f'{self.windows_profile.generation.replace("windows","Windows ")} / '
                      f'{self.windows_profile.language.upper()} UI ✓')
        checks.append('глобални клавиши ✓' if self.hotkeys_ok else 'глобални клавиши ✗')
        self.status.set('Готовност: '+' • '.join(checks)+
                        '. Преди екранния кадър затворете чувствителните прозорци.')

    def close_browser_async(self):
        if not self.session or not self.session.job and not self.session.pages:
            return
        job,pages=self.session.detach_browser()
        def cleanup():
            try:
                NativeSession.close_detached_browser(job,pages)
            except Exception:
                LOG.exception('Detached browser cleanup failed')
        thread=threading.Thread(target=cleanup,name='BrowserCleanup',daemon=True)
        self.cleanup_threads.append(thread); thread.start()

    def detach_session_cleanup(self):
        if self.session is None:
            return
        session,self.session=self.session,None
        generation=self.scenario.generation
        def cleanup():
            try:
                session.close()
                notice=getattr(session,'cleanup_notice','')
            except Exception as exc:
                LOG.exception('Lesson cleanup failed')
                notice='Учебната папка е запазена за преглед: '+str(session.folder)
            self.events.post('cleanup_done',(generation,notice),coalesce='cleanup_done')
        thread=threading.Thread(target=cleanup,name='SessionCleanup',daemon=True)
        self.cleanup_threads.append(thread); thread.start()

    def measure_resources(self,now):
        if now-self.last_metrics<2.0:
            return
        self.last_metrics=now
        working,available=windows_memory_snapshot()
        browser=None
        if self.session and self.session.job:
            browser=self.session.job.peak_memory_mib()
        high=((working is not None and working>256) or
              (browser is not None and browser>768) or
              (available is not None and available<512) or self.loop_delay_ms>450)
        self.pressure_samples=getattr(self,'pressure_samples',0)+(1 if high else -1)
        self.pressure_samples=max(0,min(3,self.pressure_samples))
        self.pressure=self.pressure_samples>=3
        if self.pressure:
            self.reduced_motion.set(True)
            if not self.pressure_handled:
                self.pressure_handled=True
                self.close_browser_async()
                if isinstance(self.stage,DesktopOverlay):
                    self.close_stage()
                    if self.running:
                        self.stage_mode('glitch_static')
        fmt=lambda value: 'недостъпно' if value is None else f'{value:.0f} MiB'
        self.resource_status.set(
            f'{self.profile.name}: прозорци {self.live_effect_count()}/{self.profile.max_effects}, '
            f'раздели {self.session.tabs if self.session else 0}/{self.profile.max_tabs}, '
            f'цикъл +{self.loop_delay_ms:.0f} ms, render {self.render_ms:.0f} ms, '
            f'Python {fmt(working)}, browser peak {fmt(browser)}, свободна RAM {fmt(available)}'
            + (' • НАТИСК: новите ефекти са спрени' if self.pressure else ''))

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
        # Discard events from a completed registration attempt before starting a new one.
        self.events.clear_all()
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
        if self.running:
            self.status.set('Демонстрацията вече работи. Използвайте „Повтори глава“ или „Спри / изчисти“.')
            return
        warning=('Това е контролирана учебна симулация. Ще се използват само собствени прозорци, '
                 'локални страници и осем временни учебни файла. Няма реално инсталиране, '
                 'шифроване, срив или рестартиране.\n\n'
                 'Аварийни клавиши: Ctrl+Alt+P — пауза; Ctrl+Alt+Q — незабавен изход.\n\n'
                 'Затворете чувствителните прозорци преди екранния ефект. Да започне ли?')
        if not messagebox.askokcancel('Учебна симулация — потвърждение',warning,parent=self.root):
            self.status.set('Стартирането е отменено. Нищо не е променено.')
            return
        self.closing_effects[:]=[e for e in self.closing_effects if e.thread.is_alive()]
        if self.closing_effects:
            self.status.set('Предишните native прозорци още се освобождават. Изчакайте момент и стартирайте отново.')
            return
        self.clear_effects()
        self.close_stage()
        self.sound_bank.stop()
        self.detach_session_cleanup()
        self.scenario.new_session()
        self.story=STORY_PRESETS.get(self.duration.get(),DEFAULT_STORY)
        self.timeline=list(self.story.beats)
        self.chapters=list(self.story.chapters)
        self.clock = 0.0
        self.event_index = 0
        self.mode = mode
        self.running = True
        self.paused = False
        self.native_kind=None
        self.teacher_paced=self.presentation_mode.get()=='Учителско темпо' and mode=='auto'
        self.pressure=False
        self.pressure_handled=False
        self.pressure_samples=0
        self.limiter.reset()
        self.rate = 1.0
        self._finish_branch_gate()
        self.close_tray_icon();self.toast_notifier.clear()
        self.last = time.monotonic()
        try:
            if sys.platform!='win32':
                raise RuntimeError('Тази версия работи върху истински Windows 10/11.')
            self.cleanup_notice = ''
            self.session=NativeSession(self.browser_path,self.profile.max_tabs,self.scenario.generation,
                                       self.presentation_monitor.work_rect)
            self.last_folder=self.session.folder
            self.hide_panel()
            LOG.info('Starting mode=%s, story=%s, display=%s, platform=%s/%s',
                     mode,self.story.label,self.presentation_monitor.label,
                     self.windows_profile.generation,self.windows_profile.language)
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
        if (self.paused and self.teacher_paced and self.mode=='auto' and
                self.scenario.chapter_index+1<len(self.chapters) and
                self.chapters[self.scenario.chapter_index+1][0]-self.clock<.01):
            self.next_chapter()
            return
        self.paused = not self.paused
        self.last = time.monotonic()
        if self.session:
            self.session.update(self.clock,self.paused,self.hide_on_pause.get())
        if self.paused:
            self.sound_bank.stop()
            if self.stage is not None:
                self.stage.win.attributes('-topmost', False)
                if self.hide_on_pause.get():
                    self.stage.win.withdraw()
            for effect in self.effects:
                if not effect.closed:
                    effect.set_topmost(False)
                    if self.hide_on_pause.get():
                        effect.hide()
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
                    effect.show(activate=False)
            self.resume_button.configure(text='Пауза')
        self.update_status()

    def clear_effects(self):
        for effect in self.effects:
            effect.close()
            if effect.thread.is_alive() and effect not in self.closing_effects:
                self.closing_effects.append(effect)
        self.effects.clear()

    def close_stage(self):
        if self.stage is not None:
            self.stage.close()
            self.stage = None

    def close_session(self):
        self.native_kind=None
        self.detach_session_cleanup()

    def toggle_fullscreen(self):
        self.fullscreen.set(not self.fullscreen.get())
        if self.stage is not None:
            self.stage.win.attributes('-fullscreen', self.fullscreen.get())

    def next_chapter(self):
        if not self.running or self.mode != 'auto':
            return
        self.seek_chapter(min(len(self.chapters)-1,self.scenario.chapter_index+1))

    def replay_chapter(self):
        if not self.running or self.mode!='auto':
            self.status.set('Повторението е достъпно по време на цялата история.')
            return
        self.seek_chapter(self.scenario.chapter_index)

    def seek_chapter(self,index):
        index=max(0,min(len(self.chapters)-1,index))
        target=self.chapters[index][0]
        self.paused=False
        self.sound_bank.stop()
        self._finish_branch_gate()
        self.close_tray_icon();self.toast_notifier.clear()
        self.clear_effects()
        self.close_stage()
        self.close_browser_async()
        self.native_kind=None
        completed=[beat.scene for beat in self.timeline if beat.at<target]
        issues=[]
        locked_count=0
        if self.session:
            issues=self.session.restore_files()
            if 'files_chapter' in completed and 'recovery' not in completed:
                self.session.lock_files(8)
            locked_count=sum(locked.exists() for _,locked,_ in self.session.files)
        self.scenario.rebuild_for_story(completed,index,locked_count=locked_count)
        if self.scenario.tray_visible:
            self.ensure_tray_icon()
        self.clock = target
        self.event_index = next((i for i,beat in enumerate(self.timeline) if beat.at>=target),len(self.timeline))
        try:
            self.advance(0)
        except Exception as exc:
            self.report_error('Не успях да отворя следващата глава', exc)
        self.last = time.monotonic()
        if issues:
            LOG.warning('Replay left changed lesson files untouched: %s',', '.join(issues))
            self.status.set('Някои учебни файлове са променени и не бяха презаписани: '+', '.join(issues))
            self.notify_windows(
                self.system_text('Необходим е преглед на учебните файлове','Lesson files need review'),
                self.system_text('Променен или конфликтен файл не беше презаписан.',
                                 'A changed or conflicting file was not overwritten.'))
        self.hide_panel()
        self.resume_button.configure(text='Пауза',state='normal')

    def stop(self, message='Ефектите са спрени. Работният плот е свободен.'):
        if self.closed:
            return
        self.running = self.paused = False
        self.scenario.invalidate()
        self.native_kind=None
        self.sound_bank.stop()
        self.close_tray_icon();self.toast_notifier.clear()
        self.clear_effects()
        self.close_stage()
        self.close_session()
        self.resume_button.configure(text='Продължи', state='disabled')
        self._finish_branch_gate()
        self.status.set(self.cleanup_notice or message)
        self.show_panel()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.running = False
        self.scenario.invalidate()
        if self.job is not None:
            self.root.after_cancel(self.job)
            self.job = None
        self.clear_effects()
        self.close_stage()
        self.close_tray_icon();self.toast_notifier.clear()
        self.close_session()
        self.sound_bank.close()
        self.toast_notifier.close()
        if self.hotkeys is not None:
            self.hotkeys.close()
        deadline=time.monotonic()+.75
        for effect in list(self.closing_effects):
            effect.wait_closed(max(0,min(.08,deadline-time.monotonic())))
        for thread in list(self.cleanup_threads):
            remaining=deadline-time.monotonic()
            if remaining<=0:
                break
            thread.join(timeout=min(.15,remaining))
        self.root.destroy()

    def update_status(self):
        if self.running:
            elapsed = int(self.clock)
            chapter = next(name for t, name in reversed(self.chapters) if t <= self.clock) if self.mode == 'auto' else 'Отделна сцена'
            total=self.story.duration if self.mode=='auto' else 300
            remaining=max(0,total-elapsed)
            self.status.set(f'{"ПАУЗА" if self.paused else "В ход"}  •  '
                            f'{elapsed//60:02}:{elapsed%60:02} / остава {remaining//60:02}:{remaining%60:02}  •  '
                            f'{chapter}')
            self.chapter_status.set(f'Глава {self.scenario.chapter_index+1}/{len(self.chapters)}: {chapter}  •  '
                                    f'{"учителско темпо" if self.teacher_paced else "автоматично"}')

    def tick(self):
        if self.closed:
            return
        self.job = None
        try:
            for action,payload in self.events.drain(self.EVENT_LIMIT):
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
                elif action == 'effect_error':
                    raise payload
                elif action == 'native_callback':
                    payload()
                elif action=='native_key':
                    {'stop':self.stop,'next':self.next_chapter,
                     'fullscreen':self.toggle_fullscreen}[payload]()
                elif action=='tray_open':
                    if self.running and not self.paused:
                        self.limiter.reset('effect-launch');self.spawn('helper_status')
                elif action=='tray_exit':
                    self.scenario.apply_event(ScenarioEvent.HELPER_STOPPED)
                    self.close_tray_icon()
                    if self.running:
                        self.record_student_choice('Block Runtime tray menu','stop')
                elif action=='tray_error':
                    self.status.set('Tray иконата не е достъпна; историята продължава без нея.')
                elif action=='cleanup_done':
                    generation,notice=payload
                    if generation==self.scenario.generation and notice:
                        self.cleanup_notice=notice
                        if not self.running:
                            self.status.set(notice)
            now = time.monotonic()
            self.loop_delay_ms=max(0.0,(now-self.last_tick_started)-.060)*1000
            self.last_tick_started=now
            dt, self.last = max(0, now-self.last), now
            self.advance(dt)
            if self.session:
                try:
                    self.session.update(self.clock,self.paused,self.hide_on_pause.get())
                except RuntimeError as exc:
                    self.native_kind=None;self.close_browser_async();self.browser_fallback(exc)
                if self.running and not self.paused:
                    for generation,page_index in self.session.drain_page_actions():
                        if generation==self.scenario.generation:
                            self.handle_page_action(page_index)
            self.closing_effects[:]=[e for e in self.closing_effects if e.thread.is_alive()]
            self.cleanup_threads[:]=[t for t in self.cleanup_threads if t.is_alive()]
            self.update_status()
            self.measure_resources(now)
        except Exception as exc:
            # If an effect fails, recover the controller instead of leaving overlays behind.
            self.report_error('Демонстрацията е спряна заради грешка', exc)
        if not self.closed:
            self.job = self.root.after(60, self.tick)

    def advance(self, dt):
        if not self.running or self.paused:
            return
        # Do not replay a backlog after a blocked debugger, sleep, or display reset.
        self.clock += min(dt,.25)*self.rate
        if self.mode == 'auto':
            previous=self.scenario.chapter_index
            if self.teacher_paced and previous+1<len(self.chapters):
                boundary=self.chapters[previous+1][0]
                if self.clock>=boundary:
                    self.clock=boundary-.001
                    self.paused=True
                    self.last=time.monotonic()
                    self.resume_button.configure(text='▶ Продължи')
                    self.show_panel()
                    self.update_status()
                    return
            current=retained_chapter_index(self.clock,self.chapters)
            if current!=previous:
                self.scenario.new_chapter(current)
            while self.event_index < len(self.timeline) and self.clock+1e-7 >= self.timeline[self.event_index].at:
                beat=self.timeline[self.event_index]
                name=beat.scene
                self.event_index += 1
                if name == 'finish':
                    self.stop('Историята приключи. Обсъдете видимите признаци и правилната реакция.')
                    return
                self.spawn(name)
        elif self.clock >= 300:
            self.stop('Ръчният ефект приключи след 5 минути.')
            return
        for effect in list(self.effects):
            effect.tick()
            if effect.closed and effect.thread.is_alive() and effect not in self.closing_effects:
                self.closing_effects.append(effect)
        self.effects[:] = [e for e in self.effects if not e.closed]
        if self.stage is not None and self.stage.mode=='uac_dim' and not self.effects:
            self.close_stage()
        self.advance_native()
        if self.stage is not None:
            try:
                self.stage.tick()
            except Exception as exc:
                if isinstance(self.stage,DesktopOverlay):
                    LOG.exception('Animated desktop capture failed; using static fallback')
                    self.close_stage();self.stage_mode('glitch_static')
                    self.status.set('Екранният кадър не е достъпен; показана е безопасна статична алтернатива.')
                else:
                    raise
        if not self.effects and self.stage is None and self.native_kind is None and self.mode != 'auto':
            self.stop()

    def advance_native(self):
        if not self.session or not self.native_kind:
            return
        elapsed=max(0,self.clock-self.native_born)
        if self.native_kind=='tabs':
            target=min(self.profile.max_tabs,1+int(elapsed/3.0))
            # At most one launch per UI tick, even after a delayed event loop.
            if self.session.tabs<target and self.session.browser_ready:
                try:
                    self.session.open_tab()
                except Exception as exc:
                    self.native_kind=None;self.close_browser_async();self.browser_fallback(exc)
        elif self.native_kind=='errors':
            target=min(self.profile.max_effects,1+int(elapsed/2.0))
            if self.native_count<target:
                before=self.live_effect_count()
                self.spawn('error' if self.native_count%4 else 'warning')
                if self.live_effect_count()>before:
                    self.native_count+=1
        elif self.native_kind=='files':
            count=max(0,min(8,int((elapsed-4)/3)))
            self.session.lock_files(count)
            actual=sum(locked.exists() for _,locked,_ in self.session.files)
            self.scenario.apply_event(ScenarioEvent.FILES_LOCKED,{'count':actual})

    def handle_page_action(self,index):
        scene=PAGE_ACTION_SCENES[index%len(PAGE_ACTION_SCENES)]
        LOG.info('Browser action tab=%s scene=%s', index, scene)
        self.spawn(scene)

    def effect(self, title, width, height, **kwargs):
        for item in self.effects:
            if item.closed and item.thread.is_alive() and item not in self.closing_effects:
                self.closing_effects.append(item)
        self.effects[:] = [e for e in self.effects if not e.closed]
        if self.pressure or self.live_effect_count()>=self.profile.max_effects:
            LOG.info('Effect skipped by resource budget: %s',title)
            return None
        if not self.limiter.allow('effect-launch',1.0):
            LOG.info('Effect skipped by wall-clock launch rate: %s',title)
            return None
        effect = NativeEffect(self, title, width, height, **kwargs)
        self.effects.append(effect)
        return effect

    def spawn(self, kind):
        if self.paused or not self.running:
            return
        LOG.info('Scene=%s, clock=%.2f', kind, self.clock)
        already_active=(kind=='reboot' and self.stage is not None and self.stage.mode=='reboot')
        if kind in ('browser','tabs','installer','taskmanager','errorwall','updater',
                    'protection_history','properties','network_activity','terminal_chapter',
                    'glitch','explorer','files_chapter','ransom','recovery',
                    'blue','reboot','debrief'):
            self.clear_effects()
            if not already_active:
                self.close_stage()
            self.native_kind=None
            self.native_born=self.clock
            self.native_count=0
            if self.session and kind not in ('browser','tabs'):
                self.close_browser_async()
        getattr(self, 'scene_'+kind)()
        if self.sound.get() and not already_active:
            aliases={'uac':'SystemQuestion','notification':'SystemNotification',
                     'warning':'SystemExclamation','firewall':'SystemExclamation',
                     'error':'SystemHand'}
            if kind in aliases:
                self.sound_bank.play_system(aliases[kind])
            else:
                self.sound_bank.play_scene(kind)

    def stage_mode(self, mode):
        if self.stage is None:
            if self.pressure or self.live_effect_count()>=self.profile.max_effects:
                self.status.set('Сцената е пропусната заради ресурсния профил.')
                return
            self.stage = Stage(self)
        if self.stage.mode != mode or self.stage.layout_key is None:
            self.stage.change(mode)

    def scene_browser(self):
        self.native_kind='browser'
        try:
            self.session.open_tab()
        except Exception as exc:
            self.native_kind=None;self.close_browser_async();self.browser_fallback(exc)

    def scene_tabs(self):
        self.native_kind='tabs'
        if self.session.tabs==0:
            try:
                self.session.open_tab()
            except Exception as exc:
                self.native_kind=None;self.close_browser_async();self.browser_fallback(exc)

    def browser_fallback(self,exc):
        LOG.warning('Browser scene disabled: %s',exc)
        e=self.effect('Браузърната сцена е изключена',610,280,position='center',role='dialog')
        if e is None:
            self.status.set('Браузърната сцена е изключена: '+str(exc));return
        detail=str(exc)[:300]
        def build(ui):
            ui._add_label('Браузърната изолация не е готова',28,28,550,36,16,True,'#263c50','#f3f3f3','Segoe UI')
            ui._add_label(detail+'\n\nЗащитата или организационната политика няма да бъде заобикаляна.',
                          28,78,550,105,10,False,'#4a5965','#f3f3f3','Segoe UI')
            ui._add_button('Затвори',472,211,105,34,self.guarded(e.close),True)
        e.build_async(build);e.show()

    def scene_errorwall(self):
        self.native_kind='errors'

    def scene_terminal_chapter(self):
        self.scene_terminal()

    def scene_glitch(self):
        if Image is None or self.pressure:
            self.stage_mode('glitch_static')
        elif self.live_effect_count()<self.profile.max_effects:
            self.stage=DesktopOverlay(self)

    def scene_files_chapter(self):
        self.native_kind='files'
        self.session.reveal_files()

    def scene_reboot(self):
        self.stage_mode('reboot')

    def scene_debrief(self):
        self.stage_mode('debrief')

    def scene_download(self):
        if self.scenario.download_stage=='completed':
            return
        self.scenario.apply_event(ScenarioEvent.DOWNLOAD_REQUESTED)
        e=self.effect('Downloads',470,178,bg='#ffffff',position='toast',role='toast')
        if e is None:return
        h={};state={'completed':False}
        def cancel():
            self.scenario.download_stage='cancelled';e.close()
            if self.teacher_paced:self.record_student_choice('download','cancel')
        def build(ui):
            ui._add_label('CaveDepths_Setup.exe',22,20,340,26,11,True,'#202124','#ffffff',self.windows_profile.font)
            h['detail']=ui._add_label('Starting download…',22,51,340,24,9,False,'#5f6368','#ffffff',self.windows_profile.font)
            h['bar']=ui._add_progress(22,88,360,18)
            h['percent']=ui._add_label('0%',390,84,55,25,9,False,'#5f6368','#ffffff',self.windows_profile.font)
            h['cancel']=ui._add_button('×',414,16,34,30,self.guarded(cancel),False)
            ui._add_label('Source: 127.0.0.1',22,127,260,22,9,False,'#6c7278','#ffffff',self.windows_profile.font)
        e.build_async(build);e.show(activate=False)
        def update(t):
            if state['completed'] or self.scenario.download_stage=='cancelled':return
            stops=((0,0,'Starting download…'),(1.5,11,'Connecting…'),(3.8,34,'1.8 MB of 5.4 MB'),
                   (6.4,67,'3.6 MB of 5.4 MB'),(9.1,91,'Verifying download…'),(11.2,100,'Download complete'))
            previous=stops[0]
            for item in stops:
                if t>=item[0]:previous=item
            progress=previous[1]
            upcoming=next((item for item in stops if item[0]>t),None)
            if upcoming:
                span=max(.1,upcoming[0]-previous[0])
                progress=int(previous[1]+(upcoming[1]-previous[1])*(t-previous[0])/span)
            e.set_progress(h['bar'],progress);e.set_text(h['percent'],f'{progress}%')
            e.set_text(h['detail'],previous[2])
            if progress>=100:
                state['completed']=True
                self.scenario.apply_event(ScenarioEvent.DOWNLOAD_COMPLETED)
                e.set_enabled(h['cancel'],False)
                if self.mode!='auto':
                    self.limiter.reset('effect-launch');self.spawn('uac')
        e.update_view=update

    def scene_helper(self):
        self.scenario.apply_event(ScenarioEvent.HELPER_STARTED)
        self.ensure_tray_icon()
        self.status.set('Block Runtime Host стартира и добави временна tray икона.')
        self.notify_windows('Block Runtime Host','Background update service is running.')

    def scene_helper_status(self):
        e=self.effect('Block Runtime Host',620,365,bg='#f7f8fa',position='center',role='app')
        if e is None:return
        h={}
        def stop_helper():
            e.close();self.record_student_choice('Block Runtime Host','stop')
        def open_update():
            e.close();self.limiter.reset('effect-launch');self.spawn('updater')
        def build(ui):
            ui._add_label('BLOCK RUNTIME',0,0,620,58,15,True,'#ffffff','#1767a0',self.windows_profile.font)
            ui._add_label('Runtime Host',30,82,360,34,20,True,'#253946','#f7f8fa',self.windows_profile.font)
            h['state']=ui._add_label('Status: Running in background',30,128,510,28,10,False,'#365366','#f7f8fa',self.windows_profile.font)
            ui._add_label('Component: ModUpdateHelper.exe\nInstalled for: CaveDepths\nUpdate channel: Automatic',
                          30,178,540,82,10,False,'#4e5d68','#ffffff',self.windows_profile.font)
            ui._add_button('Check for updates',30,294,145,36,self.guarded(open_update),True)
            ui._add_button('Stop service',350,294,110,36,self.guarded(stop_helper),False)
            ui._add_button('Close',472,294,110,36,self.guarded(e.close),False)
        e.build_async(build);e.show()

    def scene_explorer(self):
        if not self.session:return
        self.native_kind=None
        self.session.reveal_files()
        self.status.set('File Explorer показва само осемте временни учебни файла.')

    def scene_uac(self):
        self.stage_mode('uac_dim')
        title=self.system_text('Управление на потребителските акаунти','User Account Control')
        e=self.effect(title,650,460,
                      bg='#e9f2f7',position='center',role='dialog',topmost=True)
        if e is None:self.close_stage();return
        h={};state={'details':False}
        def decide(choice):
            e.close();self.close_stage()
            event=ScenarioEvent.UAC_APPROVED if choice=='yes' else ScenarioEvent.UAC_DECLINED
            self.scenario.apply_event(event,{'idempotency_key':f'{event.value}:{self.scenario.chapter_generation}'})
            self.record_student_choice(title,choice,'installer')
        def toggle_details():
            state['details']=not state['details']
            e.set_visible(h['details'],state['details'])
            e.set_text(h['toggle'],self.system_text(
                'Скрий подробностите' if state['details'] else 'Покажи подробности',
                'Hide details' if state['details'] else 'Show details'))
        def build(ui):
            ui._set_icon(32515)
            ui._add_label('◆',27,31,72,74,43,True,'#2f78a6','#e9f2f7','Segoe UI')
            ui._add_label(title,116,28,490,32,17,True,'#17384c','#e9f2f7',self.windows_profile.font)
            ui._add_label(self.system_text('Искате ли да разрешите на това приложение да прави промени по устройството?',
                                           'Do you want to allow this app to make changes to your device?'),
                          116,68,495,62,13,False,'#1e3645','#e9f2f7','Segoe UI')
            ui._add_label('CaveDepths Mod Setup',116,148,470,30,14,True,'#1d3341','#e9f2f7','Segoe UI')
            ui._add_label(self.system_text('Проверен издател:  Неизвестен\nПроизход:  Твърд диск на този компютър',
                                           'Verified publisher:  Unknown\nFile origin:  Hard drive on this computer'),
                          116,187,480,55,10,False,'#425967','#e9f2f7','Segoe UI')
            h['details']=ui._add_label(self.system_text(
                                        'Местоположение на програмата:\nC:\\Users\\Student\\Downloads\\CaveDepths_Setup.exe\n\nСъстояние на сертификата: Няма данни',
                                        'Program location:\nC:\\Users\\Student\\Downloads\\CaveDepths_Setup.exe\n\nCertificate status: Not available'),
                                        116,248,480,92,9,False,'#425967','#dce8ee','Consolas')
            h['toggle']=ui._add_button(self.system_text('Покажи подробности','Show details'),26,363,145,34,self.guarded(toggle_details),False)
            ui._add_button(self.system_text('Не','No'),411,363,92,34,self.guarded(lambda:decide('no')),False)
            ui._add_button(self.system_text('Да','Yes'),512,363,104,34,self.guarded(lambda:decide('yes')),True)
        e.build_async(build,lambda:e.set_visible(h['details'],False));e.limit=11;e.show()

    def scene_firewall(self):
        title=self.system_text('Предупреждение от Защитна стена на Windows','Windows Security Alert')
        e=self.effect(title,650,485,
                      bg='#f4f4f4',position='center',role='dialog')
        if e is None:return
        h={};state={'decided':False}
        def decide(choice,caption):
            if state['decided']:return
            state['decided']=True
            event=ScenarioEvent.FIREWALL_ALLOWED if choice=='allow' else ScenarioEvent.FIREWALL_BLOCKED
            self.scenario.apply_event(event,{'idempotency_key':f'firewall:{self.scenario.chapter_generation}'})
            e.set_text(h['status'],caption)
            e.set_enabled(h['allow'],False);e.set_enabled(h['cancel'],False)
            self.record_student_choice(title,choice)
        def build(ui):
            ui._set_icon(32515)
            ui._add_label('▣',24,27,70,72,39,True,'#2d6f9f','#f4f4f4','Segoe UI')
            ui._add_label(self.system_text(
                              'Защитна стена на Windows Defender блокира някои функции на това приложение',
                              'Windows Defender Firewall has blocked some features of this app'),
                          108,25,510,58,15,True,'#243746','#f4f4f4','Segoe UI')
            ui._add_label(self.system_text(
                              'Block Runtime Host поиска достъп до мрежата след инсталирането на мода.',
                              'Block Runtime Host requested network access after the mod setup.'),
                          108,88,505,42,10,False,'#4b5964','#f4f4f4','Segoe UI')
            ui._add_label(self.system_text(
                              'Име:  ModUpdateHelper.exe\nИздател:  Неизвестен\nПът:  C:\\Users\\Student\\AppData\\Local\\BlockRuntime',
                              'Name:  ModUpdateHelper.exe\nPublisher:  Unknown\nPath:  C:\\Users\\Student\\AppData\\Local\\BlockRuntime'),
                          108,145,505,75,10,False,'#273943','#ffffff','Segoe UI')
            ui._add_label(self.system_text(
                              '☑  Частни мрежи, например у дома или в училище\n☐  Публични мрежи, например на летища и в кафенета',
                              '☑  Private networks, such as home or school\n☐  Public networks, such as airports and cafés'),
                          108,241,505,66,10,False,'#364955','#f4f4f4','Segoe UI')
            h['status']=ui._add_label(self.system_text(
                                          'Изберете дали приложението може да комуникира в тези мрежи.',
                                          'Choose whether this app can communicate on these networks.'),
                                        108,319,505,35,10,False,'#7a4d16','#f4f4f4','Segoe UI')
            h['allow']=ui._add_button(self.system_text('Разреши достъп','Allow access'),340,381,150,36,
                                      self.guarded(lambda:decide('allow',self.system_text('Достъпът е разрешен','Access allowed'))),True)
            h['cancel']=ui._add_button(self.system_text('Отказ','Cancel'),500,381,112,36,
                                       self.guarded(lambda:decide('block',self.system_text('Заявката е отменена','Request cancelled'))),False)
        e.build_async(build);e.limit=24;e.show()

    def scene_taskmanager(self):
        title=self.system_text('Диспечер на задачите','Task Manager')
        e=self.effect(title,830,570,bg='#f6f6f6',
                      position='center',role='app',resizable=True)
        if e is None:return
        h={};state={'stopped':False,'last':-1}
        def end_demo_task():
            state['stopped']=True
            self.scenario.apply_event(ScenarioEvent.HELPER_STOPPED)
            self.close_tray_icon()
            e.set_text(h['status'],self.system_text('ModUpdateHelper.exe беше спрян','ModUpdateHelper.exe was stopped'))
            e.set_enabled(h['end'],False)
            self.record_student_choice(title,'stop')
        def build(ui):
            ui._add_label(self.system_text(
                              'Процеси   Производителност   Хронология   Стартиране   Потребители   Подробности   Услуги',
                              'Processes   Performance   App history   Startup apps   Users   Details   Services'),
                          18,15,790,32,10,False,'#26343e','#f6f6f6','Segoe UI')
            h['status']=ui._add_label(self.system_text('Процеси','Processes'),
                                      18,54,790,28,10,True,'#1f6d55','#f6f6f6','Segoe UI')
            h['rows']=ui._add_edit('',18,91,790,270,10,'#27323a','#ffffff')
            ui._add_label('CPU',18,384,55,24,10,True,'#334752','#f6f6f6','Segoe UI')
            h['cpu']=ui._add_progress(75,385,280,20)
            h['cpu_text']=ui._add_label('0%',365,382,72,25,10,True,'#a12d39','#f6f6f6','Segoe UI')
            ui._add_label(self.system_text('Диск','Disk'),18,420,55,24,10,True,'#334752','#f6f6f6','Segoe UI')
            h['disk']=ui._add_progress(75,421,280,20)
            h['disk_text']=ui._add_label('0%',365,418,72,25,10,True,'#9b6a1b','#f6f6f6','Segoe UI')
            h['network']=ui._add_label(self.system_text('Мрежа  0 Mbps','Network  0 Mbps'),465,385,310,55,11,True,'#334752','#f6f6f6','Segoe UI')
            h['end']=ui._add_button(self.system_text('Край на задачата','End task'),636,486,165,36,self.guarded(end_demo_task),True)
        e.build_async(build)
        def update(t):
            slot=int(t*2)
            if slot==state['last']:return
            state['last']=slot
            if state['stopped']:
                cpu,disk,network=4,2,0.0
            else:
                cpu=max(18,min(96,int(68+22*math.sin(t*.63)+8*math.sin(t*1.7))))
                disk=max(8,min(99,int(56+37*math.sin(t*.41+1.2))))
                network=max(0.1,3.8+3.3*math.sin(t*.52))
            rows=(
                'Name                              Status          CPU      Memory\r\n'
                'ModUpdateHelper.exe               Running         '
                f'{cpu:>2}%      184.6 MB\r\n'
                'BlockRuntimeHost.exe              Running          8%       72.1 MB\r\n'
                'CaveDepths Setup                  Suspended         0%       18.4 MB\r\n'
                'Browser                           4 processes      12%      318.3 MB\r\n'
                'PC Defender                       Running           5%       63.8 MB\r\n'
                'Windows Explorer                  Running           1%       96.4 MB')
            e.set_text(h['rows'],rows);e.set_progress(h['cpu'],cpu);e.set_progress(h['disk'],disk)
            e.set_text(h['cpu_text'],f'{cpu}%');e.set_text(h['disk_text'],f'{disk}%')
            e.set_text(h['network'],self.system_text(
                f'Мрежа  {network:.1f} Mbps\nGPU  {max(2,cpu//5)}%',
                f'Network  {network:.1f} Mbps\nGPU  {max(2,cpu//5)}%'))
        e.update_view=update;e.show()

    def scene_updater(self):
        e=self.effect('Block Runtime Update',650,430,
                      bg='#f7f7f7',position='center',role='app')
        if e is None:return
        h={};state={'cancelled':False,'last':-1}
        def cancel_update():
            state['cancelled']=True
            e.set_text(h['headline'],'Update cancelled')
            e.set_text(h['detail'],'The requested component was not installed.')
            e.set_enabled(h['cancel'],False)
            self.record_student_choice('Block Runtime Update','cancel')
        def build(ui):
            ui._add_label('BLOCK RUNTIME',0,0,650,58,16,True,'#ffffff','#1767a0','Segoe UI')
            h['headline']=ui._add_label('Installing required game component',35,88,580,38,20,True,'#253946','#f7f7f7','Segoe UI')
            ui._add_label('Requested by: CaveDepths Mod Setup\nPublisher: Unknown • Package: runtime_setup.exe',
                          35,140,580,55,10,False,'#52616b','#f7f7f7','Segoe UI')
            h['bar']=ui._add_progress(35,225,580,24)
            h['percent']=ui._add_label('0%',555,259,60,25,10,True,'#334854','#f7f7f7','Segoe UI')
            h['detail']=ui._add_label('Preparing package…',35,260,500,50,10,False,'#52616b','#f7f7f7','Segoe UI')
            h['cancel']=ui._add_button('Cancel',505,337,110,36,self.guarded(cancel_update),False)
        e.build_async(build)
        steps=('Preparing package…','Checking package signature…',
               'Copying runtime components…','Registering update state…','Finishing…')
        def update(t):
            if state['cancelled']:return
            progress=min(100,int(t/24*100));slot=min(len(steps)-1,progress//21)
            if progress==state['last']:return
            state['last']=progress;e.set_progress(h['bar'],progress)
            e.set_text(h['percent'],f'{progress}%');e.set_text(h['detail'],steps[slot])
            if progress>=100:
                e.set_text(h['headline'],'Block Runtime is up to date')
                e.set_text(h['detail'],'Version 4.8.12 is ready.')
                e.set_enabled(h['cancel'],False)
                self.notify_windows('Block Runtime update',
                                    'Block Runtime 4.8.12 is ready.')
        e.update_view=update;e.show()

    def scene_installer(self):
        if self.scenario.phase in ('discovery','delivery','decision'):
            self.scenario.apply_event(
                ScenarioEvent.UAC_APPROVED,
                {'idempotency_key':f'auto-uac:{self.scenario.chapter_generation}'})
        e=self.effect('CaveDepths Mod Setup',600,440,position='center',role='app')
        if e is None:return
        state={'stage':'welcome','opened':self.clock,'started':0.0,'progress':-1}
        h={}
        def cancel():
            self.scenario.apply_event(
                ScenarioEvent.INSTALL_CANCELLED,
                {'idempotency_key':f'install-cancel:{self.scenario.chapter_generation}'})
            e.close();self.record_student_choice('CaveDepths Setup','cancel','helper')
        def render_stage():
            stage=state['stage']; self.scenario.installer_stage=stage
            titles={'welcome':'Welcome to CaveDepths Mod Setup','options':'Choose setup options',
                    'installing':'Installing CaveDepths','completed':'Setup completed'}
            bodies={'welcome':'Setup will install CaveDepths and the required Block Runtime components.\nClose Minecraft before continuing.',
                    'options':'Installation type: Typical\nDestination: C:\\Users\\Student\\AppData\\Local\\CaveDepths\n\nAdditional component: Block Runtime Host',
                    'installing':'Please wait while Setup installs the selected components.',
                    'completed':'CaveDepths has been installed.\nClick Finish to close Setup.'}
            e.set_text(h['title'],titles[stage]); e.set_text(h['body'],bodies[stage])
            e.set_visible(h['bar'],stage=='installing'); e.set_visible(h['detail'],stage=='installing')
            e.set_visible(h['percent'],stage=='installing'); e.set_enabled(h['back'],stage=='options')
            e.set_visible(h['next'],stage in ('welcome','options')); e.set_visible(h['finish'],stage=='completed')
            e.set_enabled(h['cancel'],stage!='completed')
        def next_step():
            if state['stage']=='welcome':state['stage']='options'
            elif state['stage']=='options':
                state['stage']='installing'; state['started']=self.clock
                self.scenario.apply_event(
                    ScenarioEvent.INSTALL_STARTED,
                    {'idempotency_key':f'install-start:{self.scenario.chapter_generation}'})
            render_stage()
        def back():
            if state['stage']=='options':state['stage']='welcome'; render_stage()
        def build(ui):
            ui._add_label('CAVEDEPTHS',0,0,155,440,20,True,'#ffffff','#285f91','Segoe UI')
            ui._add_label('Welcome\n\nOptions\n\nInstalling\n\nComplete',22,75,115,250,10,False,'#d7e9f8','#285f91','Segoe UI')
            h['title']=ui._add_label('',182,28,385,42,20,True,'#23384d','#f3f3f3','Segoe UI')
            h['body']=ui._add_label('',182,88,382,120,11,False,'#334455','#f3f3f3','Segoe UI')
            h['bar']=ui._add_progress(182,230,382,22)
            h['detail']=ui._add_label('Preparing package…',182,264,300,27,10,False,'#626b74','#f3f3f3','Segoe UI')
            h['percent']=ui._add_label('0%',503,264,60,27,10,False,'#626b74','#f3f3f3','Segoe UI')
            ui._add_label('',155,346,445,1,9,False,'#b9b9b9','#b9b9b9','Segoe UI')
            h['back']=ui._add_button('< Back',290,370,85,34,self.guarded(back),False)
            h['next']=ui._add_button('Next >',382,370,85,34,self.guarded(next_step),True)
            h['finish']=ui._add_button('Finish',382,370,85,34,self.guarded(e.close),True)
            h['cancel']=ui._add_button('Cancel',482,370,85,34,self.guarded(cancel),False)
        e.build_async(build,render_stage);e.show()
        phases=[(0,0,'Preparing package…'),(2.1,8,'Checking compatibility…'),
                (5.2,29,'Copying Block Runtime files…'),(10.4,64,'Registering components…'),
                (15.1,88,'Creating shortcuts…'),(18.0,100,'Finishing…')]
        def update(_):
            age=max(0,self.clock-state['opened'])
            if self.mode=='auto' and state['stage']=='welcome' and age>=6:
                state['stage']='options';render_stage()
            elif self.mode=='auto' and state['stage']=='options' and age>=12:
                state['stage']='installing';state['started']=self.clock
                self.scenario.apply_event(
                    ScenarioEvent.INSTALL_STARTED,
                    {'idempotency_key':f'auto-install:{self.scenario.chapter_generation}'})
                render_stage()
            if state['stage']!='installing':return
            elapsed=max(0,self.clock-state['started']); progress=0; detail=phases[0][2]
            for start,value,text in phases:
                if elapsed>=start:progress=value;detail=text
            if elapsed<18:
                upcoming=next((p for p in phases if p[0]>elapsed),phases[-1])
                previous=max((p for p in phases if p[0]<=elapsed),key=lambda p:p[0])
                span=max(.1,upcoming[0]-previous[0])
                progress=int(previous[1]+(upcoming[1]-previous[1])*(elapsed-previous[0])/span)
            if progress!=state['progress']:
                state['progress']=progress;e.set_progress(h['bar'],progress)
                e.set_text(h['percent'],f'{progress}%');e.set_text(h['detail'],detail)
            if progress>=100:
                state['stage']='completed'
                self.scenario.apply_event(
                    ScenarioEvent.INSTALL_COMPLETED,
                    {'idempotency_key':f'install-complete:{self.scenario.chapter_generation}'})
                render_stage()
        e.update_view=update

    def scene_notification(self):
        e=self.effect('PC Defender',410,190,bg='#242424',position='toast',role='toast')
        if e is None:return
        def details():e.close();self.spawn('warning')
        def build(ui):
            ui._add_label('■',18,19,30,32,17,True,'#67b49f','#242424','Segoe UI')
            ui._add_label(self.system_text('Защита от вируси и заплахи','Virus & threat protection'),57,17,285,28,12,True,'#ffffff','#242424','Segoe UI')
            ui._add_label(time.strftime('%H:%M'),344,18,48,24,9,False,'#b9b9b9','#242424','Segoe UI')
            ui._add_label(self.system_text(
                              'Подозрителна активност от ModUpdateHelper.exe\nПрегледайте откритото поведение.',
                              'Suspicious activity from ModUpdateHelper.exe\nReview the detected behavior.'),
                          18,57,372,55,10,False,'#e2e2e2','#242424','Segoe UI')
            ui._add_button(self.system_text('Подробности','Details'),250,132,104,30,self.guarded(details),False)
            ui._add_button('×',360,132,32,30,self.guarded(e.close),False)
        e.build_async(build);e.limit=18;e.show(activate=False)
        self.notify_windows('PC Defender',self.system_text(
            'Подозрителна активност от ModUpdateHelper.exe.',
            'Suspicious activity from ModUpdateHelper.exe.'))

    def scene_warning(self):
        self.scenario.apply_event(
            ScenarioEvent.ALERT_RAISED,
            {'idempotency_key':f'alert:{self.scenario.chapter_generation}'})
        e=self.effect(self.system_text('PC Defender — Необходимо е действие','PC Defender — Action required'),
                      570,390,position='center',role='dialog')
        if e is None:return
        h={};state={'expanded':False}
        def scan():e.close();self.spawn('scanner')
        def toggle_details():
            state['expanded']=not state['expanded'];e.set_visible(h['details'],state['expanded'])
            e.set_text(h['toggle'],self.system_text(
                'Скрий подробностите' if state['expanded'] else 'Покажи подробности',
                'Hide details' if state['expanded'] else 'Show details'))
            e.resize(570,475 if state['expanded'] else 390)
        def build(ui):
            ui._set_icon(32515)
            ui._add_label('!',24,28,55,58,37,True,'#a86b17','#f3f3f3','Segoe UI')
            ui._add_label(self.system_text('Потенциално нежелан софтуер','Potentially unwanted software'),94,28,440,30,16,True,'#263747','#f3f3f3','Segoe UI')
            ui._add_label(self.system_text(
                              'Неизвестен помощен процес поиска неочаквано действие.\nПрегледайте подробностите, преди да му разрешите да продължи.',
                              'An unknown helper requested an unexpected action.\nReview the details before allowing it to continue.'),
                          94,67,440,54,10,False,'#43515f','#f3f3f3','Segoe UI')
            ui._add_label(self.system_text('Процес','Process'),25,147,90,24,10,True,'#59636c','#f3f3f3','Segoe UI')
            ui._add_label('ModUpdateHelper.exe',122,147,260,24,10,False,'#222222','#f3f3f3','Segoe UI')
            ui._add_label(self.system_text('Ниво','Severity'),25,179,90,24,10,True,'#59636c','#f3f3f3','Segoe UI')
            ui._add_label(self.system_text('Високо','High'),122,179,260,24,10,False,'#a32b37','#f3f3f3','Segoe UI')
            h['details']=ui._add_label(self.system_text(
                'Технически подробности\nИД на поведение: BRH-204\nПроизход: CaveDepths_Setup.exe\nЗасегнат компонент: BlockRuntimeHost.exe',
                'Technical details\nBehavior ID: BRH-204\nOrigin: CaveDepths_Setup.exe\nAffected component: BlockRuntimeHost.exe'),25,230,510,92,9,False,'#485866','#e7ebef','Consolas')
            h['toggle']=ui._add_button(self.system_text('Покажи подробности','Show details'),25,326,145,32,self.guarded(toggle_details),False)
            ui._add_button(self.system_text('Сканирай сега','Scan now'),303,326,125,32,self.guarded(scan),True)
            ui._add_button(self.system_text('Отхвърли','Dismiss'),438,326,97,32,self.guarded(e.close),False)
        e.build_async(build,lambda:e.set_visible(h['details'],False));e.show()

    def scene_advert(self):
        e = self.effect('Lucky Chest Rewards', 520, 390, bg='#ffffff',role='app')
        if e is None:return
        title, subtitle = self.rng.choice([
            ('ПОЗДРАВЛЕНИЯ!', 'Избрани сте за специална награда!'),
            ('КОМПЮТЪРЪТ Е БАВЕН?', 'Изтеглете нашия „ускорител“ веднага.'),
            ('БЕЗПЛАТНИ БОНУСИ!', 'Офертата изтича след броени минути.')])
        h={}
        def build(ui):
            ui._add_label('  LUCKY CHEST REWARDS  •  MEMBER OFFER',0,0,520,42,10,True,'#555555','#ededed','Segoe UI')
            ui._add_label(title,28,74,464,48,25,True,'#8523ac','#ffffff','Segoe UI')
            ui._add_label(subtitle,28,137,464,52,12,False,'#202020','#ffffff','Segoe UI')
            h['countdown']=ui._add_label('Оставащо време: 01:59',28,210,464,38,18,True,'#c02e42','#ffffff','Segoe UI')
            ui._add_button('ВЗЕМИ СЕГА',28,298,180,38,self.guarded(lambda:self.spawn('warning')),True)
            ui._add_button('Затвори',382,298,110,38,self.guarded(e.close),False)
        e.build_async(build)
        def update(t):
            n=max(0,119-int(t))
            e.set_text(h['countdown'],f'Оставащо време: {n//60:02}:{n%60:02}')
        e.update_view = update
        e.show()

    def scene_terminal(self):
        e=self.effect('Incident Response Console',830,520,bg='#0c0c0c',role='app',resizable=True)
        if e is None:return
        h={}
        def build(ui):
            h['state']=ui._add_label('OFFLINE TRACE • CASE BR-204',12,10,795,25,9,True,'#79c99e','#0c0c0c','Consolas')
            h['text']=ui._add_edit('',10,42,810,430,11,'#c6c6c6','#0c0c0c')
        e.build_async(build)
        state = {'count': -1}
        delays=[0,.35,.9,1.8,2.7,3.7,4.6,5.5,6.3,7.2,8.3,9.1,
                10.2,11.4,12.7,14.0,15.4,16.8,18.4,20.0,22.0,25.0,28.0]
        def update(t):
            count=sum(t>=delay for delay in delays)
            if count != state['count']:
                lines=TERMINAL_LINES[:count][-80:]
                e.append_edit(h['text'],'\r\n'.join(lines)+'\r\n_')
                e.set_text(h['state'],f'CONNECTED • STAGE {self.scenario.terminal_stage.upper()} • '
                           f'LOCKED {self.scenario.locked_count}/8')
                self.scenario.terminal_stage='processing' if count<len(TERMINAL_LINES) else 'complete'
                state['count'] = count
        e.update_view = update
        e.show()

    def scene_scanner(self):
        e=self.effect('PC Defender',660,470,role='app')
        if e is None:return
        h={};state={'started':self.clock,'pause_at':0.0,'paused_total':0.0,'paused':False,'stopped':False,'details':False}
        def pause_scan():
            if state['stopped'] or self.scenario.scanner_stage=='completed':return
            state['paused']=not state['paused']
            self.scenario.apply_event(ScenarioEvent.SCAN_PAUSED,{'paused':state['paused']})
            if state['paused']:state['pause_at']=self.clock
            else:state['paused_total']+=self.clock-state['pause_at']
            e.set_text(h['pause'],self.system_text(
                'Продължи' if state['paused'] else 'Пауза',
                'Resume' if state['paused'] else 'Pause'))
            e.set_text(h['status'],self.system_text(
                'Сканирането е на пауза' if state['paused'] else 'Сканиране…',
                'Scan paused' if state['paused'] else 'Scanning…'))
        def stop_scan():
            state['stopped']=True;self.scenario.apply_event(ScenarioEvent.SCAN_CANCELLED)
            e.set_text(h['status'],self.system_text('Сканирането е отменено','Scan cancelled'))
            e.set_enabled(h['pause'],False);e.set_enabled(h['stop'],False)
        def details():
            state['details']=not state['details']
            text=('\r\n'.join(self.scenario.scanner_results) if state['details'] else
                  self.system_text('Изберете „Подробности“, за да видите откритите елементи.',
                                   'Select Details to view detected items.'))
            e.append_edit(h['results'],text);e.set_text(h['details'],self.system_text(
                'Обобщение' if state['details'] else 'Подробности',
                'Summary' if state['details'] else 'Details'))
        def build(ui):
            ui._add_label('PC DEFENDER',0,0,155,470,16,True,'#eaf2f8','#294867','Segoe UI')
            ui._add_label(self.system_text('Общ преглед\n\nСистемно сканиране\n\nХронология\n\nНастройки','Overview\n\nSystem Scan\n\nHistory\n\nSettings'),20,72,115,220,10,False,'#bdd0df','#294867','Segoe UI')
            ui._add_label(self.system_text('Системно сканиране','System Scan'),182,24,430,38,22,True,'#294867','#f3f3f3','Segoe UI')
            h['status']=ui._add_label(self.system_text('Сканиране…','Scanning…'),182,70,430,28,10,False,'#526273','#f3f3f3','Segoe UI')
            h['stat']=ui._add_label(self.system_text('Проверени елементи: 0  •  0%','Items checked: 0  •  0%'),182,112,430,28,11,True,'#253a4c','#f3f3f3','Segoe UI')
            h['bar']=ui._add_progress(182,149,440,22)
            h['found']=ui._add_label(self.system_text('Открити: 0','Findings: 0'),182,190,430,32,16,True,'#a82d3e','#f3f3f3','Segoe UI')
            h['current']=ui._add_label(self.system_text('Текущ елемент: ','Current item: ')+'C:\\Users\\Student\\AppData\\Local\\BlockRuntime',182,228,440,25,9,False,'#66737d','#f3f3f3','Consolas')
            h['results']=ui._add_edit(self.system_text('Изберете „Подробности“, за да видите откритите елементи.','Select Details to view detected items.'),182,270,440,92,9,'#394957','#ffffff')
            h['pause']=ui._add_button(self.system_text('Пауза','Pause'),182,391,85,34,self.guarded(pause_scan),False)
            h['stop']=ui._add_button(self.system_text('Спри','Stop'),276,391,85,34,self.guarded(stop_scan),False)
            h['details']=ui._add_button(self.system_text('Подробности','Details'),370,391,105,34,self.guarded(details),False)
            ui._add_button(self.system_text('Затвори','Close'),527,391,95,34,self.guarded(e.close),False)
        e.build_async(build);self.scenario.apply_event(ScenarioEvent.SCAN_STARTED)
        def update(t):
            if state['stopped'] or state['paused']:return
            elapsed=max(0,self.clock-state['started']-state['paused_total']);p=min(1,elapsed/22)
            checked=int(p*2400);found=min(len(self.scenario.scanner_results),int(p*4))
            e.set_progress(h['bar'],p*100);e.set_text(h['stat'],self.system_text(
                f'Проверени елементи: {checked:,}  •  {int(p*100)}%',
                f'Items checked: {checked:,}  •  {int(p*100)}%'))
            e.set_text(h['found'],self.system_text(f'Открити: {found}',f'Findings: {found}'))
            e.set_text(h['current'],self.system_text('Текущ елемент: ','Current item: ')+f'C:\\Users\\Student\\AppData\\Local\\BlockRuntime\\cache-{checked%97:03}.dat')
            if p>=1 and self.scenario.scanner_stage!='completed':
                self.scenario.apply_event(ScenarioEvent.SCAN_COMPLETED)
                e.set_text(h['status'],self.system_text('Сканирането завърши','Scan complete'))
                e.set_enabled(h['pause'],False);e.set_enabled(h['stop'],False)
                self.notify_windows(self.system_text('Сканирането приключи','Scan completed'),
                                    self.system_text('Открити са 3 заплахи. Прегледайте хронологията на защитата.',
                                                     '3 threats were found. Review Protection history.'))
        e.update_view = update
        e.show()

    def scene_protection_history(self):
        e=self.effect(self.system_text('Защита на Windows','Windows Security'),820,555,
                      bg='#f7f7f7',position='center',role='app',resizable=True)
        if e is None:return
        h={};state={'expanded':False,'acted':False}
        def toggle():
            state['expanded']=not state['expanded']
            e.set_visible(h['details'],state['expanded'])
            e.set_text(h['toggle'],self.system_text(
                'Скрий подробностите' if state['expanded'] else 'Виж подробности',
                'Hide details' if state['expanded'] else 'See details'))
        def contain():
            if state['acted']:return
            state['acted']=True
            self.scenario.apply_event(
                ScenarioEvent.QUARANTINE_STARTED,
                {'idempotency_key':f'quarantine:{self.scenario.chapter_generation}'})
            e.set_text(h['status'],self.system_text(
                'Действията започнаха • изолиране на компонентите на Block Runtime',
                'Actions started • isolating Block Runtime components'))
            e.set_enabled(h['action'],False)
        def build(ui):
            ui._add_label('☰',20,20,38,30,17,False,'#314250','#f7f7f7','Segoe UI')
            ui._add_label(self.system_text('Защита на Windows','Windows Security'),66,18,300,32,18,True,'#25343f','#f7f7f7',self.windows_profile.font)
            ui._add_label(self.system_text(
                              'Начало\n\nЗащита от вируси и заплахи\n\nЗащита на акаунта\n\nЗащитна стена и мрежа\n\nУправление на приложения и браузър',
                              'Home\n\nVirus & threat protection\n\nAccount protection\n\nFirewall & network protection\n\nApp & browser control'),
                          24,76,205,360,10,False,'#344a5a','#edf1f4',self.windows_profile.font)
            ui._add_label(self.system_text('Хронология на защитата','Protection history'),258,74,510,40,23,True,'#223746','#f7f7f7',self.windows_profile.font)
            ui._add_label(self.system_text('Текущи заплахи','Current threats'),258,129,180,24,10,True,'#65727c','#f7f7f7',self.windows_profile.font)
            ui._add_label('!',270,174,44,44,28,True,'#b22c3b','#fff4f4','Segoe UI')
            ui._add_label(self.system_text('Открита заплаха — необходимо е действие','Threat found — action needed'),329,169,410,30,14,True,'#7f1e2b','#fff4f4',self.windows_profile.font)
            ui._add_label(self.system_text('Trojan:Win32/CaveDepthsLoader\nЗасегнати елементи: 3','Trojan:Win32/CaveDepthsLoader\nAffected items: 3'),329,204,410,48,10,False,'#394b58','#fff4f4',self.windows_profile.font)
            h['details']=ui._add_label(self.system_text(
                'Произход: CaveDepths_Setup.exe\nПроцес: ModUpdateHelper.exe\nКомпонент: BlockRuntimeHost.exe\nПоведение: неочаквана файлова и мрежова активност',
                'Origin: CaveDepths_Setup.exe\nProcess: ModUpdateHelper.exe\nComponent: BlockRuntimeHost.exe\nBehavior: unexpected file and network activity'),
                                        270,277,468,96,9,False,'#435866','#e9eef2','Consolas')
            h['status']=ui._add_label(self.system_text('Препоръчано действие: карантина','Recommended action: quarantine'),258,391,480,30,10,True,'#7f1e2b','#f7f7f7',self.windows_profile.font)
            h['toggle']=ui._add_button(self.system_text('Виж подробности','See details'),258,458,140,36,self.guarded(toggle),False)
            h['action']=ui._add_button(self.system_text('Стартирай действия','Start actions'),574,458,165,36,self.guarded(contain),True)
        e.build_async(build,lambda:e.set_visible(h['details'],False));e.show()

    def scene_properties(self):
        e=self.effect(self.system_text('Свойства на CaveDepths_Setup.exe','CaveDepths_Setup.exe Properties'),610,520,bg='#f2f2f2',
                      position='center',role='dialog')
        if e is None:return
        h={}
        def certificate():
            e.set_text(h['notice'],self.system_text(
                'Windows не може да провери издателя на този файл.',
                'Windows cannot verify the publisher of this file.'))
            e.set_enabled(h['view'],False)
        def build(ui):
            ui._add_label(self.system_text('Общи     Защита     Подробности     Цифрови подписи','General     Security     Details     Digital Signatures'),18,15,560,34,10,False,'#273746','#f2f2f2',self.windows_profile.font)
            ui._add_label(self.system_text('Цифрови подписи','Digital Signatures'),28,70,525,35,18,True,'#263c4a','#f2f2f2',self.windows_profile.font)
            ui._add_label(self.system_text('Следният списък показва подписите, свързани с този файл:','The following list shows the signatures associated with this file:'),28,112,525,42,10,False,'#43515d','#f2f2f2',self.windows_profile.font)
            ui._add_edit(self.system_text('Име на подписващия                    Алгоритъм             Времеви печат\r\n\r\nНяма цифрови подписи.','Name of signer                         Digest algorithm     Timestamp\r\n\r\nNo digital signatures are present.'),28,166,525,125,9,'#26343e','#ffffff')
            ui._add_label(self.system_text('Информация за файла','File information'),28,314,200,25,10,True,'#314655','#f2f2f2',self.windows_profile.font)
            ui._add_label(self.system_text('Тип: Приложение\nИме на продукт: CaveDepths Mod Setup\nВерсия на файла: 1.21.1.4\nИздател: Неизвестен','Type: Application\nProduct name: CaveDepths Mod Setup\nFile version: 1.21.1.4\nPublisher: Unknown'),28,345,360,96,10,False,'#3f4f5a','#f2f2f2',self.windows_profile.font)
            h['notice']=ui._add_label(self.system_text('Състояние на подписа: Няма данни','Signature status: Not available'),392,345,165,55,9,True,'#9a2634','#f2f2f2',self.windows_profile.font)
            h['view']=ui._add_button(self.system_text('Преглед на сертификата','View certificate'),371,405,180,34,self.guarded(certificate),False)
            ui._add_button('OK',382,464,78,32,self.guarded(e.close),True)
            ui._add_button(self.system_text('Отказ','Cancel'),470,464,82,32,self.guarded(e.close),False)
        e.build_async(build);e.show()

    def scene_network_activity(self):
        e=self.effect('Network Activity',900,535,bg='#f5f6f7',position='center',role='app',resizable=True)
        if e is None:return
        h={};state={'blocked':False,'last':-1}
        def block():
            if state['blocked']:return
            state['blocked']=True
            self.scenario.apply_event(
                ScenarioEvent.FIREWALL_BLOCKED,
                {'idempotency_key':f'network-block:{self.scenario.chapter_generation}'})
            e.set_text(h['status'],'Connection blocked for this incident trace')
            e.set_enabled(h['block'],False)
        def build(ui):
            ui._add_label('Network Activity',22,18,430,36,21,True,'#233744','#f5f6f7',self.windows_profile.font)
            h['status']=ui._add_label('Monitoring Block Runtime Host',22,60,600,26,10,False,'#536570','#f5f6f7',self.windows_profile.font)
            h['table']=ui._add_edit('',22,103,850,270,10,'#24323b','#ffffff')
            ui._add_label('Selected process',22,397,140,24,10,True,'#42535f','#f5f6f7',self.windows_profile.font)
            ui._add_label('ModUpdateHelper.exe   PID 4820   Publisher: Unknown',165,397,510,24,10,False,'#2d3f4a','#f5f6f7','Consolas')
            h['rate']=ui._add_label('Send 0.0 KB/s   Receive 0.0 KB/s',22,442,430,28,10,True,'#2f596f','#f5f6f7',self.windows_profile.font)
            h['block']=ui._add_button('Block connection',700,432,172,36,self.guarded(block),True)
            ui._add_label('Trace source: offline incident snapshot',22,497,400,22,9,False,'#6b7881','#f5f6f7',self.windows_profile.font)
        e.build_async(build)
        def update(t):
            slot=int(t)
            if slot==state['last']:return
            state['last']=slot
            rate=0.0 if state['blocked'] else 18.0+12.0*(.5+.5*math.sin(t*.7))
            rows=('Process                  Remote address       Protocol   State\r\n'
                  'ModUpdateHelper.exe      192.0.2.42:443       TCP        '
                  f'{"Blocked" if state["blocked"] else "Established"}\r\n'
                  'BlockRuntimeHost.exe     198.51.100.18:443    TCP        Waiting\r\n'
                  'CaveDepths_Setup.exe     —                    —          Closed')
            e.append_edit(h['table'],rows)
            e.set_text(h['rate'],f'Send {rate:.1f} KB/s   Receive {rate*2.4:.1f} KB/s')
        e.update_view=update;e.show()

    def scene_recovery(self):
        e=self.effect(self.system_text('PC Defender — Отстраняване','PC Defender — Remediation'),720,495,bg='#f6f8f9',position='center',role='app')
        if e is None:return
        self.scenario.apply_event(
            ScenarioEvent.QUARANTINE_STARTED,
            {'idempotency_key':f'recovery-quarantine:{self.scenario.chapter_generation}'})
        self.scenario.apply_event(
            ScenarioEvent.RECOVERY_STARTED,
            {'idempotency_key':f'recovery-start:{self.scenario.chapter_generation}'})
        self.close_tray_icon()
        h={};state={'started':self.clock,'restored':0,'next':0.8,'done':False,'issue':None}
        def open_folder():
            if self.session:self.session.reveal_files()
        def build(ui):
            ui._add_label('PC DEFENDER',0,0,720,60,16,True,'#ffffff','#1f6e5a',self.windows_profile.font)
            ui._add_label(self.system_text('Отстраняване на заплахи','Resolving threats'),34,88,520,38,22,True,'#223b44','#f6f8f9',self.windows_profile.font)
            h['status']=ui._add_label(self.system_text('Спиране на ModUpdateHelper.exe…','Stopping ModUpdateHelper.exe…'),34,142,630,32,11,False,'#4b5e68','#f6f8f9',self.windows_profile.font)
            h['bar']=ui._add_progress(34,194,650,24)
            h['summary']=ui._add_label(self.system_text('Заплахи под карантина: 0 / 3\nВъзстановени имена: 0 / 8','Threats quarantined: 0 / 3\nFile names restored: 0 / 8'),34,247,650,70,13,True,'#245848','#ffffff',self.windows_profile.font)
            h['detail']=ui._add_label(self.system_text('Подготовка за възстановяване…','Preparing recovery…'),34,338,650,42,10,False,'#536670','#f6f8f9',self.windows_profile.font)
            h['folder']=ui._add_button(self.system_text('Отвори възстановените файлове','Open recovered files'),34,422,235,36,self.guarded(open_folder),False)
            h['close']=ui._add_button(self.system_text('Затвори','Close'),584,422,100,36,self.guarded(e.close),True)
            e.set_enabled(h['folder'],False);e.set_enabled(h['close'],False)
        e.build_async(build)
        def update(_t):
            if state['done']:return
            elapsed=max(0,self.clock-state['started'])
            if elapsed<2:
                e.set_progress(h['bar'],10+elapsed*10);return
            if elapsed>=state['next']+2 and self.session:
                restored,name=self.session.restore_next_file();state['next']+=1.05
                if restored is True:
                    state['restored']+=1;e.set_text(h['detail'],self.system_text('Възстановен: ','Restored: ')+name)
                elif restored is False:
                    state['issue']=name;state['done']=True
                    e.set_text(h['status'],self.system_text('Възстановяването е спряно — файлът е променен','Recovery paused — file changed'))
                    e.set_text(h['detail'],self.system_text(
                        'Необходим е преглед; няма презаписани данни: ',
                        'Needs inspection; no data was overwritten: ')+str(name))
                    e.set_enabled(h['folder'],True);e.set_enabled(h['close'],True)
            locked=(sum(locked.exists() for _,locked,_ in self.session.files)
                    if self.session else self.scenario.locked_count)
            self.scenario.apply_event(ScenarioEvent.FILES_LOCKED,{'count':locked})
            quarantined=min(3,max(1,int(elapsed//2)))
            progress=min(96,25+quarantined*12+state['restored']*5)
            e.set_progress(h['bar'],progress)
            e.set_text(h['summary'],self.system_text(
                f'Заплахи под карантина: {quarantined} / 3\nВъзстановени имена: {state["restored"]} / 8',
                f'Threats quarantined: {quarantined} / 3\nFile names restored: {state["restored"]} / 8'))
            if not state['done'] and locked==0 and elapsed>=7:
                state['done']=True;e.set_progress(h['bar'],100)
                self.scenario.apply_event(
                    ScenarioEvent.RECOVERY_COMPLETED,
                    {'idempotency_key':f'recovery-complete:{self.scenario.chapter_generation}'})
                e.set_text(h['status'],self.system_text('Отстраняването завърши','Remediation completed'))
                e.set_text(h['detail'],self.system_text('Няма останали активни компоненти на Block Runtime.','No active Block Runtime components remain.'))
                e.set_enabled(h['folder'],True);e.set_enabled(h['close'],True)
                self.notify_windows('PC Defender',self.system_text(
                    'Отстраняването завърши. 3 заплахи са поставени под карантина.',
                    'Remediation completed. 3 threats were quarantined.'))
        e.update_view=update;e.show()

    def scene_error(self):
        variants=[
            ('Block Runtime Host',520,255,32513,'ModUpdateHelper.exe is not responding.','Windows can wait for the program to respond or close it.','Wait for the program','Close the program'),
            ('CaveDepths',500,235,32515,'CaveDepths cannot start.','Required component block_runtime.dll was not found.','OK',None),
            ('Block Runtime Host',470,245,32513,'The requested operation was denied.','Process: BlockRuntimeHost.exe\nError code: 0x80070005','Close',None),
            ('Block Runtime Update',550,270,32515,'The update was not completed.','The package signature is invalid or cannot be verified.','Retry','Cancel')]
        index=getattr(self,'error_sequence',0)%len(variants);self.error_sequence=index+1
        title,width,height,icon,headline,body,primary,secondary=variants[index]
        e=self.effect(title,width,height,position='random',role='dialog')
        if e is None:return
        def build(ui):
            ui._set_icon(icon)
            ui._add_label('×' if icon==32513 else '!',22,28,58,58,36,True,'#b62435' if icon==32513 else '#a86b17','#f3f3f3','Segoe UI')
            ui._add_label(headline,92,27,width-120,35,12,True,'#273746','#f3f3f3','Segoe UI')
            ui._add_label(body,92,76,width-120,70,10,False,'#46535f','#f3f3f3','Segoe UI')
            if secondary:
                ui._add_button(secondary,width-230,height-62,96,34,self.guarded(e.close),False)
            ui._add_button(primary,width-124,height-62,96,34,self.guarded(e.close),True)
        e.build_async(build);e.show()

    def scene_ransom(self):
        e=self.effect('Wana Decrypt0r 2.0',930,620,bg='#f0eee9',position='center',role='app',resizable=True)
        if e is None:return
        h={};state={'notice':'Recovery key status: not found.'}
        def check_key():
            state['notice']='The recovery service is unavailable. Try again later.';e.set_text(h['notice'],state['notice'])
        def build(ui):
            ui._add_label('WANA\nDECRYPT0R 2.0',0,0,215,620,16,True,'#ffffff','#7a0f20','Segoe UI')
            ui._add_label('PAYMENT DEADLINE',25,118,165,24,9,True,'#edc86d','#7a0f20','Segoe UI')
            h['timer']=ui._add_label('05:00',25,148,165,55,31,True,'#ffffff','#7a0f20','Consolas')
            ui._add_label('FILES MARKED .locked',25,245,165,30,9,True,'#edc86d','#7a0f20','Segoe UI')
            h['locked']=ui._add_label(f'{self.scenario.locked_count} / 8',25,280,165,45,23,True,'#ffffff','#7a0f20','Segoe UI')
            ui._add_label('Ooops, your files have been “encrypted”!',248,24,640,42,23,True,'#781323','#f0eee9','Segoe UI')
            h['text']=ui._add_edit('What happened to my computer?\r\n\r\nYour important files are no longer available. Do not rename or move the affected files.\r\n\r\nCan I recover my files?\r\n\r\nA recovery key is required. The key service is currently unavailable.\r\n\r\nCase ID: CASE-2026-NONPAYABLE\r\nPayment service: unavailable',248,84,640,330,10,'#30343a','#ffffff')
            h['notice']=ui._add_label(state['notice'],248,435,640,52,10,False,'#6f2631','#f0eee9','Segoe UI')
            ui._add_button('Check recovery status',248,519,176,38,self.guarded(check_key),False)
            ui._add_button('Close',760,519,128,38,self.guarded(e.close),True)
        e.build_async(build)
        def update(t):
            remaining=max(0,300-int(t));e.set_text(h['timer'],f'{remaining//60:02}:{remaining%60:02}')
            locked=sum(locked.exists() for _,locked,_ in self.session.files) if self.session else self.scenario.locked_count
            if locked!=self.scenario.locked_count:self.scenario.locked_count=locked;e.set_text(h['locked'],f'{locked} / 8')
        e.update_view=update;e.show()

    def scene_blue(self):
        self.stage_mode('blue')


class Stage:
    """Only the ransom/crash/reboot and explanatory scenes use a full screen.
    There is deliberately no painted desktop or browser in this version.
    """

    def __init__(self, app):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.withdraw()
        self.win.title('Windows')
        left,top,right,bottom=app.presentation_monitor.monitor_rect
        work_left,work_top,work_right,work_bottom=app.presentation_monitor.work_rect
        if app.fullscreen.get():
            self.win.geometry(f'{right-left}x{bottom-top}+{left}+{top}')
        else:
            width,height=min(1400,work_right-work_left-40),min(850,work_bottom-work_top-40)
            self.win.geometry(f'{width}x{height}+{work_left+(work_right-work_left-width)//2}+{work_top+(work_bottom-work_top-height)//2}')
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
        self.items={}
        self.layout_key=None
        self.content_phase=None
        self.recovery_notice = ''
        self.canvas.bind('<Configure>',lambda event:self.invalidate())
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
        self.win.attributes('-alpha',.62 if mode=='uac_dim' else 1.0)
        self.born = self.app.clock
        self.elapsed = 0
        self.recovery_notice = ''
        self.content_phase=None
        self.invalidate()
        self.win.lift()
        self.render()

    def tick(self):
        self.elapsed = max(0, self.app.clock-self.born)
        self.render()
        # Complete the visual sequence inside our own window. Windows is never
        # crashed or restarted; the transition only changes the Stage layout.
        if self.mode=='blue' and self.elapsed>=19.0:
            self.change('reboot')
            if self.app.sound.get():
                self.app.sound_bank.play('reboot')
        elif self.mode=='reboot' and self.elapsed>=22.0 and self.app.mode!='auto':
            self.app.stop('Фалшивият restart приключи. Windows не е бил рестартиран.')

    def invalidate(self):
        self.layout_key=None

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

    def demo_matrix(self, x, y, module=7):
        """Decorative, deliberately non-scannable QR-like BSOD element."""
        cells=17
        self.rect(x-8,y-8,cells*module+16,cells*module+16,'white')
        def finder(row,column,origin_row,origin_column):
            dy,dx=row-origin_row,column-origin_column
            if not (0<=dy<5 and 0<=dx<5):
                return False
            return dy in (0,4) or dx in (0,4) or (1<dy<4 and 1<dx<4)
        for row in range(cells):
            for column in range(cells):
                marked=(finder(row,column,0,0) or finder(row,column,0,12) or
                        finder(row,column,12,0) or
                        ((row*11+column*7+row*column*3)%13 in (0,2,5)))
                if marked:
                    self.rect(x+column*module,y+row*module,module,module,'#0078d7')

    def render(self):
        self.sx = max(1,self.canvas.winfo_width())/1600
        self.sy = max(1,self.canvas.winfo_height())/900
        self.scale = min(self.sx,self.sy)
        layout=(self.mode,self.canvas.winfo_width(),self.canvas.winfo_height())
        if self.layout_key==layout:
            self.update_dynamic()
            return
        self.layout_key=layout
        self.canvas.delete('all')
        self.buttons = []
        self.items={}
        renderer = {'ransom':self.ransom, 'blue':self.blue, 'reboot':self.reboot,
                    'debrief':self.debrief,
                    'glitch_static':self.glitch_static,'uac_dim':self.uac_dim}[self.mode]
        renderer()
        self.update_dynamic()

    def update_dynamic(self):
        if self.mode=='blue' and 'progress' in self.items:
            value=min(100,int(self.elapsed*100/17.5))
            self.canvas.itemconfigure(self.items['progress'],text=f'{value}% complete')
        elif self.mode=='reboot':
            phase=0 if self.elapsed<7 else (1 if self.elapsed<9 else (2 if self.elapsed<15 else 3))
            if self.content_phase is None:
                self.content_phase=phase
            elif phase!=self.content_phase:
                self.content_phase=phase;self.invalidate();self.render();return
            if self.items.get('dots') and not self.app.reduced_motion.get():
                for i,item in enumerate(self.items['dots']):
                    angle=self.elapsed*1.7+i*math.pi/4
                    x=(795+28*math.cos(angle))*self.sx;y=(498+28*math.sin(angle))*self.sy
                    self.canvas.coords(item,x,y,x+7*self.sx,y+7*self.sy)
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

    def uac_dim(self):
        self.rect(0,0,1600,900,'#111820')

    def glitch_static(self):
        self.rect(0,0,1600,900,'#152536')
        self.text(185,190,'ЕКРАНЕН ЕФЕКТ — СТАТИЧНА АЛТЕРНАТИВА',38,'#dceaf4',True,width=1240)
        self.text(188,290,'Анимираният кадър е пропуснат поради липсващ Pillow или активна ресурсна защита.',
                  27,'#a9c0d1',width=1200)
        self.text(188,390,'Оригиналният работен плот не е променен.\nНяма повторно заснемане и няма запис на изображение.',
                  25,'#dceaf4',width=1200)

    def set_recovery_notice(self):
        self.recovery_notice='Recovery service unavailable. Няма реална операция.'

    def blue(self):
        self.rect(0,0,1600,900,'#0078d7')
        self.text(218,72,':(',126,'white',family='Segoe UI Light')
        self.text(224,252,'Your device ran into a problem and needs to restart.',36,'white',width=1160)
        self.text(225,326,"We're just collecting some error info, and then we'll restart for you.",
                  27,'white',width=1120)
        value=min(100,int(self.elapsed*100/17.5))
        self.items['progress']=self.text(225,408,f'{value}% complete',26,'white')
        self.demo_matrix(226,536,7)
        self.text(380,538,'For more information about this issue and possible fixes, visit\n'
                  'https://www.windows.com/stopcode\n\n'
                  'If you call a support person, give them this info:\n'
                  'Stop code: CRITICAL_PROCESS_DIED',19,'white',width=900)
        self.text(226,747,'The displayed code is decorative and does not open a website.',15,'#d8efff',width=950)

    def reboot(self):
        phase=0 if self.elapsed<7 else (1 if self.elapsed<9 else (2 if self.elapsed<15 else 3))
        background='#0067b8' if phase==3 else '#050505'
        self.rect(0,0,1600,900,background)
        if phase==1:
            return
        logo_color='white' if phase==3 else '#dcecff'
        for i in range(4):
            self.rect(746+(i%2)*57,253+(i//2)*57,49,49,logo_color)
        self.items['dots']=[]
        dot_colors=['#f5f8fb','#d9e0e7','#b8c1ca','#929da8','#6d7883','#4d5660','#343b42','#20252a']
        for i in range(8):
            angle=self.elapsed*1.7+i*math.pi/4
            self.items['dots'].append(self.oval(795+28*math.cos(angle),500+28*math.sin(angle),7,7,
                                                   dot_colors[i]))
        if phase==0:
            self.text(708,567,'Restarting',28,'#f2f2f2')
        elif phase==2:
            self.text(646,566,'Getting Windows ready',27,'#f2f2f2',width=420)
            self.text(650,615,"Don't turn off your computer",19,'#bfc8d1',width=400)
        else:
            self.text(735,566,'Welcome',28,'white')
            self.text(641,615,'Loading the classroom demonstration…',18,'#d8efff',width=500)

    def debrief(self):
        self.rect(0,0,1600,900,'#0a1826')
        self.text(71,62,'ЕДНАКВА ДУМА „ЗАРАЗА“. РАЗЛИЧНИ ЦЕЛИ.',40,'white',True)
        cards=[(71,'РЕКЛАМИ И ИЗМАМИ','#b190ce',
                'Натиск да щракнеш,\nда инсталираш или да платиш.',
                'Красивият сайт и тревожният\nпрозорец не доказват надеждност.'),
               (581,'WANNACRY / РАНСЪМУЕР','#e399a6',
                'Заключва файлове\nи изисква откуп.',
                'Обещанието за ключ\nне гарантира възстановяване.'),
               (1091,'ФАЛШИВИ UPDATE-И','#83cbb9',
                'Искат нов компонент\nили „ускорител“ за играта.',
                'Проверявай източника, файла\nи цифровия подпис.')]
        for x,title,color,body,note in cards:
            self.rect(x,181,440,413,'#142a3d')
            self.rect(x,181,440,6,color)
            self.text(x+25,216,title,21,color,True,width=390)
            self.text(x+25,282,body,29,'#e9f2fa',True,width=386)
            self.text(x+25,439,note,22,'#8facbf',width=385)
        self.text(78,649,'Екранните изкривявания и синият екран бяха визуални ефекти.',27,'#bacdde')
        self.text(78,698,'По тях сами по себе си не се поставя диагноза за вирус.',25,'#8facbf')
        self.button(80,785,358,64,'Към контролния панел',self.app.stop,'#226555',size=22)


class ScreenFrames:
    """Pure, bounded image transforms. No filesystem, network or Windows writes."""
    MODES = {'Разкъсване': 'tear', 'Разтичане': 'melt', 'Безкраен екран': 'tunnel'}

    def __init__(self, snapshot, target=(960,540)):
        self.original = snapshot.convert('RGB')
        # Keep expensive transforms bounded. DesktopOverlay scales the finished
        # frame to the real canvas only at presentation time.
        self.original.thumbnail(target, Image.Resampling.LANCZOS)
        self.width, self.height = self.original.size
        self.tunnel_levels = []
        if self.width < 2 or self.height < 2:
            raise RuntimeError('Windows върна празно изображение на екрана.')

    def frame(self, elapsed, selection='Смесени ефекти'):
        elapsed = max(0.0, elapsed)
        phase = elapsed % 12.0
        if selection=='Статичен кадър':
            return self.original.copy()
        mode=self.MODES.get(selection)
        if mode is None:
            mode='tear' if phase<7 else ('melt' if phase<9.5 else 'tunnel')
        # Recognizable start, localized sequence, and explicit recovery.
        mix=min(1.0,phase/2.2,(12.0-phase)/2.0)
        if mix <= 0:
            return self.original.copy()
        changed = getattr(self, mode)(phase)
        return Image.blend(self.original, changed, max(0.0, mix))

    @staticmethod
    def present(frame, size):
        """Scale one bounded working frame to the complete visible canvas."""
        width, height = max(2, int(size[0])), max(2, int(size[1]))
        return frame.resize((width, height), Image.Resampling.BILINEAR)

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
        stripe = max(9, w//48)
        progress = min(.22, t/45.0)
        for i, x in enumerate(range(0, w, stripe)):
            right = min(w, x+stripe)
            speed = .12 + .88*(.5+.5*math.sin(i*1.217+math.sin(i*.27)))
            offset = min(h-1, int(h*progress*speed))
            if offset:
                band = self.original.crop((x, 0, right, h))
                shifted = ImageChops.offset(band, 0, offset)
                try:
                    result.paste(shifted, (x, 0))
                finally:
                    shifted.close()
                    band.close()
        # Keep the desktop recognizable instead of replacing large areas with
        # stretched pixels from the dark top edge of the screenshot.
        return Image.blend(self.original, result, .78)

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
            left,top,right,bottom=app.presentation_monitor.monitor_rect
            work_left,work_top,work_right,work_bottom=app.presentation_monitor.work_rect
            self.display_size = ((right-left,bottom-top) if app.fullscreen.get()
                                 else (min(1400,work_right-work_left-60),
                                       min(850,work_bottom-work_top-60)))
            x=left if app.fullscreen.get() else work_left+25
            y=top if app.fullscreen.get() else work_top+25
            self.win.geometry(f'{self.display_size[0]}x{self.display_size[1]}+{x}+{y}')
            self.win.configure(bg='#101015')
            self.win.attributes('-fullscreen', app.fullscreen.get())
            self.win.attributes('-topmost', True)
            self.win.protocol('WM_DELETE_WINDOW', app.stop)
            self.canvas = tk.Canvas(self.win, bg='#101015', highlightthickness=0)
            self.canvas.pack(fill='both', expand=True)
            self.canvas.bind('<Configure>', self._on_configure)
        except Exception:
            self.close()
            raise

    def _on_configure(self, event):
        if event.width > 1 and event.height > 1:
            size = (event.width, event.height)
            if size != self.display_size:
                self.display_size = size
                self.next_frame = 0.0

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
                snapshot = ImageGrab.grab(bbox=self.app.presentation_monitor.monitor_rect,
                                          all_screens=True,include_layered_windows=True)
            except Exception as exc:
                raise RuntimeError('Не мога да заснема избрания монитор за ефекта. '
                                   'Проверете дали работите в отворена Windows сесия. '
                                   'Подробностите са в журнала.') from exc
            try:
                self.frames = ScreenFrames(snapshot,self.app.profile.image_size)
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
        display = frame
        try:
            width = self.canvas.winfo_width()
            height = self.canvas.winfo_height()
            size = ((width, height) if width > 1 and height > 1 else self.display_size)
            if frame.size != size:
                display = self.frames.present(frame, size)
            photo = ImageTk.PhotoImage(display, master=self.win)
        finally:
            # PhotoImage has copied the pixels into Tcl; release the per-frame PIL
            # buffer immediately instead of waiting for garbage collection.
            if display is not frame:
                display.close()
            frame.close()
        self.photo = photo
        if self.image_item is None:
            self.image_item = self.canvas.create_image(self.canvas.winfo_width()/2,self.canvas.winfo_height()/2,
                                                        anchor='center',image=self.photo)
        else:
            self.canvas.itemconfigure(self.image_item, image=self.photo)
            self.canvas.coords(self.image_item,self.canvas.winfo_width()/2,self.canvas.winfo_height()/2)
        self.app.render_ms=(time.monotonic()-started)*1000
        fps=2 if self.app.reduced_motion.get() else self.app.profile.visual_fps
        if self.app.visual_mode.get()=='Статичен кадър' or self.app.pressure:
            fps=.2
        self.next_frame = max(started + 1/fps, time.monotonic() + .01)

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
