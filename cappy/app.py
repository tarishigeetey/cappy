#!/usr/bin/env python3
"""
Cappy - a desktop capybara companion for macOS.

It lives at the bottom of your screen, wanders across your dock, and reminds
you to drink water, walk, and get back to work. It reacts with moods (happy,
sad, sleepy, excited) and gently grabs your attention when a reminder is due.

Sprites are your own uploaded pixel-art capybaras (backgrounds removed).
"""
import sys
import os
import json
import random
import subprocess
import atexit
import fcntl

from PyQt6 import QtCore, QtGui, QtWidgets

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SPRITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites")
# Files live next to the Cappy folder (one level up from the package).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODO_FILE = os.path.join(BASE_DIR, "todos.txt")
CONFIG_FILE = os.path.join(BASE_DIR, "cappy_config.json")

# On-screen height of the capybara in pixels (sprites are scaled to this).
PET_HEIGHT = 78

# Extra pixels to lift the pet above the dock. Increase if it still overlaps.
DOCK_LIFT = 6

# How often the pet takes a "step" while walking (ms). Lower = smoother/faster.
TICK_MS = 30
WALK_SPEED = 2.2          # px per tick while walking

# Built-in reminder intervals in minutes. Tweak freely.
# Built-in reminders are now EMPTY — every reminder is custom (add via the menu).
# You can run with zero reminders. These presets only seed the "Add reminder"
# quick-pick menu; they are not scheduled unless you add them.
REMINDERS = {}

PRESET_REMINDERS = {
    "water": {"minutes": 30, "text": "time to drink water!",  "emoji": "💧", "say": "Drink some water!"},
    "walk":  {"minutes": 50, "text": "time to move — walk or exercise!", "emoji": "🏋️", "say": "Time to move!"},
    "work":  {"minutes": 45, "text": "back to work, you got this", "emoji": "💼", "say": "Focus time."},
}

# How often (minutes) the capy nags you about the next item in todos.txt.
TODO_MINUTES = 20

# Check Spotify / Apple Music every N seconds and show headphones while playing.
SPOTIFY_POLL_SEC = 5
SPOTIFY_REACT_DEFAULT = True

# Seconds before a reminder fires that the capy shows a subtle "heads-up" wiggle.
PREWARN_SEC = 60

# Auto-hide the pet a few seconds after a reminder is completed or snoozed so it
# can disappear until you call it back.
AUTO_HIDE_AFTER_REMINDER_SEC = 20

# Snooze length in minutes when you snooze a reminder.
SNOOZE_MINUTES = 5

# How long a manually-chosen mood (Set mood menu) sticks before returning to
# normal wandering — unless you change it sooner. In minutes.
MOOD_HOLD_MINUTES = 30

# Which sprite represents which mood. Filenames must exist in SPRITE_DIR.
MOODS = {
    "idle":     "plain.png",       # neutral wandering
    "happy":    "heart.png",       # after you complete a reminder / happy button
    "excited":  "bee.png",         # grabbing attention (pre-warn wiggle)
    "music":    "headphones.png",  # music playing
    "sleepy":   "sleeping.png",    # ignored too long
    "sad":      "sleeping.png",    # sad button (same droopy capy)
    "water":    "swimming.png",    # water reminder
    "snack":    "apple.png",       # snack / walk reminder
    "cute":     "orange_hat.png",  # random flavor
    "citrus":   "oranges.png",     # citrus mode
    "drinking": "boba.png",        # drinking button
    "working":  "working.png",     # focus / new task added
    "exercise": "exercise.png",    # walk / exercise reminder
}

# Map each reminder to the sprite it shows while nagging.
REMINDER_SPRITE = {"water": "water", "walk": "exercise", "work": "working", "todo": "cute"}

USE_VOICE = False  # if True, speak reminders. Off by default; a sound plays instead.

# macOS system sound played when a reminder fires (any name from
# /System/Library/Sounds, without extension). e.g. Ping, Pop, Glass, Submarine.
NOTIFY_SOUND = "Ping"


def mac_say(text: str):
    if USE_VOICE:
        try:
            subprocess.Popen(["say", text])
        except Exception:
            pass


def play_sound():
    """Short attention sound instead of a spoken reminder."""
    try:
        path = f"/System/Library/Sounds/{NOTIFY_SOUND}.aiff"
        subprocess.Popen(["afplay", path])
    except Exception:
        pass


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def read_all_todos():
    """Return list of (line_index, text, done) for every task line."""
    out = []
    try:
        with open(TODO_FILE) as f:
            for i, ln in enumerate(f):
                s = ln.strip()
                if not s or s.startswith("#"):
                    continue
                done = s[:3].lower() == "[x]"
                if done or s.startswith("[ ]"):
                    text = s[3:].strip()
                else:
                    text = s
                out.append((i, text, done))
    except FileNotFoundError:
        pass
    return out


def add_todo(text):
    """Append a new pending task."""
    try:
        with open(TODO_FILE, "a") as f:
            f.write(f"[ ] {text.strip()}\n")
    except Exception:
        pass


