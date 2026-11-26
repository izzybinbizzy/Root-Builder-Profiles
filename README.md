# Root Builder Profiles - a Mod Organizer 2 plugin

Copyright (C) 2026 izzydoingit. GPL-3.0-or-later, see `LICENSE`.

An add-on for Kezyma's [Root Builder](https://github.com/Kezyma/ModOrganizer-Plugins) (copy mode, autobuild on). It changes
nothing in Root Builder's code or settings; it runs after Root Builder's own Clear.

## What it does
- **Game-folder changes per profile.** When a program started from MO2 closes and Root Builder has cleared, the new files
  Root Builder put in `overwrite\Root` (shader caches, preset edits to files no mod owns, logs) move into a mod
  `Root Changes - <profile>`, ticked in that profile only. Without it every profile gets them. Files that were already in
  `overwrite\Root` when the add-on first starts are left where they are.
- **A clean game folder.** On start, on a profile change and after a program closes it looks for ENB / Effects 11 / ReShade
  preset files in the game folder that no mod deploys - a preset placed by hand before Root Builder, or one dropped in later -
  and offers to move them into a mod you name. Every copy is checked equal first; the game folder copies then go to the
  Recycle Bin, and when Root Builder had recorded them as game files its game snapshot and backup are renamed (never deleted),
  so it records the clean folder on its next build. Answer no and that same set is not asked about again until it changes.
- **Leftovers are never a preset.** A game-folder file that is an exact copy of a file in any mod's Root folder (ticked or
  not) is a deploy Root Builder could not clear while a game still held it. It is offered for removal (Recycle Bin; the mod
  keeps its copy), never moved into a preset mod.
- **Never while busy.** Nothing is judged while the game runs or Root Builder has a build deployed, and a file that a ticked
  mod's Root folder (or `overwrite\Root`) provides - same path or same contents - is never reported.
- **Tools menu:** "Root Builder Profiles" checks the game folder again (and forgets an earlier no).

Why: preset authors say to remove an old preset completely before installing a new one. Under Root Builder a hand-placed
preset and the shared `overwrite\Root` can keep one preset's files in every profile.

## Requires
Mod Organizer 2 2.5 and Root Builder (copy mode, autobuild on). Windows.

## Install
Through MO2's Plugin Finder, or copy the `rootbuilderprofiles` folder into `MO2\plugins`. Its log and state live in
`MO2\plugins\data\RootBuilderProfiles`. Both jobs can be switched off in MO2's plugin settings.

## Files
- `rootbuilderprofiles/__init__.py` - the MO2 part (callbacks, questions, settings).
- `rootbuilderprofiles/core.py` - the file work, testable on its own.
- `offline test.py` - runs the file work and the MO2 part against a made-up game folder and MO2 tree in the temp folder,
  through stand-ins for `mobase` and PyQt; nothing real is touched. `python "offline test.py"` ends with `RESULT: ALL PASS`.
