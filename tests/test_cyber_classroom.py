import json
import shutil
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