def delete_todo(line_index):
    """Remove a task line entirely."""
    try:
        with open(TODO_FILE) as f:
            lines = f.readlines()
        if 0 <= line_index < len(lines):
            del lines[line_index]
            with open(TODO_FILE, "w") as f:
                f.writelines(lines)
    except Exception:
        pass


def edit_todo_text(line_index, new_text):
    """Rewrite a task's text, preserving its done state."""
    try:
        with open(TODO_FILE) as f:
            lines = f.readlines()
        if 0 <= line_index < len(lines):
            s = lines[line_index].strip()
            done = s[:3].lower() == "[x]"
            lines[line_index] = f"{'[x]' if done else '[ ]'} {new_text.strip()}\n"
            with open(TODO_FILE, "w") as f:
                f.writelines(lines)
    except Exception:
        pass


def set_todo_done(line_index, done):
    """Set or clear the [x] on a given line."""
    try:
        with open(TODO_FILE) as f:
            lines = f.readlines()
        if 0 <= line_index < len(lines):
            s = lines[line_index].strip()
            if s[:3].lower() in ("[x]", "[ ]"):
                body = s[3:].strip()
            else:
                body = s
            lines[line_index] = f"{'[x]' if done else '[ ]'} {body}\n"
            with open(TODO_FILE, "w") as f:
                f.writelines(lines)
    except Exception:
        pass


def read_todos():
    """Return a list of (line_index, text) for pending (unchecked) tasks."""
    out = []
    try:
        with open(TODO_FILE) as f:
            for i, ln in enumerate(f):
                s = ln.strip()
                if not s or s.startswith("#"):
                    continue
                if s.startswith("[x]") or s.startswith("[X]"):
                    continue  # already done
                text = s[3:].strip() if s.startswith("[ ]") else s
                out.append((i, text))
    except FileNotFoundError:
        pass
    return out


def mark_todo_done(line_index):
    """Prefix the given line with [x] so it stops nagging."""
    try:
        with open(TODO_FILE) as f:
            lines = f.readlines()
        if 0 <= line_index < len(lines):
            s = lines[line_index].strip()
            body = s[3:].strip() if s.startswith("[ ]") else s
            lines[line_index] = f"[x] {body}\n"
            with open(TODO_FILE, "w") as f:
                f.writelines(lines)
    except Exception:
        pass


def spotify_now_playing():
    """Return the track string if Spotify or Apple Music is playing, else None.

    Uses AppleScript. Only queries an app if it's already running, so it never
    launches Spotify/Music itself.
    """
    script = '''
    on isRunning(appName)
        tell application "System Events" to (name of processes) contains appName
    end isRunning
    set out to ""
    if isRunning("Spotify") then
        tell application "Spotify"
            if player state is playing then
                set out to (artist of current track) & " - " & (name of current track)
            end if
        end tell
    end if
    if out is "" and isRunning("Music") then
        tell application "Music"
            if player state is playing then
                set out to (artist of current track) & " - " & (name of current track)
            end if
        end tell
    end if
    return out
    '''
    try:
        res = subprocess.run(["osascript", "-e", script],
                             capture_output=True, text=True, timeout=3)
        out = res.stdout.strip()
        return out or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Speech bubble
