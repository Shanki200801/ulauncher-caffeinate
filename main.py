import os
import subprocess
import sys

from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.HideWindowAction import HideWindowAction

CAF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "caffeinate.py")
ICON = "images/icon.svg"
PRESETS = [("Until I turn it off", ""), ("30 minutes", "30"), ("1 hour", "60"),
           ("2 hours", "120"), ("4 hours", "240")]


def run(*args):
    return subprocess.run([sys.executable, CAF, *args], capture_output=True, text=True).stdout.strip()


def item(name, desc, arg):
    return ExtensionResultItem(icon=ICON, name=name, description=desc,
                               on_enter=ExtensionCustomAction(arg))


class Query(EventListener):
    def on_event(self, event, extension):
        status = run("status")
        typed = (event.get_argument() or "").strip()
        items = []
        if typed:  # e.g. "caf 45" or "caf 1h30m"
            items.append(item(f"Keep awake for {typed}", f"Currently: {status}", typed))
        if status != "off":
            items.append(item("Turn off caffeinate", f"Currently: {status}", "off"))
        for label, arg in PRESETS:
            items.append(item(f"Keep awake: {label}", f"Currently: {status}", arg or "on"))
        return RenderResultListAction(items)


class Enter(EventListener):
    def on_event(self, event, extension):
        arg = event.get_data()
        if arg == "on":
            run()
        else:
            run(arg)
        status = run("status")
        try:
            icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), ICON)
            subprocess.Popen(["notify-send", "-i", icon, "-t", "2500", "Caffeinate", status.capitalize()])
        except FileNotFoundError:
            pass  # notify-send not installed
        return HideWindowAction()


class Caffeinate(Extension):
    def __init__(self):
        super().__init__()
        self.subscribe(KeywordQueryEvent, Query())
        self.subscribe(ItemEnterEvent, Enter())


if __name__ == "__main__":
    Caffeinate().run()
