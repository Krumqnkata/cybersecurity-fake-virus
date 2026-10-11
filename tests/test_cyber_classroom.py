import json
import base64
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
import xml.etree.ElementTree as ET

import cyber_classroom as classroom
from classroom_core import (
    ABSOLUTE_MAX_EFFECTS, ABSOLUTE_MAX_TABS, BoundedEventBus, PauseClock,
    DEFAULT_STORY_LABEL, PROFILES, STORY_PRESETS, RateLimiter, ScenarioEvent,
    ScenarioState, SignalChannel, SurfaceVariant, NotificationSpec,
    build_session_mix, new_mix_code, normalize_mix_code, retained_chapter_index,
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

    def test_controlled_browser_signal_and_close_sequence_are_state_driven(self):
        spec=next(item for item in build_session_mix('15 минути','CAVE42').signals
                  if item.channel is SignalChannel.BROWSER)
        self.pages.set_browser_signal(spec,'bg')
        state_url=(f'http://127.0.0.1:{self.pages.server.server_port}/'
                   f'{self.pages.token}/state')
        with urllib.request.urlopen(state_url,timeout=3) as response:
            state=json.loads(response.read())
        self.assertEqual(state['browser_signal']['id'],spec.signal_id)
        self.assertEqual(state['browser_signal']['layout'],spec.surface.layout_id)
        self.pages.request_notification_close()
        with urllib.request.urlopen(state_url,timeout=3) as response:
            closed=json.loads(response.read())
        self.assertIsNone(closed['browser_signal'])
        self.assertEqual(closed['notification_close_sequence'],1)

    def test_manual_web_notification_page_is_explicit_local_and_closeable(self):
        with urllib.request.urlopen(self.pages.web_notification_url(),timeout=3) as response:
            page=response.read().decode('utf-8')
        self.assertIn('Notification.requestPermission()',page)
        self.assertIn('window.classroomNotifications',page)
        self.assertIn('item.close()',page)
        self.assertIn('LOCALHOST',page)
        self.assertNotIn('https://',page)


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


class WindowsToastTests(unittest.TestCase):
    def test_encoded_toast_is_local_labeled_and_escapes_text(self):
        encoded=classroom.WindowsToastNotifier.encoded_script(
            "УЧЕБНА СИМУЛАЦИЯ • Teacher's alert",'Само локално известие')
        script=base64.b64decode(encoded).decode('utf-16le')
        self.assertIn('ToastNotificationManager',script)
        self.assertIn("Teacher''s alert",script)
        self.assertIn('Само локално известие',script)
        self.assertIn("$toast.ExpirationTime",script)
        self.assertNotIn('http://',script)
        self.assertNotIn('https://',script)

    def test_adaptive_layouts_are_distinct_valid_and_escape_user_text(self):
        layouts=('text_fallback','adaptive_compact','adaptive_warning','adaptive_summary','adaptive_success')
        payloads=[classroom.WindowsToastNotifier.toast_xml(
            'A < B & C','Teacher says "review"',layout) for layout in layouts]
        self.assertEqual(len(set(payloads)),len(layouts))
        for payload in payloads:
            ET.fromstring(payload)
            self.assertIn('A &lt; B &amp; C',payload)
            self.assertNotIn('<script',payload.lower())
        self.assertIn('template="ToastText02"',payloads[0])


class SessionMixTests(unittest.TestCase):
    def test_three_thousand_seeded_mixes_satisfy_model_invariants(self):
        alphabet='ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        checked=0
        for story in STORY_PRESETS:
            for number in range(1000):
                value=number;characters=[]
                for _ in range(6):
                    characters.append(alphabet[value%len(alphabet)])
                    value=value//len(alphabet)+7
                mix=build_session_mix(story,''.join(characters))
                self.assertEqual(mix.story_label,story)
                checked+=1
        self.assertEqual(checked,3000)

    def test_same_code_and_preset_replay_exactly_and_other_code_changes_mix(self):
        first=build_session_mix('15 минути','CAVE42')
        replay=build_session_mix('15 минути','CAVE42')
        other=build_session_mix('15 минути','DEPTH7')
        self.assertEqual(first,replay)
        self.assertNotEqual(first.signals,other.signals)

    def test_signal_counts_channels_spacing_and_nonrepetition(self):
        expected={'10 минути':9,'15 минути':13,'20 минути':16}
        phase_windows={
            '10 минути':{'delivery':(0,80),'install':(80,180),'foothold':(180,280),
                         'symptoms':(280,420),'recovery':(540,600)},
            '15 минути':{'delivery':(0,100),'install':(100,225),'foothold':(225,370),
                         'symptoms':(370,500),'detection':(500,655),'recovery':(835,875)},
            '20 минути':{'delivery':(0,125),'install':(125,280),'foothold':(280,460),
                         'symptoms':(460,625),'detection':(625,750),
                         'investigation':(750,965),'impact':(965,1050),
                         'recovery':(1110,1170)},
        }
        for story,count in expected.items():
            for code in ('CAVE42','DEPTH7','M1XBAD'.replace('1','2'),'7H2K9M'):
                with self.subTest(story=story,code=code):
                    mix=build_session_mix(story,code)
                    self.assertEqual(len(mix.signals),count)
                    self.assertEqual(len({item.channel for item in mix.signals}),5)
                    self.assertEqual(len({item.uniqueness_key for item in mix.signals}),count)
                    for previous,current in zip(mix.signals,mix.signals[1:]):
                        self.assertGreaterEqual(current.at-previous.at,8)
                        self.assertNotEqual(previous.channel,current.channel)
                        self.assertNotEqual(previous.surface.icon_id,current.surface.icon_id)
                        self.assertNotEqual(previous.surface.severity,current.surface.severity)
                        self.assertNotEqual(previous.surface.sound_id,current.surface.sound_id)
                    toast_times=[item.at for item in mix.signals
                                 if item.channel is SignalChannel.NOTIFICATION_CENTER]
                    self.assertTrue(all(b-a>=20 for a,b in zip(toast_times,toast_times[1:])))
                    for item in mix.signals:
                        low,high=phase_windows[story][item.phase]
                        self.assertLessEqual(low,item.at)
                        self.assertLess(item.at,high)

    def test_mix_codes_are_six_safe_characters_and_normalize_separators(self):
        self.assertEqual(normalize_mix_code('ca-ve 42'),'CAVE42')
        for _ in range(20):
            code=new_mix_code()
            self.assertEqual(len(code),6)
            self.assertFalse(set(code)&set('IO01'))
        for invalid in ('short','OOOOOO','ABC*23'):
            with self.assertRaises(ValueError):
                normalize_mix_code(invalid)


class ReliabilityPrimitiveTests(unittest.TestCase):
    def test_extended_story_is_ordered_long_and_varied(self):
        times=[moment for moment,_ in classroom.TIMELINE]
        scenes={scene for _,scene in classroom.TIMELINE}
        self.assertEqual(times,sorted(times))
        self.assertEqual(classroom.MASTER_DURATION,900)
        self.assertTrue({'download','uac','firewall','taskmanager','updater','protection_history',
                         'ransom','recovery'} <= scenes)
        self.assertFalse({'blue','reboot','glitch'} & scenes)
        self.assertNotIn('spyware',scenes)
        for scene in scenes-{'finish'}:
            self.assertTrue(hasattr(classroom.Classroom,'scene_'+scene),scene)

    def test_story_presets_are_distinct_complete_graphs(self):
        self.assertEqual(DEFAULT_STORY_LABEL,'15 минути')
        self.assertEqual(set(STORY_PRESETS),{'10 минути','15 минути','20 минути'})
        self.assertEqual([story.duration for story in STORY_PRESETS.values()],[600,900,1200])
        lengths=[]
        for label,story in STORY_PRESETS.items():
            with self.subTest(label=label):
                self.assertEqual(story.beats[-1].at,story.duration)
                self.assertEqual(story.beats[-1].scene,'finish')
                self.assertEqual(story.chapters[0][0],0)
                self.assertEqual([beat.at for beat in story.beats],
                                 sorted(beat.at for beat in story.beats))
                lengths.append(len(story.beats))
        self.assertEqual(lengths,[16,21,23])
        self.assertIn('network_activity',{beat.scene for beat in STORY_PRESETS['20 минути'].beats})
        self.assertNotIn('network_activity',{beat.scene for beat in STORY_PRESETS['10 минути'].beats})

    def test_default_story_uses_the_approved_fixed_moments(self):
        story=STORY_PRESETS['15 минути']
        self.assertEqual([(beat.at,beat.scene) for beat in story.beats],[
            (0,'browser'),(70,'download'),(100,'uac'),(130,'installer'),
            (225,'helper'),(255,'notification'),(290,'tabs'),(330,'firewall'),
            (370,'taskmanager'),(415,'updater'),(465,'error'),(500,'warning'),
            (535,'scanner'),(610,'protection_history'),(655,'terminal_chapter'),
            (710,'explorer'),(745,'files_chapter'),(785,'ransom'),
            (835,'recovery'),(875,'debrief'),(900,'finish')])

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

    def test_scenario_events_are_idempotent_and_share_causal_state(self):
        state=ScenarioState();generation=state.new_session()
        self.assertTrue(state.apply_event(ScenarioEvent.DOWNLOAD_REQUESTED,generation=generation))
        self.assertFalse(state.apply_event(ScenarioEvent.DOWNLOAD_REQUESTED,generation=generation))
        self.assertTrue(state.apply_event(ScenarioEvent.INSTALL_COMPLETED,
                                          {'idempotency_key':'install:1'},generation=generation))
        self.assertEqual((state.phase,state.helper_state,state.tray_visible),('foothold','running',True))
        self.assertTrue(state.apply_event(ScenarioEvent.FILES_LOCKED,{'count':5},generation=generation))
        self.assertFalse(state.apply_event(ScenarioEvent.FILES_LOCKED,{'count':5},generation=generation))
        self.assertTrue(state.apply_event(ScenarioEvent.FILES_LOCKED,{'count':8},generation=generation))
        self.assertEqual(state.locked_count,8)
        state.invalidate()
        self.assertFalse(state.apply_event(ScenarioEvent.RECOVERY_STARTED,generation=generation))

    def test_teacher_branch_controls_the_student_choice(self):
        state=ScenarioState();state.new_session()
        self.assertTrue(state.apply_event(ScenarioEvent.STUDENT_DECISION,
                                          {'checkpoint':'uac','choice':'no','idempotency_key':'uac:no'}))
        self.assertTrue(state.branch_pending)
        self.assertTrue(state.apply_event(ScenarioEvent.TEACHER_ACCEPTED,
                                          {'idempotency_key':'teacher:accept'}))
        self.assertEqual(state.phase,'contained')
        self.assertFalse(state.branch_pending)

    def test_every_teacher_branch_choice_has_an_explicit_result(self):
        for choice in ('no','cancel','block','stop'):
            with self.subTest(choice=choice):
                state=ScenarioState();state.new_session()
                self.assertTrue(state.apply_event(ScenarioEvent.STUDENT_DECISION,
                    {'checkpoint':choice,'choice':choice,'idempotency_key':f'decision:{choice}'}))
                self.assertFalse(state.apply_event(ScenarioEvent.STUDENT_DECISION,
                    {'checkpoint':choice,'choice':choice,'idempotency_key':f'decision:{choice}'}))
                self.assertTrue(state.apply_event(ScenarioEvent.TEACHER_ACCEPTED,
                    {'idempotency_key':f'accept:{choice}'}))
                self.assertEqual(state.phase,'contained')
                self.assertFalse(state.branch_pending)
        state=ScenarioState();state.new_session()
        state.apply_event(ScenarioEvent.STUDENT_DECISION,
                          {'checkpoint':'uac','choice':'yes','idempotency_key':'decision:yes'})
        self.assertTrue(state.apply_event(ScenarioEvent.TEACHER_COMPROMISED,
                                         {'phase':'execution','idempotency_key':'force:yes'}))
        self.assertEqual(state.phase,'execution');self.assertFalse(state.branch_pending)

    def test_story_rebuild_invalidates_old_callbacks_and_projects_prior_beats(self):
        state=ScenarioState();old_generation=state.new_session()
        generation=state.rebuild_for_story(
            ['download','uac','installer','helper','firewall','warning','scanner',
             'terminal_chapter','files_chapter'],6,locked_count=8)
        self.assertNotEqual(generation,old_generation)
        self.assertFalse(state.accepts(old_generation))
        self.assertEqual(state.chapter_index,6)
        self.assertEqual(state.download_stage,'completed')
        self.assertEqual(state.installer_stage,'completed')
        self.assertEqual(state.helper_state,'running')
        self.assertEqual(state.firewall_state,'allowed')
        self.assertEqual(state.scanner_stage,'completed')
        self.assertEqual(state.terminal_stage,'completed')
        self.assertEqual(state.locked_count,8)

    def test_story_rebuild_after_recovery_is_consistently_clean(self):
        state=ScenarioState()
        state.rebuild_for_story(
            ['download','installer','helper','warning','scanner','files_chapter','recovery'],
            9,locked_count=0)
        self.assertEqual(state.phase,'recovered')
        self.assertEqual(state.recovery_stage,'completed')
        self.assertEqual(state.quarantine_state,'completed')
        self.assertEqual(state.locked_count,0)
        self.assertFalse(state.tray_visible)

    def test_chapter_index_supports_skipping(self):
        self.assertEqual(retained_chapter_index(0,classroom.CHAPTERS),0)
        self.assertEqual(retained_chapter_index(255,classroom.CHAPTERS),2)
        self.assertEqual(retained_chapter_index(475,classroom.CHAPTERS),3)
        self.assertEqual(retained_chapter_index(999,classroom.CHAPTERS),len(classroom.CHAPTERS)-1)

    def test_windows_profile_detection_is_deterministic(self):
        win10=classroom.detect_windows_profile(build=19045,language_id=0x0409)
        win11=classroom.detect_windows_profile(build=22631,language_id=0x0402)
        self.assertEqual((win10.generation,win10.language,win10.rounded_corners),
                         ('windows10','en',False))
        self.assertEqual((win11.generation,win11.language,win11.rounded_corners),
                         ('windows11','bg',True))


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

    def test_recovery_restores_at_most_one_owned_file_per_step(self):
        self.session.lock_files(3)
        restored,name=self.session.restore_next_file()
        self.assertTrue(restored);self.assertTrue(name.endswith('.txt'))
        self.assertEqual(sum(locked.exists() for _,locked,_ in self.session.files),2)

    def test_step_recovery_never_overwrites_a_conflicting_plain_file(self):
        plain,locked,_=self.session.files[0]
        self.session.lock_files(1)
        plain.write_text('Запази тази учителска промяна',encoding='utf-8')
        restored,name=self.session.restore_next_file()
        self.assertFalse(restored);self.assertEqual(name,locked.name)
        self.assertEqual(plain.read_text(encoding='utf-8'),'Запази тази учителска промяна')
        self.assertTrue(locked.exists())

    def test_browser_uses_selected_monitor_bounds(self):
        class FakeJob:
            def __init__(self):self.launches=[]
            def launch(self,exe,args):self.launches.append(args)
        class FakePages:
            def url(self,index):return f'http://127.0.0.1/local/{index}'
        self.session.executable=Path('C:/fake/msedge.exe')
        self.session.presentation_bounds=(-1920,0,0,1040)
        self.session.job=FakeJob();self.session.pages=FakePages();self.session.browser_ready=True
        self.assertTrue(self.session.open_tab())
        args=self.session.job.launches[0]
        self.assertIn('--window-position=-1920,0',args)
        self.assertIn('--window-size=1920,1040',args)

    def test_manual_notification_launch_uses_only_the_local_owned_page(self):
        class FakeJob:
            def __init__(self):self.launches=[]
            def launch(self,exe,args):self.launches.append(args)
        class FakePages:
            def web_notification_url(self):return 'http://127.0.0.1/manual-notification'
        self.session.executable=Path('C:/fake/msedge.exe')
        self.session.job=FakeJob();self.session.pages=FakePages();self.session.browser_ready=True
        self.assertTrue(self.session.open_web_notification())
        self.assertEqual(self.session.job.launches[0][-1],
                         'http://127.0.0.1/manual-notification')

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
        app.windows_notifications.set(False)
        app.hotkeys_ok=True;app.running=True;app.mode='manual';app.scenario.new_session()
        app.session=classroom.NativeSession(max_tabs=4,generation=app.scenario.generation)
        try:
            scenes=(app.scene_download,app.scene_uac,app.scene_installer,app.scene_notification,
                    app.scene_warning,app.scene_firewall,app.scene_taskmanager,app.scene_updater,
                    app.scene_advert,app.scene_terminal,app.scene_scanner,app.scene_properties,
                    app.scene_protection_history,app.scene_network_activity,app.scene_ransom,
                    app.scene_recovery)
            for scene in scenes:
                app.limiter.reset();scene();root.update()
                app.clock+=.2
                for effect in list(app.effects):effect.tick()
                app.clear_effects()
                app.close_stage()
                deadline=time.monotonic()+.3
                while time.monotonic()<deadline and any(e.thread.is_alive() for e in app.closing_effects):
                    root.update();time.sleep(.01)
                app.closing_effects[:]=[e for e in app.closing_effects if e.thread.is_alive()]
            for index,layout in enumerate(('defender_card','inline_banner','legacy_balloon','compact_toast')):
                spec=NotificationSpec(
                    f'native-signal-{index}',10+index*10,'smoke',SignalChannel.IN_APP,
                    'CaveDepths','Учебен сигнал','Classroom signal',
                    'Различима контролирана повърхност.','Distinct controlled surface.',
                    SurfaceVariant(layout,('shield','update','error','info')[index],
                                   ('warning','caution','error','info')[index],
                                   ('warning','updater','error','notification')[index]))
                app.limiter.reset();self.assertTrue(app.scene_signal(spec));root.update()
                app.clear_effects()
            app.fullscreen.set(False);app.stage_mode('blue');root.update()
            self.assertEqual(app.stage.mode,'blue')
            app.clock+=20;app.stage.tick();root.update()
            self.assertEqual(app.stage.mode,'reboot')
            app.close_stage()
            self.assertEqual(app.live_effect_count(),0)
        finally:
            app.close()

    def test_owned_tray_icon_has_bounded_lifecycle(self):
        events=BoundedEventBus();tray=classroom.OwnedTrayIcon(events,'Block Runtime Host')
        try:
            self.assertTrue(tray.ready.wait(1.5))
            self.assertIsNotNone(tray.hwnd)
            self.assertTrue(tray.set_tooltip('Block Runtime • scan pending'))
            self.assertTrue(tray.show_balloon('Scan result','Three classroom findings','warning'))
        finally:
            tray.close()
        self.assertFalse(tray.thread.is_alive())

    def test_taskbar_progress_is_owned_and_clearable(self):
        class FakeApp:
            clock=0.0;rng=random.Random(12);events=BoundedEventBus()
        effect=classroom.NativeEffect(FakeApp(),'Taskbar test',380,180,role='app')
        taskbar=classroom.TaskbarController()
        try:
            self.assertTrue(effect.ready.wait(1.0))
            self.assertIsNotNone(effect.hwnd)
            if not taskbar.available:
                self.skipTest('ITaskbarList3 is unavailable')
            self.assertTrue(taskbar.signal(effect.hwnd,'scan_progress',1.0))
            self.assertTrue(taskbar.active)
            taskbar.clear(effect.hwnd)
            self.assertFalse(taskbar.active)
        finally:
            taskbar.close();effect.close();effect.wait_closed(1)


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
