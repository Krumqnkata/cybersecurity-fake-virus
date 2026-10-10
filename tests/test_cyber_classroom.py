import json
import contextlib
import io
import os
from pathlib import Path
import queue
import random
import shutil
import sys
import threading
import time
import tempfile
import unittest
import urllib.error
import urllib.request
import wave

import cyber_classroom as classroom
from classroom_core import (
    ABSOLUTE_MAX_EFFECTS, ABSOLUTE_MAX_TABS, BoundedEventBus, PauseClock,
    PROFILES, RateLimiter, ScenarioState, retained_chapter_index,
)


class LocalPagesTests(unittest.TestCase):
    def setUp(self):
        self.pages = classroom.LocalPages(generation=7, max_tabs=4)

    def tearDown(self):
        self.pages.close()

    def test_serves_only_tokenized_local_pages_and_state(self):
        with urllib.request.urlopen(self.pages.url(0), timeout=3) as response:
            html = response.read().decode('utf-8')
            self.assertEqual(response.status, 200)
            self.assertIn('BLOCKFORGE MODS', html)
            self.assertIn('Minecraft Java Edition', html)
            self.assertIn('CaveDepths_Setup.exe', html)
            self.assertIn("default-src 'none'", response.headers['Content-Security-Policy'])
            self.assertNotIn('https://', html)

        state_url = (f'http://127.0.0.1:{self.pages.server.server_port}/'
                     f'{self.pages.token}/state')
        with urllib.request.urlopen(state_url, timeout=3) as response:
            state=json.loads(response.read())
        self.assertEqual((state['time'],state['paused'],state['tabs']),(0,False,0))
        self.assertEqual(state['generation'],7)

        bad_url = f'http://127.0.0.1:{self.pages.server.server_port}/state'
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(bad_url, timeout=3)
        self.assertEqual(caught.exception.code, 404)

    def test_six_pages_are_authored_as_distinct_layouts(self):
        pages=[self.pages.page(index) for index in range(6)]
        story_markers=('CaveDepths','LUCKY CHEST REWARDS','37 заплахи',
                       'GAMEHUB ACCOUNT','Block Runtime','240 FPS')
        titles=[]
        for html,marker in zip(pages,story_markers):
            start=html.index('<title>')+7
            titles.append(html[start:html.index('</title>',start)])
            self.assertIn('Локал',html)
            self.assertIn('/action/',html)
            self.assertIn(marker,html)
        self.assertEqual(len(set(titles)),6)
        self.assertEqual(len(set(pages)),6)

    def test_page_actions_are_generation_tagged_and_rate_limited(self):
        request = urllib.request.Request(self.pages.action_url(2), data=b'', method='POST')
        with urllib.request.urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 202)
            self.assertEqual(json.loads(response.read()), {'accepted': True})
        self.assertEqual(self.pages.drain_actions(), [(7,2)])

        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(caught.exception.code,429)

        invalid=urllib.request.Request(self.pages.action_url(3),data=b'x',method='POST')
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(invalid,timeout=3)
        self.assertEqual(caught.exception.code,404)

    def test_expected_browser_disconnect_does_not_print_a_traceback(self):
        output=io.StringIO()
        with contextlib.redirect_stderr(output):
            try:
                raise ConnectionResetError(10054,'browser tab closed')
            except ConnectionResetError:
                self.pages.server.handle_error(None,('127.0.0.1',12345))
        self.assertEqual(output.getvalue(),'')


class SoundBankTests(unittest.TestCase):
    def test_generated_wav_and_exact_name_custom_override(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);custom=root/'custom';cache=root/'cache';custom.mkdir()
            bank=classroom.SoundBank(custom_dir=custom,cache_dir=cache)
            try:
                generated=bank.prepare('installer')
                self.assertTrue(generated.is_file())
                with wave.open(str(generated),'rb') as audio:
                    self.assertEqual((audio.getnchannels(),audio.getsampwidth(),audio.getframerate()),
                                     (1,2,classroom.SoundBank.RATE))
                    self.assertGreater(audio.getnframes(),1000)
                    self.assertLess(audio.getnframes(),classroom.SoundBank.RATE*2)

                override=custom/'browser.wav'
                with wave.open(str(override),'wb') as audio:
                    audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(8000)
                    audio.writeframes(b'\0\0'*16)
                self.assertEqual(bank.prepare('browser'),override)
                self.assertTrue(set(classroom.SoundBank.SCENES.values()) <= set(classroom.SoundBank.CUES))
            finally:
                bank.close()
        bundled=Path(classroom.__file__).resolve().parent/'sounds'
        for cue in classroom.SoundBank.CUES:
            with self.subTest(cue=cue):
                path=bundled/f'{cue}.wav'
                self.assertTrue(path.is_file())
                with wave.open(str(path),'rb') as audio:
                    self.assertEqual(audio.getframerate(),classroom.SoundBank.RATE)
                    self.assertGreater(audio.getnframes(),0)


