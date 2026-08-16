# 🦫 Cappy — your desktop capybara companion

A tiny pixel-art capybara that lives at the bottom of your Mac screen, wanders
across your dock, and reminds you to **drink water, walk, and get back to work**.
It reacts with moods — happy, sad/sleepy, excited — and runs to the middle of the
screen to grab your attention when a reminder is due. Click it to say "done" and
it gets happy again.

Built from your own uploaded capybara pixel art (backgrounds removed).

---

## Run it (macOS)

```bash
cd Cappy
chmod +x run.sh
./run.sh
```

The first run makes a small virtual environment and installs PyQt6
(~30 seconds). After that it launches instantly.

To let it use a **spoken voice** for reminders, nothing extra is needed — it uses
the built-in macOS `say` command.

### Quit
Right-click the capybara → **Quit Cappy**.

### No Dock icon (background app)
Cappy runs as a background/agent app: it does **not** show an icon in the Dock
or in the Cmd-Tab switcher — only the capy itself is visible on screen. Because
there's no Dock icon, quit it by right-clicking the capy → **Quit Cappy**.
(This needs the `pyobjc-framework-Cocoa` package, installed automatically by
`run.sh`. If it's missing, Cappy still runs — it just shows a Dock icon.)

---

## What it does

- **Wanders** along the bottom of the screen, over the dock, changing direction
  and mood as it goes.
- **Reminders** fire on a schedule (defaults below). When one fires, the capy
  runs to the center, bounces, shows a speech bubble, and speaks the reminder.
- **Your own todo list** — put tasks in `todos.txt` (one per line) and the capy
  nags you about each, one at a time, every 20 min.
- **Spotify / Apple Music aware** — while music is actually playing, the capy
  puts on its headphones 🎧 and takes them off when the music stops.
- **Click it** while it's nagging → it's satisfied and turns happy 💛.
- **Ignore it** too long → it gets sad/sleepy 😴 until you click it.
- **Right-click** → trigger any reminder, add/remove a custom reminder, edit the
  todo list, toggle the Spotify reaction, or quit.

---

## Your todo list

Edit `todos.txt` in the Cappy folder (or right-click the capy → **Edit todo
list…**). One task per line; lines starting with `#` are ignored:

```
Reply to pending emails
Review the pull request
Prep notes for standup
```

The capy cycles through them, reminding you of the next one every 20 minutes
(change `TODO_MINUTES` in `app.py`). Edits take effect immediately — no restart.

## Custom reminders

Right-click → **Add custom reminder…**, type the message and how often (in
minutes). It's saved to `cappy_config.json` and persists across restarts.
Remove one via right-click → **Remove custom reminder**.

## Spotify / Apple Music reaction

On by default. The capy checks every few seconds whether Spotify or Apple Music
is *playing* (it never launches them itself) and wears headphones while music is
on. Toggle it from the right-click menu. The **first time**, macOS will ask for
permission to control Spotify/Music — click **OK** (needed for it to read what's
playing). If you deny it, the feature just stays off and everything else works.

---

## Customize

Open `cappy/app.py` and edit the config block near the top.

**Reminder timing & text** — `REMINDERS`:
```python
REMINDERS = {
    "water": {"minutes": 30, ...},
    "walk":  {"minutes": 50, ...},
    "work":  {"minutes": 45, ...},
}
```

**Size** — `PET_HEIGHT` (default 110 px).

**Speed** — `WALK_SPEED`.

**Voice on/off** — `USE_VOICE = True/False`.

**Which sprite = which mood** — the `MOODS` dict maps moods to the PNGs in
`cappy/sprites/`. Swap filenames to reassign. Your sprites:

| file | used for |
|------|----------|
| `plain.png` | idle / wandering |
| `heart.png` | happy (reminder done, or petting) |
| `bee.png` | excited |
| `headphones.png` | work / focus |
| `sleeping.png` | sad / ignored |
| `swimming.png` | water reminder |
| `apple.png` | walk / snack reminder |
| `orange_hat.png` | random cute flavor |

---

## Start automatically at login (optional)

1. Copy the full path: `pwd` inside the `Cappy` folder.
2. System Settings → General → Login Items → **＋** → choose `run.sh`
   (or make a tiny Automator "Application" that runs `./run.sh`).

---

## Notes / troubleshooting

- **It sits behind the dock:** the pet is always-on-top, but macOS may draw the
  dock above it in some spaces. Increase `PET_HEIGHT` or lower `floor_y` in
  `app.py` (`self.floor_y = ...`) to nudge it up.
- **No voice:** set `USE_VOICE = False` if you don't want it talking, or check
  your system volume.
- **Wrong Python:** needs Python 3.9+. `python3 --version` to check.
