"""Offline test of Root Builder Profiles: core on a fake game/MO2 tree, then the MO2 glue through stub mobase/PyQt6.
The fake trees live in the system temp folder; nothing real is touched (the game check is stubbed, never tasklist).
Run: python "offline test.py"  -> last line RESULT: ALL PASS."""
import json, os, shutil, sys, tempfile, types
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).parent
SRC = HERE
# The long path: a short 8.3 TEMP (GitHub's runners have one) never matches the long path a Recycle Bin record holds.
W = Path(tempfile.gettempdir()).resolve() / "Root Builder Profiles offline test"
if W.exists():
    shutil.rmtree(W)
game, mo = W / "game", W / "mo2"
ow, mods, pdata = mo / "overwrite", mo / "mods", mo / "plugins" / "data"
rbdir = pdata / "RootBuilder" / "x" / "1_0"


def put(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


for rel in ["SkyrimSE.exe", "skse64_loader.exe", "enbseries.ini", "enbseries/w/cloudy.ini", "enbseries/a.fx", "Data/Skyrim.esm", "Skyrim/SkyrimPrefs.ini"]:
    put(game / rel, "game " + rel)
gamedata = {r.lower().replace("/", "\\"): {} for r in ["SkyrimSE.exe", "skse64_loader.exe", "enbseries.ini", "enbseries/w/cloudy.ini", "enbseries/a.fx", "Skyrim/SkyrimPrefs.ini"]}
put(rbdir / "GameData.json", json.dumps(gamedata))
put(rbdir / "Backup" / "SkyrimSE.exe", "bak")
put(ow / "Root" / "shot.png", "legacy screenshot")

fails = []


START = __import__("time").time()


def in_bin(path):
    """True when the Recycle Bin of path's drive holds a $I record naming path written by THIS run (the paths are the same
    every run, so an older run's record must not count; the record's path is UTF-16 from byte 28)"""
    want = str(path).lower()
    root = Path(str(path)[:3]) / "$Recycle.Bin"
    for rec in root.glob("*/$I*"):
        try:
            if rec.stat().st_mtime < START - 2:
                continue
            data = rec.read_bytes()
        except OSError:
            continue
        name = data[28:].decode("utf-16-le", errors="ignore").split("\x00", 1)[0].lower()
        if name == want:
            return True
    return False


def check(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)

# ---- glue through stubs ------------------------------------------------------------------------
calls = []
mobase = types.ModuleType("mobase")
class IPluginTool:
    def __init__(self): pass
mobase.IPluginTool = IPluginTool
mobase.VersionInfo = lambda *a: a
mobase.PluginSetting = lambda *a: a
mobase.PluginRequirementFactory = types.SimpleNamespace(pluginDependency=lambda names: ("needs", names), gameDependency=lambda g: g, basic=lambda *a: a)  # the names MO2 2.5.2's mobase really has
mobase.ModState = types.SimpleNamespace(ACTIVE=2)
sys.modules["mobase"] = mobase
qt = types.ModuleType("PyQt6"); core_m = types.ModuleType("PyQt6.QtCore"); w_m = types.ModuleType("PyQt6.QtWidgets"); g_m = types.ModuleType("PyQt6.QtGui")
core_m.QCoreApplication = types.SimpleNamespace(translate=lambda ctx, t: t)
core_m.QTimer = types.SimpleNamespace(singleShot=lambda ms, fn: fn())
class MB:
    class StandardButton: Yes = 1; No = 0
    answer = 1
    @staticmethod
    def question(*a): calls.append(("question", a[2][:60])); return MB.answer
    @staticmethod
    def warning(*a): calls.append(("warning", a[2][:80]))
    @staticmethod
    def information(*a): calls.append(("info", a[2][:60]))
w_m.QMessageBox = MB
class ID:
    reply = ("NAT ENB Preset - Game Root", True)
    @staticmethod
    def getText(parent, title, label, echo, default): calls.append(("name?", default)); return ID.reply
w_m.QInputDialog = ID
w_m.QLineEdit = types.SimpleNamespace(EchoMode=types.SimpleNamespace(Normal=0))
g_m.QIcon = lambda: None
sys.modules.update({"PyQt6": qt, "PyQt6.QtCore": core_m, "PyQt6.QtWidgets": w_m, "PyQt6.QtGui": g_m})
sys.path.insert(0, str(SRC))
from rootbuilderprofiles import core as C
RUNNING = [False]
C.game_running = lambda images=None: RUNNING[0]   # never the real tasklist

log = []
c = C.Core(game, ow, mods, rbdir, pdata / "RootBuilderProfiles", ["Saves", "Morrowind.ini", "Data", "Data Files"], say=log.append, running=lambda: RUNNING[0])
check(C.path_safe("D:/SteamLibrary/steamapps/common/Skyrim Special Edition") == "DSteamLibrarysteamappscommonSkyrim_Special_Edition", "path_safe matches Root Builder's folder name for a Steam library path")
check(C.path_safe("1.6.1170.0") == "1_6_1170_0", "path_safe on the version")
check(c.first_start() and not c.first_start(), "first start records once")
check(c.move_changes("P") == (None, 0, False), "nothing new -> nothing moved, legacy screenshot stays")
put(ow / "Root" / "enbcache" / "x.sc", "cache")
put(ow / "Root" / "enbseries" / "w" / "sunny.ini", "edited")
mod, n, created = c.move_changes("Profile A")
dest = mods / "Root Changes - Profile A"
check(n == 2 and created and (dest / "Root" / "enbcache" / "x.sc").read_text() == "cache", "two new files moved into the profile mod")
check((ow / "Root" / "shot.png").exists() and not (ow / "Root" / "enbcache").exists(), "legacy kept, empty folders gone")
check((dest / "meta.ini").exists(), "meta.ini written")
put(ow / "Root" / "enbcache" / "x.sc", "cache2")
check(c.move_changes("Profile A")[1] == 1 and (dest / "Root" / "enbcache" / "x.sc").read_text() == "cache2", "second run: newer file replaces the mod's copy")
put(rbdir / "BuildData.json", "{}")
check(c.build_deployed(), "a deployed build is seen")
try:
    c.adopt({}, "X"); check(False, "adopt refuses while deployed")
except RuntimeError:
    check(True, "adopt refuses while deployed")
(rbdir / "BuildData.json").unlink()
put(game / "d3d11.dll", "stray enb")
adoptable, strays = c.scan_game()
check(sorted(adoptable) == ["enbseries.ini", "enbseries\\a.fx", "enbseries\\w\\cloudy.ini"], f"adoptable = the hand-placed preset {sorted(adoptable)}")
check(sorted(strays) == ["d3d11.dll"], f"stray = the file Root Builder never saw {sorted(strays)}")
created, copied = c.adopt(adoptable, "NAT ENB Preset - Game Root")
pm = mods / "NAT ENB Preset - Game Root" / "Root"
check(created and copied == 3 and (pm / "enbseries" / "w" / "cloudy.ini").read_text() == "game enbseries/w/cloudy.ini", "preset copied into its mod")
check(not (game / "enbseries").exists() and not (game / "enbseries.ini").exists(), "game copies gone, empty folder removed")
check(in_bin(game / "enbseries.ini") and in_bin(game / "enbseries" / "w" / "cloudy.ini"), "the game copies are in the Recycle Bin (its $I records name them)")
check((game / "SkyrimSE.exe").exists() and (game / "Data" / "Skyrim.esm").exists() and (game / "d3d11.dll").exists(), "nothing else touched")
check(not (rbdir / "GameData.json").exists() and not (rbdir / "Backup").exists() and len(list(rbdir.iterdir())) == 2, "Root Builder snapshot + backup set aside, not deleted")
# existing mod with one different copy: game copy wins, all proven
put(game / "enbseries" / "b.ini", "game b")
put(mods / "M" / "Root" / "enbseries" / "b.ini", "old b")
c.adopt({"enbseries\\b.ini": game / "enbseries" / "b.ini"}, "M")
check((mods / "M" / "Root" / "enbseries" / "b.ini").read_text() == "game b", "existing mod: the game folder's version is kept")
# ---- 1.1.1: ticked mods' Root files left in the game folder are not strays ----
for f in list(game.iterdir()):
    if f.name.lower() not in ("skyrimse.exe", "skse64_loader.exe", "data", "skyrim"):
        shutil.rmtree(f) if f.is_dir() else f.unlink()
put(game / "d3d11.dll", "enb binary 0.505")
put(game / "D3DCompiler_46e.dll", "compiler 46e")
put(game / "enbseries" / "KiLoaderSatelliteENB.dllplugin", "kiloader satellite")
put(mods / "ENB Binaries 0.505" / "Root" / "d3d11.dll", "enb binary 0.505")
put(mods / "KiLoader" / "Root" / "enbseries" / "kiloadersatelliteenb.dllplugin", "kiloader satellite")      # same path, other case
put(mods / "Compiler Pack" / "Root" / "tools" / "d3dcompiler_46e.dll", "compiler 46e")                       # other path, same sha1
put(mods / "Unticked ENB" / "Root" / "reshade.ini", "x")
ticked = ["ENB Binaries 0.505", "KiLoader", "Compiler Pack"]
a, s_ = c.scan_game(ticked)
check(a == {} and s_ == {}, f"files a ticked mod's Root provides (by path, any case, or by sha1) are not strays {sorted(s_)}")
a, s_ = c.scan_game(["ENB Binaries 0.505"])
check(sorted(s_) == ["D3DCompiler_46e.dll", "enbseries\\KiLoaderSatelliteENB.dllplugin"], f"unticked -> those two are strays again {sorted(s_)}")
put(game / "d3d11.dll", "a different enb binary")
a, s_ = c.scan_game(ticked)
check(sorted(s_) == [], "same path as a ticked mod's file counts as provided even when the contents differ (a deploy left behind)")
put(game / "d3d11.dll", "enb binary 0.505")
put(game / "dxgi.dll", "reshade dll")
put(ow / "Root" / "dxgi.dll", "reshade dll")
a, s_ = c.scan_game(ticked)
check(s_ == {}, "a file overwrite\\Root provides (deployed on every profile) is not a stray")
(ow / "Root" / "dxgi.dll").unlink()
a, s_ = c.scan_game([])
check(sorted(s_) == ["D3DCompiler_46e.dll", "d3d11.dll", "dxgi.dll", "enbseries\\KiLoaderSatelliteENB.dllplugin"], f"nothing ticked -> all four are strays {sorted(s_)}")
RUNNING[0] = True
n = len(log); a, s_ = c.scan_game([])
check(a == {} and s_ == {} and c.busy_reason() == "the game is running" and "game is running" in log[n], "game running -> no scan at all")
RUNNING[0] = False
put(rbdir / "BuildData.json", "{}")
a, s_ = c.scan_game([])
check(a == {} and s_ == {} and c.busy_reason() == "Root Builder has a build deployed", "a live Root Builder deploy -> no scan at all")
(rbdir / "BuildData.json").unlink()
check(c.busy_reason() is None, "nothing deployed, game closed -> the check may run")
# ---- 1.2.0: ENB leftovers swept into overwrite\Root while a NON-ENB profile ran ----------
leftovers = mods / C.LEFTOVERS
def lo_files():
    return sorted(str(p.relative_to(leftovers)).split("\\", 1)[1] for p in leftovers.rglob("*") if p.is_file() and p.name != "meta.ini") if leftovers.exists() else []
put(ow / "Root" / "d3d11.dll", "enb binary 0.505")                       # a copy of ENB Binaries 0.505's file
put(ow / "Root" / "enblocal.ini", "written by ENB itself")              # new, ENB's own ini
put(ow / "Root" / "enbseries" / "KiLoaderSatelliteENB.dllplugin", "a satellite no mod has")
mod_, n_, created_ = c.move_changes("Profile B", [])        # Profile B ticks no Root mod
check(n_ == 0 and mod_ is None and not (mods / "Root Changes - Profile B").exists(), "a profile with no Root setup gets NO Root Changes mod")
check(lo_files() == ["d3d11.dll", "enblocal.ini", "enbseries\\KiLoaderSatelliteENB.dllplugin"] and c.last_leftovers == 3, f"all three set aside in Root Leftovers {lo_files()}")
check(not any((leftovers / d).is_dir() for d in ("Root",)) and not (ow / "Root" / "d3d11.dll").exists(), "set aside OUTSIDE any Root folder, overwrite\\Root emptied of them")
shutil.rmtree(leftovers)
put(mods / "NAT Preset" / "Root" / "enbseries" / "weather.ini", "nat")    # a CS profile: a Root mod, but no ENB
put(ow / "Root" / "enbseries" / "weather.ini", "a menu edit")
put(ow / "Root" / "d3d11.dll", "some other enb binary")
mod_, n_, created_ = c.move_changes("Default", ["NAT Preset"])
check(n_ == 1 and (mods / "Root Changes - Default" / "Root" / "enbseries" / "weather.ini").exists(), "a real preset edit still goes into the profile's changes mod")
check(lo_files() == ["d3d11.dll"] and not (mods / "Root Changes - Default" / "Root" / "d3d11.dll").exists(), "an ENB file under a profile without ENB is set aside")
shutil.rmtree(leftovers)
put(ow / "Root" / "d3d11.dll", "enb binary 0.505")
mod_, n_, created_ = c.move_changes("ENB TEST", ["ENB Binaries 0.505"])
check(n_ == 0 and lo_files() == ["d3d11.dll"], "even on an ENB profile, a byte copy of a mod's Root file is a leftover, not a change")
shutil.rmtree(leftovers)
put(ow / "Root" / "enblocal.ini", "an ENB menu edit")
mod_, n_, created_ = c.move_changes("ENB TEST", ["ENB Binaries 0.505"])
check(n_ == 1 and (mods / "Root Changes - ENB TEST" / "Root" / "enblocal.ini").exists() and lo_files() == [], "an ENB profile keeps its own ENB edits")
# ---- 1.3.0: copies of an UNTICKED mod's Root files left in the game folder (DXVK's two DLLs here) are leftovers, never a preset
for f in list(game.iterdir()):
    if f.name.lower() not in ("skyrimse.exe", "skse64_loader.exe", "data", "skyrim"):
        shutil.rmtree(f) if f.is_dir() else f.unlink()
put(game / "d3d11.dll", "dxvk d3d11"); put(game / "dxgi.dll", "dxvk dxgi")
put(mods / "TEST DXVK" / "Root" / "d3d11.dll", "dxvk d3d11"); put(mods / "TEST DXVK" / "Root" / "dxgi.dll", "dxvk dxgi")
a, s_ = c.scan_game([])
cp = c.copies_of_mod_roots({**a, **s_})
check(cp == {"d3d11.dll": "TEST DXVK", "dxgi.dll": "TEST DXVK"}, f"copies of an UNTICKED mod's Root files are named {cp}")
try:
    c.adopt(s_, "Preset from game folder")
    check(False, "adopt refuses a mod's leftover copies")
except RuntimeError:
    check(not (mods / "Preset from game folder").exists() and (game / "d3d11.dll").exists(), "adopt refuses a mod's leftover copies (nothing moved, no mod made)")
put(game / "enbseries.ini", "a real hand-placed preset")
cp = c.copies_of_mod_roots({"enbseries.ini": game / "enbseries.ini", "d3d11.dll": game / "d3d11.dll"})
check(cp == {"d3d11.dll": "TEST DXVK"}, "a real preset file is not a copy")
put(game / "dxgi.dll", "a different dxgi")
check(c.copies_of_mod_roots({"dxgi.dll": game / "dxgi.dll"}) == {}, "same name, other contents -> not a copy")
put(game / "dxgi.dll", "dxvk dxgi")
n_ = c.remove_copies({"d3d11.dll": game / "d3d11.dll", "dxgi.dll": game / "dxgi.dll"})
check(n_ == 2 and not (game / "d3d11.dll").exists() and (mods / "TEST DXVK" / "Root" / "d3d11.dll").exists() and (game / "enbseries.ini").exists(),
      "remove_copies: the game copies gone, the mod keeps its own, the real preset untouched")
(game / "enbseries.ini").unlink()
print("\n".join(log))

import rootbuilderprofiles as R

# fresh tree for the glue
shutil.rmtree(W)
for rel in ["SkyrimSE.exe", "enbseries.ini", "enbseries/a.fx"]:
    put(game / rel, "g " + rel)
put(pdata / "RootBuilder" / C.path_safe(str(game).replace("\\", "/")) / "1_0" / "GameData.json", json.dumps({"skyrimse.exe": {}, "enbseries.ini": {}, "enbseries\\a.fx": {}}))
settings = {"movechanges": True, "checkgame": True}
cb = {}
class ML:
    ticked = []
    def setActive(self, m, v): calls.append(("tick", m))
    def allModsByProfilePriority(self, profile=None): return ["Unticked Mod"] + ML.ticked
    def state(self, m): return 2 if m in ML.ticked else 1
class Org:
    def onFinishedRun(self, f): cb["run"] = f
    def onProfileChanged(self, f): cb["prof"] = f
    def onUserInterfaceInitialized(self, f): cb["ui"] = f
    def pluginSetting(self, p, k):
        if k == "enabled": return None  # MO2 2.5 keeps on/off itself
        return settings.get(k) if p == "RootBuilderProfiles" else "Saves,Morrowind.ini,Data,Data Files"
    def isPluginEnabled(self, name): return True
    def setPluginSetting(self, p, k, v): settings[k] = v
    def pluginDataPath(self): return str(pdata)
    def overwritePath(self): return str(ow)
    def modsPath(self): return str(mods)
    def profileName(self): return "Profile A"
    def refresh(self, save=True): calls.append(("refresh",))
    def onNextRefresh(self, f, imm=True): f()
    def modList(self): return ML()
    def managedGame(self):
        return types.SimpleNamespace(gameDirectory=lambda: types.SimpleNamespace(absolutePath=lambda: str(game).replace("\\", "/")), gameVersion=lambda: "1.0")
p = R.createPlugin()
check(p.init(Org()) is True and p.name() == "RootBuilderProfiles" and p.author() == "izzydoingit", "plugin initialises")
cb["ui"](None)
check(("question" in [c_[0] for c_ in calls]) and ("name?", __import__("time").strftime("Preset from game folder %Y-%m-%d")) in calls
      and not (game / "enbseries.ini").exists() and (mods / "NAT ENB Preset - Game Root" / "Root" / "enbseries.ini").exists(), "startup: asked, named, preset moved on yes")
check(("tick", "NAT ENB Preset - Game Root") in calls, "new preset mod ticked in this profile")
rbd = pdata / "RootBuilder" / C.path_safe(str(game).replace("\\", "/")) / "1_0"
check(not (rbd / "GameData.json").exists(), "files Root Builder counted as game files -> its snapshot set aside")
put(ow / "Root" / "enbcache" / "y.sc", "c")
ML.ticked = ["NAT ENB Preset - Game Root"]   # the profile ticks the preset mod it just made (the stub's setActive keeps no state)
cb["run"]("SkyrimSE.exe", 0)
ML.ticked = []
check((mods / "Root Changes - Profile A" / "Root" / "enbcache" / "y.sc").exists() and ("tick", "Root Changes - Profile A") in calls, "after a run: change moved + profile mod ticked")
# a NEW preset dropped in by hand later (Root Builder never saw it): offered too; "no" is remembered for that set
put(rbd / "GameData.json", json.dumps({"skyrimse.exe": {}}))
put(game / "reshade.ini", "new preset")
MB.answer = 0
n0 = len(calls); cb["prof"]("a", "b")
check([c_[0] for c_ in calls[n0:]] == ["question"] and (game / "reshade.ini").exists(), "hand-placed new preset offered; no = nothing moved")
n0 = len(calls); cb["prof"]("a", "b")
check(len(calls) == n0, "the same set is not asked again after no")
put(game / "enbseries.ini", "another")
MB.answer = 1; ID.reply = ("My ReShade Preset", True)
n0 = len(calls); cb["prof"]("a", "b")
check((mods / "My ReShade Preset" / "Root" / "reshade.ini").exists() and not (game / "reshade.ini").exists() and not (game / "enbseries.ini").exists(),
      "the set changed -> asked again; yes + a name -> moved into that mod")
check((rbd / "GameData.json").exists(), "files Root Builder never knew -> its snapshot left alone")
ID.reply = ("", False); put(game / "enbseries.ini", "x"); n0 = len(calls); cb["prof"]("a", "b")
check((game / "enbseries.ini").exists(), "cancel on the name box -> nothing moved")
# ---- 1.1.1 glue: Root Builder cleared (no BuildData.json) but the game still runs and its DLLs stayed
shutil.rmtree(game / "enbseries", ignore_errors=True)
for n_ in ("enbseries.ini", "reshade.ini"):
    if (game / n_).exists(): (game / n_).unlink()
state = json.loads((pdata / "RootBuilderProfiles" / "state.json").read_text()); state.pop("declined", None)
(pdata / "RootBuilderProfiles" / "state.json").write_text(json.dumps(state))
put(game / "d3d11.dll", "enb binary"); put(game / "d3dcompiler_46e.dll", "compiler")
put(game / "enbseries" / "KiLoaderSatelliteENB.dllplugin", "sat")
put(mods / "ENB Binaries 0.505" / "Root" / "d3d11.dll", "enb binary")
put(mods / "ENB Binaries 0.505" / "Root" / "d3dcompiler_46e.dll", "compiler")
put(mods / "KiLoader" / "Root" / "enbseries" / "KiLoaderSatelliteENB.dllplugin", "sat")
ML.ticked = ["ENB Binaries 0.505", "KiLoader"]
MB.answer = 1
RUNNING[0] = True
n0 = len(calls); cb["run"]("SkyrimSE.exe", 0)
check(len(calls) == n0 and (game / "d3d11.dll").exists(), "after a run with the game still alive: no question, nothing moved")
RUNNING[0] = False
n0 = len(calls); cb["run"]("SkyrimSE.exe", 0)
check(len(calls) == n0 and (game / "d3d11.dll").exists(), "game closed, the DLLs left behind belong to ticked mods: no question")
n0 = len(calls); cb["prof"]("a", "b")
check(len(calls) == n0, "profile change with the same files: no question")
ML.ticked = []
MB.answer = 0
n0 = len(calls); cb["prof"]("a", "b")
check([c_[0] for c_ in calls[n0:]] == ["question"], "untick those mods -> the files really are unowned -> asked")
# MO2's list unreadable -> the profile's modlist.txt decides what is ticked
put(W / "profile" / "modlist.txt", "# header\n-Unticked Mod\n+KiLoader\n+ENB Binaries 0.505\n")
Org.profilePath = lambda self: str(W / "profile")
ML.allModsByProfilePriority = lambda self, profile=None: (_ for _ in ()).throw(RuntimeError("no list"))
state = json.loads((pdata / "RootBuilderProfiles" / "state.json").read_text()); state.pop("declined", None)
(pdata / "RootBuilderProfiles" / "state.json").write_text(json.dumps(state))
n0 = len(calls); cb["prof"]("a", "b")
check(len(calls) == n0, "MO2's list unreadable -> modlist.txt's ticks used: no question")
# ---- 1.3.0 glue: leftover copies of an unticked mod's Root files are offered as LEFTOVERS to remove, never as a preset
ML.allModsByProfilePriority = lambda self, profile=None: ["Unticked Mod"] + ML.ticked
ML.ticked = []
shutil.rmtree(game / "enbseries", ignore_errors=True)
for n_ in ("d3d11.dll", "d3dcompiler_46e.dll"):
    if (game / n_).exists(): (game / n_).unlink()
put(game / "d3d11.dll", "dxvk d3d11"); put(game / "dxgi.dll", "dxvk dxgi")
put(mods / "TEST DXVK" / "Root" / "d3d11.dll", "dxvk d3d11"); put(mods / "TEST DXVK" / "Root" / "dxgi.dll", "dxvk dxgi")
state = json.loads((pdata / "RootBuilderProfiles" / "state.json").read_text()); state.pop("declined", None)
(pdata / "RootBuilderProfiles" / "state.json").write_text(json.dumps(state))
MB.answer = 1
n0 = len(calls); cb["prof"]("a", "b")
asked = calls[n0:]
check(asked and asked[0][0] == "question" and "exact copies" in asked[0][1] and not any(c_[0] == "name?" for c_ in asked)
      and not any(c_[0] == "tick" for c_ in asked), f"DXVK leftovers: asked to REMOVE them, no preset name asked, nothing ticked {asked}")
check(not (game / "d3d11.dll").exists() and not (game / "dxgi.dll").exists() and (mods / "TEST DXVK" / "Root" / "dxgi.dll").exists()
      and not any(d.name.startswith("Preset from game folder") for d in mods.iterdir()), "yes -> the game copies gone, the test mod keeps its own, no preset mod made")
print(calls)
try:
    meta = (p.requirements(), p.settings(), p.version(), p.icon(), p.description(), p.displayName(), p.tooltip(), p.isActive())
    check(meta[0] == [("needs", ["RootBuilder"])] and meta[2] == (1, 3, 1), "every method MO2 calls while loading a plugin runs (requirements, settings, version, icon ...)")
except Exception as e:
    check(False, f"a plugin method MO2 calls at load raised {e!r}")
# ---- 1.3.1: the fixes of the public release's review ------------------------------------------------------------
# a move between drives (MO2's mods folder on another drive than overwrite): copied, proven equal, the source removed
real_replace = C.os.replace
put(W / "xdrive" / "src.bin", "cross drive")
def no_cross(a, b):
    e = OSError(18, "not the same device"); e.winerror = 17
    raise e
C.os.replace = no_cross
try:
    C.move_file(W / "xdrive" / "src.bin", W / "xdrive" / "dest.bin")
    check((W / "xdrive" / "dest.bin").read_text() == "cross drive" and not (W / "xdrive" / "src.bin").exists(),
          "a move between drives copies, proves the copy and removes the source")
finally:
    C.os.replace = real_replace
check(C.path_safe("D:/Steam Library/Skyrim") == "DSteam_LibrarySkyrim" and C.path_safe('a<b>c:d|e*f\\g/h?i"j.k') == "abcdefghij_k",
      "path_safe: spaces and dots to underscores, unsafe characters dropped")
# both questions answered no: neither is asked again (each keeps its own remembered answer)
ML.allModsByProfilePriority = lambda self, profile=None: ["Unticked Mod"] + ML.ticked
ML.ticked = []
put(game / "d3d11.dll", "dxvk d3d11")                    # a copy of TEST DXVK's Root file
put(game / "reshade.ini", "a hand-placed preset")
state = json.loads((pdata / "RootBuilderProfiles" / "state.json").read_text())
state.pop("declined", None); state.pop("declined_copies", None)
(pdata / "RootBuilderProfiles" / "state.json").write_text(json.dumps(state))
MB.answer = 0
n0 = len(calls); cb["prof"]("a", "b")
first = [c_[0] for c_ in calls[n0:]]
n0 = len(calls); cb["prof"]("a", "b")
check(first == ["question", "question"] and len(calls) == n0, f"no to both questions -> neither is asked again {first}")
# the Tools menu entry asks again, even with the automatic check switched off
settings["checkgame"] = False
n0 = len(calls); p.display()
check([c_[0] for c_ in calls[n0:]][:1] == ["question"], "Tools menu entry asks even with the automatic check off")
settings["checkgame"] = True
# moving a preset into an EXISTING mod that is not ticked: it is ticked in this profile
(game / "d3d11.dll").unlink()
put(mods / "Old Preset Mod" / "meta.ini", "[General]")
state = json.loads((pdata / "RootBuilderProfiles" / "state.json").read_text())
state.pop("declined", None); state.pop("declined_copies", None)
(pdata / "RootBuilderProfiles" / "state.json").write_text(json.dumps(state))
MB.answer = 1; ID.reply = ("Old Preset Mod", True)
n0 = len(calls); cb["prof"]("a", "b")
check((mods / "Old Preset Mod" / "Root" / "reshade.ini").exists() and ("tick", "Old Preset Mod") in calls[n0:],
      "a preset moved into an existing unticked mod -> that mod is ticked in this profile")
# a profile changed between the game's close and the move: the files go to the profile that ran, nothing is ticked here
put(ow / "Root" / "enbcache" / "z.sc", "z")
p._run_profile = "Profile Z"
n0 = len(calls); p._guard(p._after_run)
check((mods / "Root Changes - Profile Z" / "Root" / "enbcache" / "z.sc").exists() and ("tick", "Root Changes - Profile Z") not in calls[n0:],
      "files go to the profile that ran, and its mod is not ticked in the current one")
print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