class ReliabilityPrimitiveTests(unittest.TestCase):
    def test_profiles_and_absolute_caps(self):
        self.assertEqual(PROFILES['Училищен безопасен'].max_tabs,4)
        self.assertEqual(PROFILES['Училищен безопасен'].max_effects,6)
        self.assertEqual(PROFILES['Училищен безопасен'].image_size,(960,540))
        self.assertLessEqual(PROFILES['Балансиран'].max_tabs,ABSOLUTE_MAX_TABS)
        self.assertLessEqual(PROFILES['Балансиран'].max_effects,ABSOLUTE_MAX_EFFECTS)

    def test_event_bus_is_nonblocking_coalesced_bounded_and_prioritized(self):
        bus=BoundedEventBus(maxsize=2)
        self.assertTrue(bus.post('a',1))
        self.assertTrue(bus.post('b',2))
        self.assertFalse(bus.post('c',3))
        bus.post('paint',1,coalesce='paint')
        bus.post('paint',2,coalesce='paint')
        bus.post('quit',None,priority=True)
        events=bus.drain(limit=3)
        self.assertEqual(events[0][0],'quit')
        self.assertIn(('paint',2),events)
        self.assertEqual(bus.dropped,1)

    def test_wall_clock_rate_limiter(self):
        now=[10.0]
        limiter=RateLimiter(lambda:now[0])
        self.assertTrue(limiter.allow('effect',1.0))
        now[0]=10.9;self.assertFalse(limiter.allow('effect',1.0))
        now[0]=11.0;self.assertTrue(limiter.allow('effect',1.0))
        self.assertTrue(limiter.allow('browser',3.0))

    def test_pause_clock_does_not_catch_up(self):
        now=[0.0];clock=PauseClock(lambda:now[0]);clock.reset(False)
        now[0]=2.0;self.assertEqual(clock.update(),2.0)
        clock.set_paused(True);now[0]=100.0;self.assertEqual(clock.update(),2.0)
        clock.set_paused(False);now[0]=101.0;self.assertEqual(clock.update(),3.0)

    def test_generation_rejects_stale_callbacks(self):
        state=ScenarioState();generation=state.new_session();_,chapter=state.new_chapter(2)
        self.assertTrue(state.accepts(generation,chapter))
        state.new_chapter(3);self.assertFalse(state.accepts(generation,chapter))
        state.invalidate();self.assertFalse(state.accepts(generation))

    def test_chapter_index_supports_skipping(self):
        self.assertEqual(retained_chapter_index(0,classroom.CHAPTERS),0)
        self.assertEqual(retained_chapter_index(255,classroom.CHAPTERS),6)
        self.assertEqual(retained_chapter_index(999,classroom.CHAPTERS),len(classroom.CHAPTERS)-1)


class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = classroom.NativeSession(max_tabs=2,generation=3)

    def tearDown(self):
        shutil.rmtree(self.session.root, ignore_errors=True)

    def test_manifest_has_exactly_eight_real_text_files(self):
        self.assertEqual(len(self.session.files),8)
        self.assertEqual(len(self.session.manifest),8)
        self.assertTrue(all(plain.suffix=='.txt' for plain,_,_ in self.session.files))
        self.assertEqual(len(list(self.session.folder.iterdir())),8)

    def test_locks_and_restores_only_generated_files(self):
        extra = self.session.folder / 'Добавен_от_учителя.txt'
        extra.write_text('Не трябва да се променя.', encoding='utf-8')
        self.session.lock_files(8)
        self.assertEqual(sum(path.name.endswith('.locked') for path in self.session.folder.iterdir()),8)
        self.assertEqual(self.session.restore_files(),[])
        self.assertEqual(extra.read_text(encoding='utf-8'),'Не трябва да се променя.')

    def test_restore_never_overwrites_a_conflict(self):
        plain,locked,_=self.session.files[0]
        self.session.lock_files(1)
        plain.write_text('Учителски конфликт',encoding='utf-8')
        issues=self.session.restore_files()
        self.assertIn(locked.name,issues)
        self.assertEqual(plain.read_text(encoding='utf-8'),'Учителски конфликт')
        self.assertTrue(locked.exists())

    def test_reports_a_generated_file_that_was_removed(self):
        plain, locked, _ = self.session.files[0]
        self.session.lock_files(1);locked.unlink()
        self.assertIn(plain.name,self.session.restore_files())

    def test_browser_tab_cap_and_three_second_launch_limit(self):
        class FakeJob:
            def __init__(self):self.launches=[];self.closed=False
            def launch(self,exe,args):self.launches.append((exe,args))
            def close(self):self.closed=True
        class FakePages:
            def url(self,index):return f'http://127.0.0.1/local/{index}'
            def close(self):pass
        self.session.executable=Path('C:/fake/msedge.exe')
        self.session.job=FakeJob();self.session.pages=FakePages();self.session.browser_ready=True
        self.assertTrue(self.session.open_tab())
        self.assertFalse(self.session.open_tab())
        self.session.last_browser_launch-=3.1
        self.assertTrue(self.session.open_tab())
        self.session.last_browser_launch-=3.1
        self.assertFalse(self.session.open_tab())
        self.assertEqual(len(self.session.job.launches),2)

    def test_close_browser_only_closes_owned_objects_and_resets_state(self):
        class Owned:
            def __init__(self):self.closed=False
            def close(self):self.closed=True
        job,pages=Owned(),Owned();unrelated=Owned()
        self.session.job=job;self.session.pages=pages;self.session.tabs=2;self.session.browser_ready=True
        self.session.close_browser();self.session.close_browser()
        self.assertTrue(job.closed);self.assertTrue(pages.closed);self.assertFalse(unrelated.closed)
        self.assertEqual(self.session.tabs,0);self.assertFalse(self.session.browser_ready)


