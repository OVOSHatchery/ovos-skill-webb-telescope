from mycroft import intent_file_handler, intent_handler, MycroftSkill
from mycroft.skills.core import resting_screen_handler
from adapt.intent import IntentBuilder
from mtranslate import translate
import random
from os.path import join, dirname
from os import listdir
from requests_cache import CachedSession
from datetime import timedelta
from mycroft.util import create_daemon


class JamesWebbTelescopeSkill(MycroftSkill):
    def __init__(self):
        super(JamesWebbTelescopeSkill, self).__init__(name="WebbTelescopeSkill")
        if "random" not in self.settings:
            # idle screen, random or latest
            self.settings["random"] = False
        if "include_hubble" not in self.settings:
            self.settings["include_hubble"] = False
        if "exclude_long" not in self.settings:
            self.settings["exclude_long"] = True
        self.session = CachedSession(backend='memory',
                                     expire_after=timedelta(hours=6))
        self.translate_cache = {}
        # bootstrap - cache image data
        create_daemon(self.latest_webb)

    # webb api
    def latest_webb(self, n=-1):
        url = "http://hubblesite.org/api/v3/images/all"
        info_url = "http://hubblesite.org/api/v3/image/{img_id}"
        entries = self.session.get(url).json()
        wallpapers = []
        for e in entries:
            image_data = self.session.get(
                info_url.format(img_id=e["id"])).json()
            if image_data["mission"] != "james_webb" and\
                    not self.settings["include_hubble"]:
                continue
            data = {
                "author": "Webb Space Telescope",
                "caption": image_data.get("description"),
                "title": image_data["name"],
                "url": "https://hubblesite.org/image/{id}/gallery".format(
                    id=e["id"]),
                "imgLink": "",

            }
            max_size = 0
            min_size = 99999
            for link in image_data["image_files"]:
                if not link.get("height") or not link.get("width"):
                    continue
                if link['height'] > 2 * link['width'] \
                        and self.settings["exclude_long"]:
                    continue  # skip long infographics
                for ext in [".png", ".jpg", ".jpeg"]:
                    if link["file_url"].endswith(ext):
                        if link["width"] > max_size:
                            data["imgLink"] = "http:" + link["file_url"]
                        if max_size < link["width"] < min_size:
                            data["thumbnail"] = "http:" + link["file_url"]
            if data["imgLink"]:
                wallpapers.append(data)
            if 0 < n <= len(wallpapers):
                break
        return wallpapers

    def webb_pod(self):
        return self.latest_webb(1)[0]

    def random_webb(self):
        pictures = self.latest_webb()
        return random.choice(pictures)

    # idle screen
    def update_picture(self, latest=True):
        if latest:
            data = self.webb_pod()
        else:
            data = self.random_webb()

        tx = ["title", "caption"]
        for k in data:
            if not self.lang.startswith("en") and k in tx:
                if data[k] not in self.translate_cache:
                    translated = translate(data[k], self.lang)
                    self.translate_cache[data[k]] = translated
                    data[k] = translated
                else:
                    data[k] = self.translate_cache[data[k]]

            self.settings[k] = data[k]
            self.gui[k] = data[k]
        self.set_context("WebbTelescope")

    @resting_screen_handler("WebbTelescope")
    def idle(self, message):
        self.update_picture(not self.settings["random"])
        self.gui.clear()
        self.gui.show_page('idle.qml')

    # intents
    # TODO https://webbtelescope.org/quick-facts
    def _random_pic(self):
        path = join(dirname(__file__), "ui", "images", "webb_pictures")
        pics = listdir(path)
        return join(path, random.choice(pics))

    @intent_file_handler("about.intent")
    def handle_about_webb_intent(self, message):
        webb = self._random_pic()
        caption = self.dialog_renderer.render("about", {})
        self.gui.show_image(webb, override_idle=True,
                            fill='PreserveAspectFit', caption=caption)
        self.speak(caption, wait=True)

    @intent_file_handler('webb.intent')
    def handle_pod(self, message):
        if self.voc_match(message.data["utterance"], "latest"):
            self.update_picture(True)
        else:
            self.update_picture(False)
        self.gui.clear()
        self.gui.show_image(self.settings['imgLink'],
                            title=self.settings['title'],
                            fill='PreserveAspectFit')

        self.speak(self.settings['caption'])

    @intent_handler(IntentBuilder("ExplainIntent")
                    .require("ExplainKeyword").require("WebbTelescope"))
    def handle_explain(self, message):
        self.gui.show_image(self.settings['imgLink'], override_idle=True,
                            fill='PreserveAspectFit',
                            title=self.settings["title"],
                            caption=self.settings['caption'])
        self.speak(self.settings['caption'], wait=True)


def create_skill():
    return JamesWebbTelescopeSkill()
