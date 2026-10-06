import subprocess
import time
import os
import json
import urllib.request

CONFIG_FILE = os.path.expanduser("~/rejoin_config.json")

def clear():
    os.system("clear")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {
        "packages": [],
        "webhook_url": "",
        "webhook_interval": 1,
        "startup_delay": 15,
        "rejoin_delay": 10,
        "check_interval": 15
    }

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def is_valid_package(pkg):
    import re
    return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9._]+$', pkg)) and " " not in pkg and len(pkg) > 3

def detect_roblox_packages():
    found = []

    try:
        result = subprocess.run(
            ["pm", "query-activities", "-a", "android.intent.action.VIEW", "-d", "roblox://"],
            capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("packageName="):
                pkg = line.replace("packageName=", "").strip()
                if is_valid_package(pkg) and pkg not in found:
                    found.append(pkg)
            elif line.startswith("package:"):
                pkg = line.replace("package:", "").strip()
                if is_valid_package(pkg) and pkg not in found:
                    found.append(pkg)
    except:
        pass

    keywords = ["roblox", "rblx", "roblx", "rbx"]
    try:
        result = subprocess.run(["pm", "list", "packages"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            pkg = line.replace("package:", "").strip()
            if is_valid_package(pkg) and any(k in pkg.lower() for k in keywords) and pkg not in found:
                found.append(pkg)
    except:
        pass

    common = [
        "com.roblox.client",
        "com.roblox.client2",
        "com.roblox.client3",
        "com.roblx",
        "com.roblx.client",
        "com.roblox",
        "com.roblox2",
        "com.roblox3",
    ]
    for pkg in common:
        try:
            result = subprocess.run(["pm", "list", "packages", pkg], capture_output=True, text=True)
            if f"package:{pkg}" in result.stdout and pkg not in found:
                found.append(pkg)
        except:
            pass

    return list(set(found))

def get_ram():
    result = subprocess.run(["cat", "/proc/meminfo"], capture_output=True, text=True)
    lines = {}
    for l in result.stdout.splitlines():
        if ":" in l:
            parts = l.split()
            lines[parts[0].rstrip(":")] = int(parts[1])
    total = lines.get("MemTotal", 1)
    available = lines.get("MemAvailable", 1)
    used = total - available
    percent = round((used / total) * 100, 1)
    return round(total/1024), round(used/1024), round(available/1024), percent

def get_cpu():
    try:
        result = subprocess.run(["top", "-bn1"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "cpu" in line.lower() and "%" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if "id" in p or "idle" in p:
                        idle = float(parts[i-1].replace("%","").replace(",",""))
                        return round(100 - idle, 1)
        return 0.0
    except:
        return 0.0

def get_device_model():
    try:
        result = subprocess.run(["getprop", "ro.product.model"], capture_output=True, text=True)
        return result.stdout.strip() or "Unknown"
    except:
        return "Unknown"

def is_running(package):
    result = subprocess.run(["pgrep", "-f", package], capture_output=True, text=True)
    return result.returncode == 0

def kill_app(package):
    subprocess.run(["am", "force-stop", package], capture_output=True)
    subprocess.run(["am", "kill-all"], capture_output=True)
    time.sleep(2)

def launch_roblox(package, game_id):
    deeplink = f"roblox://experiences/start?placeId={game_id}"
    subprocess.run([
        "am", "start",
        "-a", "android.intent.action.VIEW",
        "-d", deeplink
    ], capture_output=True)

def format_uptime(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"

def draw_bar(percent, width=20):
    filled = int(width * percent / 100)
    return "█" * filled + "░" * (width - filled)

def send_webhook(webhook_url, packages_status, ram_total, ram_used, ram_free, ram_percent, cpu_percent, device_model, start_times):
    if not webhook_url:
        return
    try:
        now = time.time()
        total = len(packages_status)
        online = sum(1 for i in packages_status.values() if i["running"])
        offline = total - online

        instance_lines = []
        for pkg, info in packages_status.items():
            dot = "🟢" if info["running"] else "🔴"
            uptime = format_uptime(now - start_times.get(pkg, now))
            line = (
                f"{dot} **{pkg}**\n"
                f"└ ⏱️ {uptime} | 🎮 `{info['game_id']}` | 🔄 Restarts: `{info['restarts']}`"
            )
            instance_lines.append(line)

        description = "\n".join(instance_lines)

        embed = {
            "title": "📊 Roblox Auto Rejoiner Status",
            "color": 3066993 if online == total else 15158332,
            "fields": [
                {
                    "name": "📱 Device Information",
                    "value": (
                        f"🖥️ | Device: `{device_model}`\n"
                        f"⚙️ | CPU: `{cpu_percent}%`\n"
                        f"💾 | RAM: `{ram_free}MB free` ({ram_used}MB used / {ram_total}MB total)"
                    ),
                    "inline": False
                },
                {
                    "name": "🤖 Instance Status",
                    "value": (
                        f"🤖 | Total: `{total}`\n"
                        f"🟢 | Online: `{online}`\n"
                        f"🔴 | Offline: `{offline}`"
                    ),
                    "inline": False
                },
                {
                    "name": "📋 Application Details",
                    "value": description or "No instances",
                    "inline": False
                }
            ],
            "footer": {"text": "Roblox Auto Rejoiner • Termux"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        data = json.dumps({"embeds": [embed]}).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
    except:
        pass

def setup_menu():
    config = load_config()
    while True:
        clear()
        print("=" * 40)
        print("   ⚙️  SETUP")
        print("=" * 40)
        print()
        print("   [1] Auto Detect Roblox Packages")
        print("   [2] Set Game ID")
        print("   [3] Set Webhook URL")
        print("   [4] Set Webhook Interval")
        print("   [5] Set Startup Delay")
        print("   [6] Set Rejoin Delay")
        print("   [7] Set Check Interval")
        print("   [8] Back")
        print()
        if config["packages"]:
            print("  📦 Saved packages:")
            for p in config["packages"]:
                print(f"     • {p['package']} | Game: {p['game_id'] or 'Not set'}")
        print()
        print("=" * 40)
        choice = input("   Select: ").strip()

        if choice == "1":
            clear()
            print("=" * 40)
            print("   🔍 DETECTING PACKAGES")
            print("=" * 40)
            print()
            print("  Scanning... please wait...")
            found = detect_roblox_packages()
            if not found:
                print()
                print("  ❌ No Roblox packages found!")
                print("  Use option [2] to set game ID manually.")
                input("  Press any key to go back...")
                continue
            print(f"\n  Found {len(found)} package(s):\n")
            for i, pkg in enumerate(found):
                already = any(p["package"] == pkg for p in config["packages"])
                tag = " ✅ saved" if already else ""
                print(f"  [{i+1}] {pkg}{tag}")
            print()
            sel = input("  Type number to save, 0 to cancel: ").strip()
            if sel == "0":
                continue
            try:
                idx = int(sel) - 1
                pkg = found[idx]
                if any(p["package"] == pkg for p in config["packages"]):
                    print("  ⚠️  Already saved!")
                    input("  Press any key to go back...")
                    continue
                game_id = input(f"  Enter Game ID for {pkg}: ").strip()
                config["packages"].append({"package": pkg, "game_id": game_id})
                save_config(config)
                print()
                print("  ✅ Saved!")
                print(f"     📦 {pkg}")
                print(f"     🎮 Game ID: {game_id}")
                print()
                input("  Press any key to go back...")
            except:
                print("  Invalid!")
                input("  Press any key to go back...")

        elif choice == "2":
            clear()
            print("=" * 40)
            print("   🎮 SET GAME ID")
            print("=" * 40)
            print()
            if not config["packages"]:
                game_id = input("  Enter Game ID: ").strip()
                config["packages"].append({"package": "com.roblox.client", "game_id": game_id})
                save_config(config)
                print("  ✅ Saved!")
                time.sleep(1)
            else:
                for i, p in enumerate(config["packages"]):
                    print(f"  [{i+1}] {p['package']} | Game: {p['game_id'] or 'Not set'}")
                print()
                sel = input("  Select package number: ").strip()
                try:
                    idx = int(sel) - 1
                    new_id = input("  New Game ID: ").strip()
                    config["packages"][idx]["game_id"] = new_id
                    save_config(config)
                    print("  ✅ Saved!")
                    time.sleep(1)
                except:
                    print("  Invalid!")
                    time.sleep(1)

        elif choice == "3":
            clear()
            print("=" * 40)
            print("   🔗 WEBHOOK URL")
            print("=" * 40)
            print(f"\n  Current: {config['webhook_url'] or 'Not set'}\n")
            url = input("  Paste Discord Webhook URL: ").strip()
            if url:
                config["webhook_url"] = url
                save_config(config)
                print("  ✅ Saved!")
                time.sleep(1)

        elif choice == "4":
            clear()
            print("=" * 40)
            print("   ⏱️  WEBHOOK INTERVAL")
            print("=" * 40)
            print(f"\n  Current: {config['webhook_interval']} min(s)\n")
            val = input("  Minutes (e.g. 1, 2, 5): ").strip()
            try:
                config["webhook_interval"] = int(val)
                save_config(config)
                print("  ✅ Saved!")
                time.sleep(1)
            except:
                print("  Invalid!")
                time.sleep(1)

        elif choice == "5":
            clear()
            print("=" * 40)
            print("   ⏳ STARTUP DELAY")
            print("=" * 40)
            print(f"\n  Current: {config['startup_delay']}s\n")
            val = input("  Seconds to wait after launch: ").strip()
            try:
                config["startup_delay"] = int(val)
                save_config(config)
                print("  ✅ Saved!")
                time.sleep(1)
            except:
                print("  Invalid!")
                time.sleep(1)

        elif choice == "6":
            clear()
            print("=" * 40)
            print("   ⏳ REJOIN DELAY")
            print("=" * 40)
            print(f"\n  Current: {config['rejoin_delay']}s\n")
            val = input("  Seconds before rejoining: ").strip()
            try:
                config["rejoin_delay"] = int(val)
                save_config(config)
                print("  ✅ Saved!")
                time.sleep(1)
            except:
                print("  Invalid!")
                time.sleep(1)

        elif choice == "7":
            clear()
            print("=" * 40)
            print("   🔄 CHECK INTERVAL")
            print("=" * 40)
            print(f"\n  Current: {config['check_interval']}s\n")
            val = input("  Seconds between checks: ").strip()
            try:
                config["check_interval"] = int(val)
                save_config(config)
                print("  ✅ Saved!")
                time.sleep(1)
            except:
                print("  Invalid!")
                time.sleep(1)

        elif choice == "8":
            break

def monitor():
    config = load_config()
    if not config["packages"]:
        clear()
        print("=" * 40)
        print("  ❌ No packages configured!")
        print("  Go to Setup first.")
        print("=" * 40)
        time.sleep(3)
        return

    packages_status = {
        p["package"]: {"game_id": p["game_id"], "running": False, "restarts": 0}
        for p in config["packages"]
    }

    start_times = {p["package"]: time.time() for p in config["packages"]}
    total_restarts = 0
    last_webhook = 0
    device_model = get_device_model()

    clear()
    print("=" * 40)
    print("   🎮 ROBLOX AUTO REJOINER - RUNNING")
    print("=" * 40)
    print()
    print(f"  Launching {len(config['packages'])} instance(s)...")
    print()

    for p in config["packages"]:
        print(f"  🚀 Launching {p['package']}...")
        launch_roblox(p["package"], p["game_id"])
        print(f"  ⏳ Waiting {config['startup_delay']}s...")
        time.sleep(config["startup_delay"])

    print("  ✅ All launched!")
    time.sleep(2)

    while True:
        ram_total, ram_used, ram_free, ram_percent = get_ram()
        cpu_percent = get_cpu()

        for pkg, info in packages_status.items():
            info["running"] = is_running(pkg)

        clear()
        print("=" * 40)
        print("   🎮 ROBLOX AUTO REJOINER - RUNNING")
        print("=" * 40)
        print()
        print(f"  🖥️  Device: {device_model}")
        print(f"  ⚙️  CPU:    {cpu_percent}%")
        print(f"  💾 RAM:    {ram_free}MB free ({ram_used}MB used / {ram_total}MB total)")
        print()

        total = len(packages_status)
        online = sum(1 for i in packages_status.values() if i["running"])
        offline = total - online
        print(f"  🤖 Total: {total}  🟢 Online: {online}  🔴 Offline: {offline}")
        print()

        now = time.time()
        for pkg, info in packages_status.items():
            dot = "🟢" if info["running"] else "🔴"
            uptime = format_uptime(now - start_times.get(pkg, now))
            print(f"  {dot} {pkg}")
            print(f"     ⏱️ {uptime} | 🎮 {info['game_id']} | 🔄 {info['restarts']}")
            print()

        print("=" * 40)
        print("  Press Ctrl+C to stop")
        print("=" * 40)

        if config["webhook_url"] and (now - last_webhook) >= config["webhook_interval"] * 60:
            send_webhook(config["webhook_url"], packages_status, ram_total, ram_used, ram_free, ram_percent, cpu_percent, device_model, start_times)
            last_webhook = now

        for pkg, info in packages_status.items():
            if not info["running"] or ram_percent >= 98:
                print()
                print(f"  ⚠️  {pkg} offline! Restarting in {config['rejoin_delay']}s...")
                time.sleep(config["rejoin_delay"])
                kill_app(pkg)
                time.sleep(3)
                launch_roblox(pkg, info["game_id"])
                info["restarts"] += 1
                total_restarts += 1
                start_times[pkg] = time.time()
                print(f"  ⏳ Waiting {config['startup_delay']}s to load...")
                time.sleep(config["startup_delay"])

        time.sleep(config["check_interval"])

def menu():
    while True:
        clear()
        print("=" * 40)
        print("   🎮 ROBLOX AUTO REJOINER")
        print("=" * 40)
        print()
        config = load_config()
        pkg_count = len(config["packages"])
        webhook = "✅ Set" if config["webhook_url"] else "❌ Not set"
        print(f"  📦 Packages: {pkg_count}")
        print(f"  🔗 Webhook:  {webhook}")
        print()
        print("   [1] Start Auto Rejoin")
        print("   [2] Setup")
        print("   [3] Exit")
        print()
        print("=" * 40)
        choice = input("   Select: ").strip()

        if choice == "1":
            try:
                monitor()
            except KeyboardInterrupt:
                clear()
                print("=" * 40)
                print("   ⛔ Stopped.")
                print("=" * 40)
                time.sleep(1)
        elif choice == "2":
            setup_menu()
        elif choice == "3":
            clear()
            print("   Bye!")
            break
        else:
            print("   Invalid, try again...")
            time.sleep(1)

if __name__ == "__main__":
    menu()