class ControllerRuleTests(unittest.TestCase):
    def test_duplicate_start_is_idempotent(self):
        class Status:
            def __init__(self):self.value=''
            def set(self,value):self.value=value
        fake=type('Fake',(),{'hotkeys_ok':True,'running':True,'status':Status()})()
        classroom.Classroom.start(fake,'auto')
        self.assertIn('вече работи',fake.status.value)

    def test_resource_cap_rejects_new_window_without_closing_old_one(self):
        profile=PROFILES['Училищен безопасен']
        fake=type('Fake',(),{})()
        fake.effects=[];fake.pressure=False;fake.profile=profile
        fake.live_effect_count=lambda:profile.max_effects
        fake.limiter=RateLimiter(lambda:10.0)
        result=classroom.Classroom.effect(fake,'blocked',400,300)
        self.assertIsNone(result);self.assertEqual(fake.effects,[])

    def test_guarded_action_is_idempotently_rejected_after_stop(self):
        fake=type('Fake',(),{})();fake.scenario=ScenarioState();fake.scenario.new_session();fake.running=True
        called=[];callback=classroom.Classroom.guarded(fake,lambda:called.append(1))
        callback();fake.scenario.invalidate();callback();fake.running=False;callback()
        self.assertEqual(called,[1])


class BrowserActionDispatchTests(unittest.TestCase):
    def test_each_page_dispatches_its_matching_safe_scene(self):
        class FakeClassroom:
            def __init__(self):self.scenes=[]
            def spawn(self,scene):self.scenes.append(scene)
        fake=FakeClassroom()
        for index in range(len(classroom.PAGE_ACTION_SCENES)):
            classroom.Classroom.handle_page_action(fake,index)
        self.assertEqual(fake.scenes,list(classroom.PAGE_ACTION_SCENES))


@unittest.skipUnless(sys.platform == 'win32' and os.environ.get('CYBER_CLASSROOM_NATIVE_TESTS')=='1',
                     'Set CYBER_CLASSROOM_NATIVE_TESTS=1 for opt-in Win32 acceptance')
