import json
import queue
import random
import shutil
import sys
import threading
import unittest
import urllib.error
import urllib.request

import cyber_classroom as classroom


class LocalPagesTests(unittest.TestCase):
    def setUp(self):
        self.pages = classroom.LocalPages()

    def tearDown(self):
        self.pages.close()

    def test_serves_only_tokenized_local_pages_and_state(self):
        with urllib.request.urlopen(self.pages.url(0), timeout=3) as response:
            html = response.read().decode('utf-8')
            self.assertEqual(response.status, 200)
            self.assertIn('SUPERMOD', html)
            self.assertIn("default-src 'none'", response.headers['Content-Security-Policy'])

        state_url = (f'http://127.0.0.1:{self.pages.server.server_port}/'
                     f'{self.pages.token}/state')
        with urllib.request.urlopen(state_url, timeout=3) as response:
            self.assertEqual(json.loads(response.read()),
                             {'time': 0, 'paused': False, 'tabs': 0})

        bad_url = f'http://127.0.0.1:{self.pages.server.server_port}/state'
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(bad_url, timeout=3)
        self.assertEqual(caught.exception.code, 404)

    def test_page_action_is_queued_by_the_loopback_post(self):
        request = urllib.request.Request(self.pages.action_url(2), data=b'', method='POST')
        with urllib.request.urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 202)
            self.assertEqual(json.loads(response.read()), {'accepted': True})

        self.assertEqual(self.pages.drain_actions(), [2])
        self.assertEqual(self.pages.drain_actions(), [])

        with urllib.request.urlopen(self.pages.url(2), timeout=3) as response:
            html = response.read().decode('utf-8')
        self.assertIn('/action/2', html)
        self.assertNotIn('Заявката не може да бъде изпълнена', html)


class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        self.session = classroom.NativeSession()

    def tearDown(self):
        shutil.rmtree(self.session.root, ignore_errors=True)

    def test_locks_and_restores_only_generated_files(self):
        extra = self.session.folder / 'Добавен_от_учителя.txt'
        extra.write_text('Не трябва да се променя.', encoding='utf-8')

        self.session.lock_files(8)
        self.assertEqual(sum(path.name.endswith('.locked')
                             for path in self.session.folder.iterdir()), 8)
        self.assertEqual(self.session.restore_files(), [])
        self.assertEqual(extra.read_text(encoding='utf-8'), 'Не трябва да се променя.')

    def test_reports_a_generated_file_that_was_removed(self):
        plain, locked, _ = self.session.files[0]
        self.session.lock_files(1)
        locked.unlink()

        self.assertIn(plain.name, self.session.restore_files())


class BrowserActionDispatchTests(unittest.TestCase):
    def test_each_page_dispatches_its_matching_safe_scene(self):
        class FakeClassroom:
            def __init__(self):
                self.scenes = []

            def spawn(self, scene):
                self.scenes.append(scene)

        fake = FakeClassroom()
        for index in range(len(classroom.PAGE_ACTION_SCENES)):
            classroom.Classroom.handle_page_action(fake, index)

        self.assertEqual(fake.scenes, list(classroom.PAGE_ACTION_SCENES))


@unittest.skipUnless(sys.platform == 'win32', 'Native windows require Win32')
class NativeEffectTests(unittest.TestCase):
    def test_native_controls_and_button_callback_have_a_bounded_lifecycle(self):
        class FakeApp:
            clock = 0.0
            rng = random.Random(1)
            events = queue.Queue()

        clicked = []
        app = FakeApp()
        effect = classroom.NativeEffect(app, 'Native test', 420, 220, position='center')
        original_handle = effect.hwnd
        try:
            self.assertNotEqual(effect.thread.ident, threading.get_ident())
            self.assertTrue(effect.thread.is_alive())
            label_handle = effect.add_label('Учебен прозорец', 20, 20, 360, 30, bold=True)
            progress_handle = effect.add_progress(20, 65, 360, 20)
            button_handle = effect.add_button('Close', 280, 120, 100, 34,
                                              lambda: clicked.append(True))
            effect.set_text(label_handle, 'Native Win32 контрол')
            effect.set_progress(progress_handle, 67)
            effect.user32.SendMessageW(button_handle, effect.BM_CLICK, 0, 0)
            self.assertEqual(clicked, [])
            action, callback = app.events.get(timeout=2)
            self.assertEqual(action, 'native_callback')
            callback()

            self.assertEqual(clicked, [True])
            self.assertTrue(effect.user32.IsWindow(original_handle))
        finally:
            effect.close()

        self.assertTrue(effect.closed)
        self.assertIsNone(effect.hwnd)
        self.assertFalse(effect.thread.is_alive())
        self.assertNotIn(effect._key(original_handle), effect.registry)
        self.assertFalse(hasattr(classroom.Classroom, 'open_quiz'))


@unittest.skipIf(classroom.Image is None, 'Pillow is not installed')
class ScreenFramesTests(unittest.TestCase):
    def test_every_visual_mode_preserves_image_shape(self):
        source = classroom.Image.new('RGB', (320, 200), '#335577')
        frames = classroom.ScreenFrames(source)
        try:
            for mode in [*classroom.ScreenFrames.MODES, 'Смесени ефекти']:
                with self.subTest(mode=mode):
                    frame = frames.frame(6.0, mode)
                    try:
                        self.assertEqual(frame.size, (320, 200))
                        self.assertEqual(frame.mode, 'RGB')
                    finally:
                        frame.close()
        finally:
            frames.close()
            source.close()


if __name__ == '__main__':
    unittest.main()
