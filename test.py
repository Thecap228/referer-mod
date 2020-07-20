#!/usr/bin/python3

# Referer Modifier: Automatic test
# Copyright (C) 2020 Fiona Klute
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import json
import os
import sys
import unittest
import uuid
from collections import namedtuple
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions

# Contains data for testing a link: The page to load initially
# (source), the link to click there (target), and the expected Referer
# header for the second request (referer).
testlink = namedtuple('testlink', ['source', 'target', 'referer'])


class RefModTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ext_dir = Path(sys.argv[0]).parent
        with open(cls.ext_dir / 'manifest.json') as fh:
            manifest = json.load(fh)

        cls.addon_path = (cls.ext_dir /
                          f'referer-mod-{manifest["version"]}.zip').resolve()
        addon_id = manifest["browser_specific_settings"]["gecko"]["id"]
        addon_dyn_id = str(uuid.uuid4())
        cls.config_url = f'moz-extension://{addon_dyn_id}/options.html'
        print(f'Dynamic ID: {addon_dyn_id}')

        profile = webdriver.FirefoxProfile()
        # Pre-seed the dynamic addon ID so we can find the options page
        profile.set_preference('extensions.webextensions.uuids',
                               json.dumps({addon_id: addon_dyn_id}))
        # Use the local test environment, see testserver/
        profile.set_preference('network.proxy.type', 1)
        profile.set_preference('network.proxy.http', 'localhost')
        profile.set_preference('network.proxy.http_port', 8080)
        cls.options = FirefoxOptions()
        cls.options.profile = profile
        if not os.environ.get('DISPLAY'):
            cls.options.headless = True

    def setUp(self):
        self.browser = webdriver.Firefox(options=self.options)
        self.browser.install_addon(str(self.addon_path), temporary=True)

    def tearDown(self):
        self.browser.quit()

    def click_link(self, target):
        links = self.browser.find_elements_by_tag_name('a')
        for l in links:
            if l.get_attribute('href') == target:
                # Found target link, click
                l.click()
                return
        self.fail(f'No link to {target} found!')

    def testReferers(self):
        # load configuration
        test_config = (self.ext_dir / 'test_config.json').resolve()
        self.browser.get(self.config_url)
        import_file = self.browser.find_element_by_id('import_file')
        import_file.send_keys(str(test_config))
        import_button = self.browser.find_element_by_id('import_button')
        import_button.click()

        # mapping from next target to click to expected Referer, in order
        tests = [
            testlink('http://web.x.test/page/', 'http://web.x.test/page/',
                     'http://web.x.test/page/'),
            testlink('http://web.x.test/page/', 'http://www.x.test/page/',
                     'http://web.x.test/'),
            testlink('http://www.x.test/page/', 'http://site.y.test/page/',
                     'https://www.example.com/'),
            testlink('http://site.y.test/page/', 'http://www.y.test/page/',
                     None),
        ]

        for link in tests:
            with self.subTest(link=link):
                self.browser.get(link.source)
                self.click_link(link.target)
                print(f'Navigating {link.source} -> {link.target}')
                try:
                    http_referer = self.browser.find_element(
                        By.XPATH, '//td[text()="Referer"]//following::td')
                    print(f'Page shows referer: {http_referer.text}')
                    self.assertEqual(link.referer, http_referer.text)
                except NoSuchElementException:
                    print('Page shows no Referer.')
                    if link.referer is not None:
                        raise


if __name__ == '__main__':
    unittest.main(verbosity=2)