class NativeEffectAcceptanceTests(unittest.TestCase):
    def test_ten_native_lifecycles_do_not_accumulate_gui_handles(self):
        kernel=classroom.ctypes.WinDLL('kernel32');user=classroom.ctypes.WinDLL('user32')
        kernel.GetCurrentProcess.restype=classroom.ctypes.c_void_p
        user.GetGuiResources.argtypes=[classroom.ctypes.c_void_p,classroom.wintypes.DWORD]
        user.GetGuiResources.restype=classroom.wintypes.DWORD
        process=kernel.GetCurrentProcess()
        baseline=(user.GetGuiResources(process,0),user.GetGuiResources(process,1))
        class FakeApp:
            clock=0.0;rng=random.Random(9);events=BoundedEventBus()
        for index in range(10):
            effect=classroom.NativeEffect(FakeApp(),f'Lifecycle {index}',320,160)
            effect.batch(lambda ui:ui._add_label('bounded',20,20,250,30,10,False,
                                                 '#222','#f3f3f3','Segoe UI'))
            effect.close();self.assertTrue(effect.wait_closed(1))
        final=(user.GetGuiResources(process,0),user.GetGuiResources(process,1))
        self.assertLessEqual(final[0],baseline[0]+3)
        self.assertLessEqual(final[1],baseline[1]+3)

    def test_native_controls_keyboard_bridge_and_bounded_lifecycle(self):
        class FakeApp:
            clock=0.0;rng=random.Random(1);events=BoundedEventBus()
        app=FakeApp();effect=classroom.NativeEffect(app,'Native test',420,220,position='center')
        original=effect.hwnd
        try:
            handles={}
            def build(ui):
                handles['label']=ui._add_label('Учебен прозорец',20,20,360,30,11,True,'#222','#f3f3f3','Segoe UI')
                handles['progress']=ui._add_progress(20,65,360,20)
                handles['button']=ui._add_button('Close',280,120,100,34,lambda:None,False)
            effect.batch(build);effect.set_text(handles['label'],'Native Win32 контрол');effect.set_progress(handles['progress'],67)
            effect.user32.SendMessageW(handles['button'],effect.BM_CLICK,0,0)
            self.assertEqual(app.events.drain(2)[0][0],'native_callback')
            effect.user32.PostMessageW(handles['button'],effect.WM_KEYDOWN,0x75,0)
            deadline=time.monotonic()+1
            events=[]
            while time.monotonic()<deadline and not events:
                events=app.events.drain(2);time.sleep(.01)
            self.assertIn(('native_key','next'),events)
        finally:
            effect.close();effect.wait_closed(1.0)
        self.assertTrue(effect.closed);self.assertFalse(effect.thread.is_alive())
        self.assertNotIn(effect._key(original),effect.registry)

    def test_python_313_tk_http_and_native_callback_regression(self):
        root=classroom.tk.Tk();root.withdraw();pages=classroom.LocalPages()
        class FakeApp:
            clock=0.0;rng=random.Random(2);events=BoundedEventBus()
        app=FakeApp();clicked=[];effect=classroom.NativeEffect(app,'GIL regression',360,180)
        handles={}
        try:
            effect.batch(lambda ui:handles.update(button=ui._add_button(
                'Trigger',120,70,100,32,lambda:clicked.append(True),False)))
            def trigger():effect.user32.SendMessageW(handles['button'],effect.BM_CLICK,0,0)
            def drain():
                for action,payload in app.events.drain(4):
                    if action=='native_callback':payload()
                root.quit()
            root.after(25,trigger);root.after(100,drain);root.mainloop()
            self.assertEqual(clicked,[True])
        finally:
            effect.close();effect.wait_closed(1);pages.close();root.destroy()

    def test_all_native_scene_builders_smoke(self):
        root=classroom.tk.Tk();root.withdraw()
        app=classroom.Classroom(root,enable_hotkeys=False)
        app.hotkeys_ok=True;app.running=True;app.mode='manual';app.scenario.new_session()
        app.session=classroom.NativeSession(max_tabs=4,generation=app.scenario.generation)
        try:
            scenes=(app.scene_installer,app.scene_notification,app.scene_warning,app.scene_advert,
                    app.scene_terminal,app.scene_scanner,app.scene_error,app.scene_ransom)
            for scene in scenes:
                app.limiter.reset();scene();root.update()
                app.clock+=.2
                for effect in list(app.effects):effect.tick()
                app.clear_effects()
                deadline=time.monotonic()+.3
                while time.monotonic()<deadline and any(e.thread.is_alive() for e in app.closing_effects):
                    root.update();time.sleep(.01)
                app.closing_effects[:]=[e for e in app.closing_effects if e.thread.is_alive()]
            app.fullscreen.set(False);app.stage_mode('blue');root.update()
            self.assertEqual(app.stage.mode,'blue')
            app.clock+=20;app.stage.tick();root.update()
            self.assertEqual(app.stage.mode,'reboot')
            app.close_stage()
            self.assertEqual(app.live_effect_count(),0)
        finally:
            app.close()


@unittest.skipIf(classroom.Image is None,'Pillow is not installed')
class ScreenFramesTests(unittest.TestCase):
    def test_every_visual_mode_preserves_bounded_image_shape(self):
        source=classroom.Image.new('RGB',(1920,1080),'#335577')
        frames=classroom.ScreenFrames(source,(960,540))
        try:
            for mode in [*classroom.ScreenFrames.MODES,'Смесени ефекти','Статичен кадър']:
                with self.subTest(mode=mode):
                    frame=frames.frame(6.0,mode)
                    try:self.assertEqual(frame.size,(960,540));self.assertEqual(frame.mode,'RGB')
                    finally:frame.close()
            working=frames.frame(8.0,'Разтичане')
            try:
                fullscreen=frames.present(working,(1920,1200))
                try:self.assertEqual(fullscreen.size,(1920,1200))
                finally:fullscreen.close()
            finally:working.close()
        finally:frames.close();source.close()


if __name__ == '__main__':
    unittest.main()
