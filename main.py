"""VidText for Android (Kivy). Hide a video in a text file; restore it with a code word."""
import threading
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.textinput import TextInput
from kivy.utils import platform

import vidtext_core as core

ON_ANDROID = platform == "android"
if ON_ANDROID:
    from android.storage import app_storage_path
    from androidstorage4kivy import Chooser, SharedStorage
    from jnius import autoclass
    Environment = autoclass("android.os.Environment")

OUT_CHOICES = ["Downloads folder", "Auto (Documents / Movies)"]


def popup(title, text):
    box = BoxLayout(orientation="vertical", padding=10, spacing=10)
    box.add_widget(Label(text=text, text_size=(Window.width * 0.8, None), halign="left"))
    ok = Button(text="OK", size_hint_y=None, height="44dp")
    box.add_widget(ok)
    p = Popup(title=title, content=box, size_hint=(0.92, 0.6))
    ok.bind(on_release=p.dismiss)
    p.open()


class Tab(BoxLayout):
    def __init__(self, app, mode, **kw):
        super().__init__(orientation="vertical", padding=12, spacing=8, **kw)
        self.app, self.mode = app, mode
        self.uri = None
        self.private_path = ""

        self.pick_btn = Button(text="Choose video" if mode == "hide" else "Choose text file",
                               size_hint_y=None, height="48dp")
        self.pick_btn.bind(on_release=self.pick)
        self.add_widget(self.pick_btn)
        self.path_in = TextInput(hint_text="No file chosen", multiline=False, readonly=ON_ANDROID,
                                 size_hint_y=None, height="44dp")
        self.add_widget(self.path_in)

        self.add_widget(Label(text="Save result to:", size_hint_y=None, height="28dp", halign="left"))
        self.spin = Spinner(text=OUT_CHOICES[0], values=OUT_CHOICES, size_hint_y=None, height="44dp")
        self.add_widget(self.spin)

        self.code = TextInput(hint_text="Code word", password=True, multiline=False,
                              size_hint_y=None, height="44dp")
        self.add_widget(self.code)
        self.code2 = None
        if mode == "hide":
            self.code2 = TextInput(hint_text="Repeat code word", password=True, multiline=False,
                                   size_hint_y=None, height="44dp")
            self.add_widget(self.code2)
            row = BoxLayout(size_hint_y=None, height="40dp")
            self.delete = CheckBox(active=True, size_hint_x=None, width="40dp")
            row.add_widget(self.delete)
            row.add_widget(Label(text="Delete original video after it is verified", halign="left"))
            self.add_widget(row)

        self.go = Button(text="Convert video to text" if mode == "hide" else "Restore video",
                         size_hint_y=None, height="52dp")
        self.go.bind(on_release=self.run)
        self.add_widget(self.go)
        self.status = Label(text="Ready.", text_size=(Window.width * 0.85, None), halign="left", valign="top")
        self.add_widget(self.status)

    # ---- choosing a file
    def pick(self, *_):
        if not ON_ANDROID:
            self.status.text = "Type or paste a file path above."
            return
        Chooser(self.chosen).choose_content("video/*" if self.mode == "hide" else "*/*")

    def chosen(self, uris):
        if not uris:
            return
        self.uri = uris[0]
        self.set_status("Copying file into the app...")

        def work():
            try:
                p = SharedStorage().copy_from_shared(self.uri)
                Clock.schedule_once(lambda dt: self.picked(p))
            except Exception as e:
                Clock.schedule_once(lambda dt: self.set_status("Error: %s" % e))
        threading.Thread(target=work, daemon=True).start()

    def picked(self, p):
        self.private_path = p or ""
        self.path_in.text = Path(self.private_path).name if p else ""
        self.set_status("File ready." if p else "Could not read that file.")

    # ---- running
    def set_status(self, s):
        self.status.text = s

    def run(self, *_):
        src = self.private_path if ON_ANDROID else self.path_in.text.strip()
        code = self.code.text
        if self.mode == "hide" and code != self.code2.text:
            popup("VidText", "Code words do not match.")
            return
        self.go.disabled = True
        say = lambda s: Clock.schedule_once(lambda dt: self.set_status(s))

        def done(msg, ok=True):
            def f(dt):
                self.go.disabled = False
                self.set_status(msg)
                popup("VidText" if ok else "VidText - error", msg)
            Clock.schedule_once(f)

        def work():
            try:
                done(self.hide(src, code, say) if self.mode == "hide" else self.reveal(src, code, say))
            except Exception as e:
                done(str(e), ok=False)
        threading.Thread(target=work, daemon=True).start()

    def collection(self):
        if ON_ANDROID and self.spin.text == OUT_CHOICES[0]:
            return Environment.DIRECTORY_DOWNLOADS
        return None  # auto

    def work_dir(self):
        d = Path(app_storage_path()) / "work" if ON_ANDROID else Path.home() / "VidText"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def hide(self, src, code, say):
        src = Path(src)
        out = core.hide_video(src, self.work_dir() / (src.stem + ".txt"), code, say)
        if not ON_ANDROID:
            return "Done. Text saved to:\n%s" % out
        say("Saving text to shared storage...")
        SharedStorage().copy_to_shared(str(out), collection=self.collection())
        msg = "Done. Text file '%s' saved to your %s." % (out.name, "Downloads/VidText folder"
              if self.collection() else "Documents/VidText folder")
        Path(out).unlink(missing_ok=True)
        if self.delete.active:
            deleted = False
            try:
                deleted = SharedStorage().delete_shared(self.uri)
            except Exception:
                pass
            Path(src).unlink(missing_ok=True)  # the app's private copy
            msg += ("\n\nOriginal video deleted." if deleted else
                    "\n\nAndroid did not allow deleting the original. "
                    "Delete it yourself in Gallery/Files - the text is verified.")
        return msg

    def reveal(self, src, code, say):
        out = core.reveal_video(src, self.work_dir(), code, say)
        if not ON_ANDROID:
            return "Done. Video restored to:\n%s" % out
        say("Saving video to shared storage...")
        SharedStorage().copy_to_shared(str(out), collection=self.collection())
        Path(out).unlink(missing_ok=True)
        return "Done. Video '%s' saved to your %s." % (out.name, "Downloads/VidText folder"
               if self.collection() else "Movies/VidText folder")


class Root(TabbedPanel):
    def __init__(self, **kw):
        super().__init__(do_default_tab=False, tab_width=Window.width / 2, **kw)
        for title, mode in (("Video -> Text", "hide"), ("Text -> Video", "reveal")):
            item = TabbedPanelItem(text=title)
            item.add_widget(Tab(self, mode))
            self.add_widget(item)
        self.default_tab = self.tab_list[-1]


class VidTextApp(App):
    title = "VidText"

    def build(self):
        if ON_ANDROID:
            from android.permissions import Permission, request_permissions
            request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
        return Root()


if __name__ == "__main__":
    VidTextApp().run()
