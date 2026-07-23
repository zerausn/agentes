"""
Debug: ejecuta 1 ciclo completo con screenshots en cada paso y dumpsys
"""
import subprocess, pathlib, time, re

ADB = ["adb", "-s", "127.0.0.1:5555"]
SCR_DIR = pathlib.Path("/sdcard/Antigravity/.state")

def run(cmd, timeout=30):
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)

def adb_shell(cmd, timeout=30):
    full_cmd = ADB + ["shell", "exec"] + (cmd if isinstance(cmd, list) else [cmd])
    return run(full_cmd, timeout=timeout)

def screenshot(step):
    path = f"/sdcard/Antigravity/.state/debug_step_{step}.png"
    adb_shell(["screencap", "-p", path])
    print(f"[SCREENSHOT] {step} -> {path}")

def dump_ui(step):
    path = f"/sdcard/Antigravity/.state/debug_ui_{step}.xml"
    r = adb_shell(["uiautomator", "dump", path])
    print(f"[UI DUMP {step}] rc={r.returncode} {r.stdout[:100]} {r.stderr[:100]}")

def current_focus():
    r = adb_shell(["dumpsys", "window"])
    m = re.search(r"mCurrentFocus=.*? ([A-Za-z0-9_.]+)/", r.stdout + r.stderr)
    return m.group(1) if m else "UNKNOWN"

# 1. Wake + open TikTok via share intent
print("=== WAKE ===")
adb_shell(["input", "keyevent", "KEYCODE_WAKEUP"])
time.sleep(1)
adb_shell(["input", "swipe", "500", "1700", "500", "500", "350"])
time.sleep(1)
screenshot("00_wake")

# 2. Force stop + share
print("=== RESET ===")
adb_shell(["am", "force-stop", "com.zhiliaoapp.musically"])
time.sleep(2)

print("=== SEND SHARE INTENT ===")
share_cmd = [
    "am", "start",
    "-a", "android.intent.action.SEND",
    "-t", "video/mp4",
    "--eu", "android.intent.extra.STREAM", "content://media/external/video/media/18459",
    "-f", "0x10000000",
]
r = adb_shell(share_cmd)
print(f"Share intent: rc={r.returncode} {r.stdout[:200]} {r.stderr[:200]}")
time.sleep(20)
screenshot("01_after_share")
dump_ui("01_after_share")
print(f"FOCUS: {current_focus()}")

# 3. Tap caption field
print("=== TAP CAPTION ===")
adb_shell(["input", "tap", "178", "152"])
time.sleep(2)
screenshot("02_tap_caption")
dump_ui("02_tap_caption")
print(f"FOCUS: {current_focus()}")

# 4. Type caption
print("=== TYPE CAPTION ===")
caption = "test_caption_debug%s#PW%s#test"
adb_shell(["input", "text", caption])
time.sleep(2)
screenshot("03_after_text")
dump_ui("03_after_text")
print(f"FOCUS: {current_focus()}")

# 5. Try to close keyboard
print("=== CLOSE KEYBOARD ===")
for i in range(5):
    r = adb_shell(["dumpsys", "input_method"])
    if "mInputShown=true" not in r.stdout:
        print(f"Keyboard closed at attempt {i+1}")
        break
    adb_shell(["input", "keyevent", "KEYCODE_BACK"])
    time.sleep(1)
    adb_shell(["input", "tap", "360", "400"])
    time.sleep(1)
else:
    print("KEYBOARD STILL OPEN after 5 attempts")
screenshot("04_after_close_kb")
dump_ui("04_after_close_kb")
print(f"FOCUS: {current_focus()}")

# 6. Tap Publicar
print("=== TAP PUBLICAR ===")
adb_shell(["input", "tap", "608", "80"])
time.sleep(2)
screenshot("05_after_publish_tap")
dump_ui("05_after_publish_tap")
print(f"FOCUS: {current_focus()}")

# 7. Wait for upload
print("=== WAIT FOR UPLOAD ===")
for i in range(4):
    time.sleep(15)
    print(f"Check {i+1}: FOCUS={current_focus()}")
    r = adb_shell(["dumpsys", "input_method"])
    kb = "KEYBOARD_VISIBLE" if "mInputShown=true" in r.stdout else "KB_HIDDEN"
    print(f"  {kb}")
    dump_ui(f"06_check_{i+1}")

screenshot("06_final")
print("=== DONE ===")