# ---------------------------------------------------------------------------
class Bubble(QtWidgets.QWidget):
    PAD_X = 16          # inner horizontal text padding
    PAD_Y = 11          # inner vertical text padding
    MARGIN = 10         # room around the card for shadow + tail
    TAIL_H = 11         # tail height below the card
    RADIUS = 14

    def __init__(self):
        super().__init__(
            None,
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.WindowTransparentForInput
            | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self._text = ""
        self.hide()

    def _font(self):
        f = QtGui.QFont()
        # Use the system UI font for a native, non-crappy look.
        f.setFamilies(["SF Pro Text", "Helvetica Neue", "Arial"])
        f.setPointSize(13)
        f.setWeight(QtGui.QFont.Weight.DemiBold)
        return f

    def show_text(self, text: str):
        self._text = text
        fm = QtGui.QFontMetrics(self._font())
        max_text_w = 260
        # measure wrapped text
        rect = fm.boundingRect(0, 0, max_text_w, 1000,
                               int(QtCore.Qt.TextFlag.TextWordWrap
                                   | QtCore.Qt.AlignmentFlag.AlignHCenter), text)
        self._text_w = min(max_text_w, rect.width())
        self._text_h = rect.height()
        w = self._text_w + self.PAD_X * 2 + self.MARGIN * 2
        h = self._text_h + self.PAD_Y * 2 + self.MARGIN * 2 + self.TAIL_H
        self.resize(int(w), int(h))
        self.update()
        self.show()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        m = self.MARGIN
        card = QtCore.QRectF(
            m, m,
            self.width() - 2 * m,
            self.height() - 2 * m - self.TAIL_H,
        )

        # build card + tail as one shape so there's no seam
        path = QtGui.QPainterPath()
        path.addRoundedRect(card, self.RADIUS, self.RADIUS)
        cx = card.center().x()
        tail = QtGui.QPainterPath()
        tail.moveTo(cx - 9, card.bottom() - 1)
        tail.lineTo(cx, card.bottom() + self.TAIL_H)
        tail.lineTo(cx + 9, card.bottom() - 1)
        tail.closeSubpath()
        path = path.united(tail)

        # soft drop shadow
        p.save()
        p.translate(0, 2)
        p.fillPath(path, QtGui.QColor(0, 0, 0, 60))
        p.restore()

        # fill + subtle border
        p.fillPath(path, QtGui.QColor(33, 33, 38, 240))
        pen = QtGui.QPen(QtGui.QColor(255, 205, 100, 230), 1.6)
        p.setPen(pen)
        p.drawPath(path)

        # text
        p.setPen(QtGui.QColor(245, 245, 248))
        p.setFont(self._font())
        text_rect = card.adjusted(self.PAD_X, self.PAD_Y - 1,
                                  -self.PAD_X, -self.PAD_Y)
        p.drawText(text_rect,
                   int(QtCore.Qt.TextFlag.TextWordWrap
                       | QtCore.Qt.AlignmentFlag.AlignCenter),
                   self._text)


# ---------------------------------------------------------------------------
# The pet
# ---------------------------------------------------------------------------
class Capy(QtWidgets.QWidget):
    def __init__(self):
        super().__init__(
            None,
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)

        self.sprites = self._load_sprites()
        self.mood = "idle"
        self.facing = -1                       # -1 left, +1 right
        self.pix = self.sprites["idle"][self.facing]
        self.resize(self.pix.size())

        self.bubble = Bubble()

        # state machine: "wander" or "nag"
        self.state = "wander"
        self.active_reminder = None
        self.nag_bounce = 0.0
        self.ignore_ticks = 0
        self.paused = False              # reminders paused via menu bar
        self.hidden = False
        self._held_mood = None           # sticky manual mood (persists ~30 min)
        self._celebrating = False        # true during a task-done bee celebration
        self._hold_timer = QtCore.QTimer(self)
        self._hide_after_reminder = QtCore.QTimer(self)
        self._hide_after_reminder.setSingleShot(True)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._release_held_mood)
        self._active_todo_line = None    # which todos.txt line is being nagged
        self._prewarn_until = 0          # ticks remaining for heads-up wiggle
        self._drag_offset = None         # mouse-drag bookkeeping
        self._press_pos = None
        self._moved = False

        # availableGeometry() excludes the dock and menu bar, so the pet walks
        # on top of the dock's upper edge instead of hiding behind it.
        scr = QtWidgets.QApplication.primaryScreen()
        avail = scr.availableGeometry()
        self.screen_w = avail.width()
        self.screen_x0 = avail.x()
        self.floor_y = avail.y() + avail.height() - PET_HEIGHT - DOCK_LIFT
        self.x = float(self.screen_x0 + random.randint(0, max(1, self.screen_w - self.pix.width())))
        self.y = float(self.floor_y)
        self.target_x = self._new_target()
        self.move(int(self.x), int(self.y))

        # load saved config (custom reminders, spotify toggle)
        self.config = load_config()
        self.custom_reminders = self.config.get("custom_reminders", {})
        self.spotify_react = self.config.get("spotify_react", SPOTIFY_REACT_DEFAULT)
        self._music_on = False
        self._todo_index = 0
        self.citrus_mode = self.config.get("citrus_mode", False)

        # main loop
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(TICK_MS)

        # schedule built-in + custom reminders
        self._reminder_timers = {}
        for name in list(REMINDERS) + list(self.custom_reminders):
            self._start_reminder_timer(name)

        # todo nagging
        self.todo_timer = QtCore.QTimer(self)
        self.todo_timer.timeout.connect(self._on_todo_due)
        self.todo_timer.start(max(1, TODO_MINUTES) * 60 * 1000)

        # spotify polling
        self.spotify_timer = QtCore.QTimer(self)
        self.spotify_timer.timeout.connect(self.check_music)
        self.spotify_timer.start(SPOTIFY_POLL_SEC * 1000)

        # occasional mood flavor while wandering
        self.flavor = QtCore.QTimer(self)
        self.flavor.timeout.connect(self._random_flavor)
        self.flavor.start(20 * 1000)

        self._setup_tray()

    def _setup_tray(self):
        self.tray = None
        self._status_item = None
        try:
            preferred = ["logo.png", "plain.png", "heart.png"]
            pix = None
            for name in preferred:
                path = os.path.join(SPRITE_DIR, name)
                candidate = QtGui.QPixmap(path)
                if not candidate.isNull():
                    pix = candidate
                    break
            if pix is None:
                pix = QtGui.QPixmap(40, 40)
                pix.fill(QtCore.Qt.GlobalColor.transparent)
                p = QtGui.QPainter(pix)
                p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
                p.setBrush(QtGui.QColor(0, 0, 0))
                p.drawRect(0, 0, 39, 39)
                p.end()
            else:
                pix = pix.scaled(30, 30,
                                 QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 QtCore.Qt.TransformationMode.SmoothTransformation)
                if pix.hasAlphaChannel():
                    alpha = pix.toImage()
                    for y in range(alpha.height()):
                        for x in range(alpha.width()):
                            color = alpha.pixelColor(x, y)
                            if color.alpha() > 0:
                                color.setAlpha(int(color.alpha() * 0.8))
                                alpha.setPixelColor(x, y, color)
                    pix = QtGui.QPixmap.fromImage(alpha)
            icon = QtGui.QIcon(pix)
            self.tray = QtWidgets.QSystemTrayIcon(icon)
            menu = QtWidgets.QMenu()
            menu.addAction("Show Cappy", self.show_pet)
            menu.addAction("Hide Cappy", self.hide_pet)
            menu.addSeparator()
            menu.addAction("Quit Cappy", QtWidgets.QApplication.quit)
            self.tray.setContextMenu(menu)
            self.tray.show()
            return
        except Exception:
            pass

        try:
            from AppKit import NSStatusBar, NSVariableStatusItemLength, NSMenu, NSMenuItem
            bar = NSStatusBar.systemStatusBar()
            item = bar.statusItemWithLength_(NSVariableStatusItemLength)
            item.setTitle_("C")
            item.setToolTip_("Cappy")
            menu = NSMenu.alloc().init()
            for title, action in [
                ("Show Cappy", "showPet:"),
                ("Hide Cappy", "hidePet:"),
                ("Quit Cappy", "quitCappy:"),
            ]:
                mitem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
                mitem.setTarget_(self)
                menu.addItem_(mitem)
            item.setMenu_(menu)
            self._status_item = item
            self._status_menu = menu
        except Exception:
            self._status_item = None
            self._status_menu = None

    def showPet_(self, _sender=None):
        self.show_pet()

    def hidePet_(self, _sender=None):
        self.hide_pet()

    def quitCappy_(self, _sender=None):
        QtWidgets.QApplication.quit()

    def show_pet(self):
        self.hidden = False
        self.show()
        self.raise_()
        self.move(int(self.x), int(self.y))
        self._place_bubble()

    def hide_pet(self):
        self.hidden = True
        self.bubble.hide()
        self.hide()

    # -- sprite loading ------------------------------------------------------
    def _load_sprites(self):
        out = {}
        for mood, fname in MOODS.items():
            path = os.path.join(SPRITE_DIR, fname)
            img = QtGui.QPixmap(path)
            if img.isNull():
                # fallback: transparent placeholder
                img = QtGui.QPixmap(PET_HEIGHT, PET_HEIGHT)
                img.fill(QtCore.Qt.GlobalColor.transparent)
            scaled = img.scaledToHeight(
                PET_HEIGHT, QtCore.Qt.TransformationMode.SmoothTransformation
            )
            flipped = scaled.transformed(QtGui.QTransform().scale(-1, 1))
            out[mood] = {-1: scaled, +1: flipped}
        return out

    def set_mood(self, mood):
        # a sticky manual mood overrides the default idle sprite
        if mood == "idle" and getattr(self, "_held_mood", None):
            mood = self._held_mood
        # in citrus mode, the neutral wandering sprite becomes the citrus capy
        elif mood == "idle" and getattr(self, "citrus_mode", False):
            mood = "citrus"
        self.mood = mood if mood in self.sprites else "idle"
        self._refresh_pix()

    def hold_mood(self, mood, bubble=None):
        """Set a mood that sticks for MOOD_HOLD_MINUTES or until changed again."""
        self._held_mood = mood
        self.set_mood(mood)
        if bubble:
            self._say_bubble(bubble, 2000)
        self._hold_timer.start(MOOD_HOLD_MINUTES * 60 * 1000)

    def _release_held_mood(self):
        self._held_mood = None
        if self.state == "wander" and not self._music_on:
            self.set_mood("idle")

    def _refresh_pix(self):
        self.pix = self.sprites[self.mood][self.facing]
        self.resize(self.pix.size())
        self.update()

    # -- painting ------------------------------------------------------------
    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.drawPixmap(0, 0, self.pix)

    # -- interaction ---------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self._press_pos = e.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._moved = False
        e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_offset is not None:
            new_pos = e.globalPosition().toPoint() - self._drag_offset
            self.x = float(new_pos.x())
            self.y = float(new_pos.y())
            self.move(int(self.x), int(self.y))
            self._place_bubble()
            if (e.globalPosition().toPoint() - self._press_pos).manhattanLength() > 6:
                self._moved = True
        e.accept()

    def mouseReleaseEvent(self, e):
        was_drag = self._moved
        self._drag_offset = None
        self._press_pos = None
        self._moved = False
        if was_drag:
            # snap back down to the floor after being dropped
            self.y = float(self.floor_y)
            self.move(int(self.x), int(self.y))
            e.accept()
            return
        # treated as a click:
        if self.state == "nag":
            self.complete_reminder()
        else:
            self.set_mood("happy")
            self._say_bubble("♥", 1500)
            QtCore.QTimer.singleShot(1500,
                lambda: (self.state == "wander" and not self._music_on) and self.set_mood("idle"))
        e.accept()

    def contextMenuEvent(self, e):
        m = QtWidgets.QMenu()
        if self.state == "nag":
            m.addAction("✓ Done", self.complete_reminder)
            m.addAction(f"Snooze {SNOOZE_MINUTES} min", self.snooze_reminder)
            m.addSeparator()
        if self.hidden:
            m.addAction("Show Cappy", self.show_pet)
        else:
            m.addAction("Hide Cappy", self.hide_pet)
        m.addSeparator()
        # trigger any currently-active reminder now
        if self.custom_reminders:
            trig = m.addMenu("Remind me now")
            for name in list(self.custom_reminders):
                trig.addAction(name, lambda n=name: self.fire_reminder(n, from_menu=True))
        if read_todos():
            m.addAction("Remind me of a todo", lambda: self.fire_todo(from_menu=True))
        m.addSeparator()
        mood = m.addMenu("Set mood")
        mood.addAction("Happy 💛", lambda: self.show_mood("happy", "♥"))
        mood.addAction("Sad 😔", lambda: self.show_mood("sad", "..."))
        mood.addAction("Drinking 🧋", lambda: self.show_mood("drinking", "slurp~"))
        mood.addAction("Working 💻", lambda: self.show_mood("working", "focus!"))
        mood.addAction("Exercise 🏋️", lambda: self.show_mood("exercise", "let's move!"))
        mood.addAction("Excited ⭐", lambda: self.show_mood("excited", "!!"))
        mood.addSeparator()
        mood.addAction("Back to normal", self._release_held_mood)
        citrus = m.addAction("Citrus mode 🍊")
        citrus.setCheckable(True)
        citrus.setChecked(self.citrus_mode)
        citrus.toggled.connect(self.set_citrus_mode)
        m.addSeparator()
        pause = m.addAction("Pause reminders")
        pause.setCheckable(True)
        pause.setChecked(self.paused)
        pause.toggled.connect(self.set_paused)
        # add a reminder: quick presets + fully custom
        addmenu = m.addMenu("Add reminder")
        for key, cfg in PRESET_REMINDERS.items():
            label = f"{cfg['emoji']} {key} (every {cfg['minutes']}m)"
            addmenu.addAction(label, lambda k=key, c=cfg: self.add_preset_reminder(k, c))
        addmenu.addSeparator()
        addmenu.addAction("Custom…", self.add_custom_reminder)
        if self.custom_reminders:
            em = m.addMenu("Edit reminder")
            for name in list(self.custom_reminders):
                cfg = self.custom_reminders[name]
                em.addAction(f"{name} (every {cfg['minutes']}m)",
                             lambda n=name: self.edit_reminder(n))
            rm = m.addMenu("Remove reminder")
            for name in list(self.custom_reminders):
                rm.addAction(name, lambda n=name: self.remove_custom_reminder(n))
        m.addAction("Todos…", self.show_todo_checklist)
        spot = m.addAction("React to Spotify/Music")
        spot.setCheckable(True)
        spot.setChecked(self.spotify_react)
        spot.toggled.connect(self.set_spotify_react)
        m.addSeparator()
        m.addAction("Quit Cappy", QtWidgets.QApplication.quit)
        m.exec(e.globalPos())

    def set_paused(self, on):
        self.paused = on
        self._say_bubble("reminders paused 😴" if on else "back on! 💪", 1800)
        if hasattr(self, "tray"):
            self._sync_tray()

    def flash_mood(self, mood, seconds=3.0, bubble=None):
        """Show a mood briefly (unless nagging), then return to idle."""
        if self.state == "nag":
            return
        self.set_mood(mood)
        if bubble:
            self._say_bubble(bubble, int(seconds * 1000))
        QtCore.QTimer.singleShot(
            int(seconds * 1000),
            lambda: (self.state == "wander" and not self._music_on) and self.set_mood("idle"))

    def show_mood(self, mood, bubble=None):
        """Manual mood button: sticks for MOOD_HOLD_MINUTES or until changed."""
        self.hold_mood(mood, bubble=bubble)

    def set_citrus_mode(self, on):
        self.citrus_mode = on
        self.config["citrus_mode"] = on
        save_config(self.config)
        if self.state == "wander" and not self._music_on:
            self.set_mood("idle")   # will resolve to citrus if on
        self._say_bubble("citrus mode! 🍊" if on else "citrus off", 1800)

    # -- custom reminders / todos / settings ---------------------------------
    def add_preset_reminder(self, key, cfg):
        self.custom_reminders[key] = dict(cfg)
        self.config["custom_reminders"] = self.custom_reminders
        save_config(self.config)
        self._start_reminder_timer(key)
        self.flash_mood("citrus", 4.0, bubble=f"{cfg['emoji']} {key} every {cfg['minutes']}m 🍊")

    def add_custom_reminder(self):
        text, ok = QtWidgets.QInputDialog.getText(
            None, "New reminder", "What should I remind you about?")
        if not ok or not text.strip():
            return
        mins, ok = QtWidgets.QInputDialog.getInt(
            None, "How often?", "Every how many minutes?", 30, 1, 24 * 60, 1)
        if not ok:
            return
        name = text.strip()[:24]
        self.custom_reminders[name] = {
            "minutes": mins, "text": text.strip(), "emoji": "⏰",
            "say": f"Reminder: {text.strip()}",
        }
        self.config["custom_reminders"] = self.custom_reminders
        save_config(self.config)
        self._start_reminder_timer(name)
        self.flash_mood("citrus", 4.0, bubble=f"new task! every {mins} min 🍊")

    def remove_custom_reminder(self, name):
        self.custom_reminders.pop(name, None)
        t = self._reminder_timers.pop(name, None)
        if t:
            t.stop()
        self.config["custom_reminders"] = self.custom_reminders
        save_config(self.config)

    def edit_reminder(self, name):
        cfg = self.custom_reminders.get(name)
        if not cfg:
            return
        text, ok = QtWidgets.QInputDialog.getText(
            None, "Edit reminder", "Reminder text:", text=cfg.get("text", name))
        if not ok or not text.strip():
            return
        mins, ok = QtWidgets.QInputDialog.getInt(
            None, "How often?", "Every how many minutes?",
            cfg.get("minutes", 30), 1, 24 * 60, 1)
        if not ok:
            return
        # stop the old timer; key stays the same so we just update in place
        old = self._reminder_timers.pop(name, None)
        if old:
            old.stop()
        cfg["text"] = text.strip()
        cfg["minutes"] = mins
        cfg["say"] = f"Reminder: {text.strip()}"
        self.custom_reminders[name] = cfg
        self.config["custom_reminders"] = self.custom_reminders
        save_config(self.config)
        self._start_reminder_timer(name)
        self._say_bubble(f"updated! every {mins} min ✏️", 2000)

    def edit_todos(self):
        # now opens the in-app manager instead of a text file
        self.show_todo_checklist()

    def show_todo_checklist(self):
        """In-app todo manager: check off, edit, delete, and add — no text file."""
        dlg = QtWidgets.QDialog()
        dlg.setWindowTitle("Cappy — Todos")
        dlg.setWindowFlag(QtCore.Qt.WindowType.WindowStaysOnTopHint, True)
        dlg.setMinimumWidth(320)
        outer = QtWidgets.QVBoxLayout(dlg)
        list_box = QtWidgets.QVBoxLayout()
        outer.addLayout(list_box)

        def clear_layout(lay):
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    clear_layout(item.layout())
                    item.layout().deleteLater()

        def refresh():
            clear_layout(list_box)
            items = read_all_todos()
            if not items:
                list_box.addWidget(QtWidgets.QLabel("No tasks yet — add one below."))
            for line_idx, text, done in items:
                row = QtWidgets.QHBoxLayout()
                cb = QtWidgets.QCheckBox(text)
                cb.setChecked(done)
                cb.toggled.connect(lambda st, li=line_idx: self._on_todo_checkbox(st, li))
                edit_b = QtWidgets.QPushButton("✎"); edit_b.setFixedWidth(32)
                edit_b.clicked.connect(lambda _, li=line_idx, t=text: do_edit(li, t))
                del_b = QtWidgets.QPushButton("🗑"); del_b.setFixedWidth(32)
                del_b.clicked.connect(lambda _, li=line_idx: (delete_todo(li),
                                                              setattr(self, "_todo_index", 0),
                                                              refresh()))
                row.addWidget(cb, 1); row.addWidget(edit_b); row.addWidget(del_b)
                list_box.addLayout(row)

        def do_edit(line_idx, old):
            text, ok = QtWidgets.QInputDialog.getText(dlg, "Edit task", "Task:", text=old)
            if ok and text.strip():
                edit_todo_text(line_idx, text.strip()); refresh()

        def do_add():
            text, ok = QtWidgets.QInputDialog.getText(dlg, "New task", "Task:")
            if ok and text.strip():
                add_todo(text.strip())
                self._todo_index = 0
                self.flash_mood("citrus", 4.0, bubble="got a new task! 🍊")
                refresh()

        refresh()
        outer.addSpacing(6)
        btns = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("＋ Add task"); add_btn.clicked.connect(do_add)
        close_btn = QtWidgets.QPushButton("Close"); close_btn.clicked.connect(dlg.accept)
        btns.addWidget(add_btn); btns.addWidget(close_btn)
        outer.addLayout(btns)
        dlg.exec()

    def _on_todo_checkbox(self, done, line_index):
        set_todo_done(line_index, done)
        self._todo_index = 0
        if done and self.state != "nag":
            self.celebrate(bubble="done! ⭐")

    def set_spotify_react(self, on):
        self.spotify_react = on
        self.config["spotify_react"] = on
        save_config(self.config)
        if not on and self._music_on:
            self._music_on = False
            if self.state == "wander":
                self.set_mood("idle")

    # -- reminders -----------------------------------------------------------
    def _all_reminders(self):
        merged = dict(REMINDERS)
        merged.update(self.custom_reminders)
        return merged

    def _start_reminder_timer(self, name):
        cfg = self._all_reminders().get(name)
        if not cfg:
            return
        old = self._reminder_timers.get(name)
        if old:
            old.stop()
        t = QtCore.QTimer(self)
        t.timeout.connect(lambda n=name: self._on_reminder_due(n))
        interval = max(1, cfg["minutes"]) * 60 * 1000
        t.start(interval)
        self._reminder_timers[name] = t

    def _on_reminder_due(self, name):
        # schedule the actual fire, and a heads-up wiggle PREWARN_SEC before it.
        # (called each interval; we do the wiggle then fire shortly after)
        self.prewarn()
        QtCore.QTimer.singleShot(PREWARN_SEC * 1000, lambda: self.fire_reminder(name))

    def prewarn(self):
        """Subtle heads-up: capy perks up and wiggles before a reminder."""
        if self.paused or self.state == "nag":
            return
        self._prewarn_until = int(3000 / TICK_MS)  # ~3s of wiggle
        self.set_mood("excited")
        self._say_bubble("hmm…", 2500)
        QtCore.QTimer.singleShot(2600, lambda: (self.state == "wander" and not self._music_on) and self.set_mood("idle"))

    def fire_reminder(self, name, from_menu=False):
        cfg = self._all_reminders().get(name)
        if not cfg:
            return
        # if paused, skip scheduled fires (but allow manual ones from the menu)
        if self.paused and not from_menu:
            return
        # if already nagging, don't stack
        if self.state == "nag" and not from_menu:
            return
        self.state = "nag"
        self.active_reminder = name
        self.ignore_ticks = 0
        self._prewarn_until = 0
        self.set_mood(REMINDER_SPRITE.get(name, "excited"))
        # run to the center of the screen to grab attention
        self.target_x = self.screen_x0 + self.screen_w / 2 - self.pix.width() / 2
        emoji = cfg.get("emoji", "⏰")
        self._say_bubble(f"{emoji} {cfg['text']}\n(click me!)", None)
        play_sound()
        mac_say(cfg.get("say", cfg["text"]))

    def _on_todo_due(self):
        if not read_todos():
            return
        self.prewarn()
        QtCore.QTimer.singleShot(PREWARN_SEC * 1000, self.fire_todo)

    def fire_todo(self, from_menu=False):
        if self.paused and not from_menu:
            return
        if self.state == "nag" and not from_menu:
            return
        todos = read_todos()
        if not todos:
            return
        # cycle through pending tasks one at a time
        self._todo_index %= len(todos)
        line_idx, task = todos[self._todo_index]
        self._todo_index += 1
        self._active_todo_line = line_idx
        self.state = "nag"
        self.active_reminder = "todo"
        self.ignore_ticks = 0
        self.set_mood(REMINDER_SPRITE.get("todo", "cute"))
        self.target_x = self.screen_x0 + self.screen_w / 2 - self.pix.width() / 2
        self._say_bubble(f"📋 {task}\n(click = done)", None)
        play_sound()
        mac_say(f"Reminder: {task}")

    def check_music(self):
        if not self.spotify_react or self.state == "nag" or getattr(self, "_celebrating", False):
            return
        playing = spotify_now_playing()
        if playing and not self._music_on:
            self._music_on = True
            self.set_mood("music")
        elif not playing and self._music_on:
            self._music_on = False
            if self.state == "wander":
                self.set_mood("idle")

    def complete_reminder(self):
        # if this was a todo, check it off so it stops nagging
        if self.active_reminder == "todo" and self._active_todo_line is not None:
            mark_todo_done(self._active_todo_line)
            self._active_todo_line = None
            self._todo_index = 0  # re-index against the now-shorter pending list
        was_todo = (self.active_reminder == "todo")
        self._last_reminder = self.active_reminder
        self.state = "wander"
        self.active_reminder = None
        self._hide_after_reminder.stop()
        self.celebrate(bubble="done! ⭐" if was_todo else "yay! ⭐")
        QtCore.QTimer.singleShot(AUTO_HIDE_AFTER_REMINDER_SEC * 1000, self.hide_pet)

    def celebrate(self, bubble="done! ⭐", seconds=4.0):
        """Show the bee capy in celebration, uninterrupted, then return to normal."""
        self._held_mood = None            # clear any sticky mood so we can return
        self._celebrating = True
        self.set_mood("excited")          # excited -> bee.png
        self._say_bubble(bubble, int(seconds * 1000))
        QtCore.QTimer.singleShot(int(seconds * 1000), self._end_celebration)

    def _end_celebration(self):
        self._celebrating = False
        self._back_to_idle()

    def snooze_reminder(self):
        """Delay the current reminder by SNOOZE_MINUTES and go back to wandering."""
        name = self.active_reminder
        self.state = "wander"
        self.active_reminder = None
        self._hide_after_reminder.stop()
        self.set_mood("idle")
        self._say_bubble(f"okay, {SNOOZE_MINUTES} min…", 1500)
        QtCore.QTimer.singleShot(1500, self._back_to_idle)
        QtCore.QTimer.singleShot(AUTO_HIDE_AFTER_REMINDER_SEC * 1000, self.hide_pet)
        if name == "todo":
            QtCore.QTimer.singleShot(SNOOZE_MINUTES * 60 * 1000, self.fire_todo)
        elif name:
            QtCore.QTimer.singleShot(SNOOZE_MINUTES * 60 * 1000,
                                     lambda n=name: self.fire_reminder(n))

    def _back_to_idle(self):
        self.set_mood("idle")
        self.bubble.hide()
        self.target_x = self._new_target()

    def _random_flavor(self):
        if self.state != "wander" or self._music_on or getattr(self, "_celebrating", False):
            return
        if random.random() < 0.4:
            mood = random.choice(["cute", "music", "idle", "idle"])
            self.set_mood(mood)
            QtCore.QTimer.singleShot(6000, lambda: (self.state == "wander" and not self._music_on) and self.set_mood("idle"))

    # -- movement loop -------------------------------------------------------
    def tick(self):
        if self.state == "nag":
            self._tick_nag()
        else:
            self._tick_wander()
        self.move(int(self.x), int(self.y))
        self._place_bubble()

    def _tick_wander(self):
        # heads-up wiggle before a reminder
        if self._prewarn_until > 0:
            self._prewarn_until -= 1
            import math
            self.y = self.floor_y - abs(math.sin(self._prewarn_until * 0.6)) * 10
            return
        dx = self.target_x - self.x
        if abs(dx) < WALK_SPEED:
            self.x = self.target_x
            # idle a moment then pick a new destination
            if random.random() < 0.02:
                self.target_x = self._new_target()
                self.set_mood("idle")
            return
        step = WALK_SPEED * (1 if dx > 0 else -1)
        new_facing = 1 if step > 0 else -1
        if new_facing != self.facing:
            self.facing = new_facing
            self._refresh_pix()
        self.x += step
        # subtle walk bob
        self.y = self.floor_y - (2 if int(self.x) % 20 < 10 else 0)

    def _tick_nag(self):
        # walk to center, then bounce and get sadder the longer ignored
        dx = self.target_x - self.x
        if abs(dx) > WALK_SPEED:
            step = WALK_SPEED * 1.6 * (1 if dx > 0 else -1)
            nf = 1 if step > 0 else -1
            if nf != self.facing:
                self.facing = nf
                self._refresh_pix()
            self.x += step
            return
        # arrived: bounce for attention
        self.nag_bounce += 0.25
        import math
        self.y = self.floor_y - abs(math.sin(self.nag_bounce)) * 22
        self.ignore_ticks += 1
        # if ignored for a long time (~25s), get sad/sleepy
        if self.ignore_ticks == int(25000 / TICK_MS):
            self.set_mood("sleepy") if "sleepy" in self.sprites else self.set_mood("sleepy")
            self._say_bubble("...you forgot about me :(", None)

    def _new_target(self):
        return float(self.screen_x0 + random.randint(0, max(1, self.screen_w - self.pix.width())))

    # -- bubble placement ----------------------------------------------------
    def _say_bubble(self, text, ms):
        self.bubble.show_text(text)
        self._place_bubble()
        if ms:
            QtCore.QTimer.singleShot(ms, self.bubble.hide)

    def _place_bubble(self):
        if not self.bubble.isVisible():
            return
        bx = int(self.x + self.pix.width() / 2 - self.bubble.width() / 2)
        # tail tip sits MARGIN px above the window's bottom edge; place it just
        # above the capy's head with a small gap.
        by = int(self.y - self.bubble.height() + self.bubble.MARGIN - 2)
        bx = max(self.screen_x0 + 4,
                 min(bx, self.screen_x0 + self.screen_w - self.bubble.width() - 4))
        self.bubble.move(bx, by)


INSTANCE_LOCK_PATH = os.path.join(BASE_DIR, ".cappy.lock")
_INSTANCE_LOCK_FD = None


def acquire_single_instance_lock(lock_path=INSTANCE_LOCK_PATH):
    """Return True if this is the only running Cappy instance."""
    global _INSTANCE_LOCK_FD
    try:
        fd = open(lock_path, "a+")
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fd.close()
            return False
        _INSTANCE_LOCK_FD = fd
        atexit.register(release_single_instance_lock)
        return True
    except Exception:
        return False


def release_single_instance_lock():
    global _INSTANCE_LOCK_FD
    if _INSTANCE_LOCK_FD is not None:
        try:
            fcntl.flock(_INSTANCE_LOCK_FD.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            _INSTANCE_LOCK_FD.close()
        except Exception:
            pass
        _INSTANCE_LOCK_FD = None


def _hide_from_dock():
    """Make this a background/agent app: no Dock icon, not in Cmd-Tab.

    Uses macOS's accessory activation policy. The capy window still shows.
    Safe no-op if not on macOS or if pyobjc isn't available.
    """
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory)
    except Exception:
        pass


def main():
    if not acquire_single_instance_lock():
        return 0

    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _hide_from_dock()
    pet = Capy()
    pet.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
