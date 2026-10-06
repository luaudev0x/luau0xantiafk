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
        "game_id": "",
        "webhook_url": "",
        "webhook_interval": 1,
        "startup_delay": 15,
        "rejoin_delay": 10,
        "ram_threshold": 85,
        "check_interval": 15
    }

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print("  ✅ Config saved!")
    time.sleep(1)

def detect_roblox_packages():
    print("  🔍 Scanning for Roblox packages...")
    result = subprocess.run(["pm", "list", "packages"], capture_output=True, text=True)
    packages = []
    keywords = ["roblox", "rblx"]
    for line in result.stdout.splitlines():
        pkg = line.replace("package:", "").strip()
        if any(k in pkg.lower() for k in keywords):
            packages.append(pkg)
    return packages

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
    return round(total/1024), round(used/1024), percent

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

def draw_bar(percent, width=20):
    filled = int(width * percent / 100)
    return "█" * filled + "░" * (width - filled)

def send_webhook(webhook_url, packages_status, ram_total, ram_used, ram_percent, cpu_percent, restarts):
    if not webhook_url:
        return
    try:
        fields = []
        for pkg, info in packages_status.items():
            fields.append({
                "name": f"📦 {pkg}",
                "value": f"Game ID: `{info['game_id']}`\nStatus: {'🟢 ONLINE' if info['running'] else '🔴 OFFLINE'}\nRestarts: `{info['restarts']}`",
                "inline": True
            })
        embed = {
            "title": "🎮 Roblox Auto Rejoiner Status",
            "color": 5763719,
            "fields": fields + [
                {"name": "💾 RAM Usage", "value": f"`{ram_percent}%` — {ram_used}MB / {ram_total}MB", "inline": True},
                {"name": "⚡ CPU Usage", "value": f"`{cpu_percent}%`", "inline": True},
                {"name": "🔄 Total Restarts", "value": f"`{restarts}`", "inline": True}
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
        print("   [2] Manage Packages & Game IDs")
        print("   [3] Set Webhook URL")
        print("   [4] Set Webhook Interval")
        print("   [5] Set Startup Delay")
        print("   [6] Set Rejoin Delay")
        print("   [7] Set RAM Threshold")
        print("   [8] Set Check Interval")
        print("   [9] Back")
        print()
        print("=" * 40)
        choice = input("   Select: ").strip()

        if choice == "1":
            clear()
            print("=" * 40)
            print("   🔍 DETECTING PACKAGES")
            print("=" * 40)
            found = detect_roblox_packages()
            if not found:
                print("  ❌ No Roblox packages found!")
                time.sleep(2)
                continue
            print(f"\n  Found {len(found)} package(s):\n")
            for i, pkg in enumerate(found):
                print(f"  [{i+1}] {pkg}")
            print()
            save = input("  Save all detected packages? (y/n): ").strip().lower()
            if save == "y":
                existing = [p["package"] for p in config["packages"]]
                for pkg in found:
                    if pkg not in existing:
                        game_id = input(f"  Game ID for {pkg}: ").strip()
                        config["packages"].append({
                            "package": pkg,
                            "game_id": game_id
                        })
                save_config(config)

        elif choice == "2":
            while True:
                clear()
                print("=" * 40)
                print("   📦 MANAGE PACKAGES")
                print("=" * 40)
                print()
                if not config["packages"]:
                    print("  No packages saved yet.")
                else:
                    for i, p in enumerate(config["packages"]):
                        print(f"  [{i+1}] {p['package']}")
                        print(f"       Game ID: {p['game_id'] or 'Not set'}")
                        print()
                print("  [A] Add Package Manually")
                print("  [D] Delete Package")
                print("  [E] Edit Game ID")
                print("  [B] Back")
                print()
                print("=" * 40)
                c = input("   Select: ").strip().lower()
                if c == "a":
                    pkg = input("  Package name: ").strip()
                    game_id = input("  Game ID: ").strip()
                    config["packages"].append({"package": pkg, "game_id": game_id})
                    save_config(config)
                elif c == "d":
                    idx = input("  Enter number to delete: ").strip()
                    try:
                        config["packages"].pop(int(idx)-1)
                        save_config(config)
                    except:
                        print("  Invalid!")
                        time.sleep(1)
                elif c == "e":
                    idx = input("  Enter number to edit: ").strip()
                    try:
                        new_id = input("  New Game ID: ").strip()
                        config["packages"][int(idx)-1]["game_id"] = new_id
                        save_config(config)
                    except:
                        print("  Invalid!")
                        time.sleep(1)
                elif c == "b":
                    break

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

        elif choice == "4":
            clear()
            print("=" * 40)
            print("   ⏱️  WEBHOOK INTERVAL")
            print("=" * 40)
            print(f"\n  Current: {config['webhook_interval']} min(s)\n")
            val = input("  Enter interval in minutes (e.g. 1, 2, 5): ").strip()
            try:
                config["webhook_interval"] = int(val)
                save_config(config)
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
            except:
                print("  Invalid!")
                time.sleep(1)

        elif choice == "6":
            clear()
            print("=" * 40)
            print("   ⏳ REJOIN DELAY")
            print("=" * 40)
            print(f"\n  Current: {config['rejoin_delay']}s\n")
            val = input("  Seconds to wait before rejoining: ").strip()
            try:
                config["rejoin_delay"] = int(val)
                save_config(config)
            except:
                print("  Invalid!")
                time.sleep(1)

        elif choice == "7":
            clear()
            print("=" * 40)
            print("   💾 RAM THRESHOLD")
            print("=" * 40)
            print(f"\n  Current: {config['ram_threshold']}%\n")
            val = input("  RAM % to trigger restart (e.g. 85): ").strip()
            try:
                config["ram_threshold"] = int(val)
                save_config(config)
            except:
                print("  Invalid!")
                time.sleep(1)

        elif choice == "8":
            clear()
            print("=" * 40)
            print("   🔄 CHECK INTERVAL")
            print("=" * 40)
            print(f"\n  Current: {config['check_interval']}s\n")
            val = input("  Seconds between each check: ").strip()
            try:
                config["check_interval"] = int(val)
                save_config(config)
            except:
                print("  Invalid!")
                time.sleep(1)

        elif choice == "9":
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

    total_restarts = 0
    last_webhook = 0

    clear()
    print("=" * 40)
    print("   🎮 ROBLOX AUTO REJOINER - RUNNING")
    print("=" * 40)
    print()
    print(f"  Launching {len(config['packages'])} instance(s) sequentially...")
    print()

    for p in config["packages"]:
        print(f"  🚀 Launching {p['package']}...")
        launch_roblox(p["package"], p["game_id"])
        print(f"  ⏳ Waiting {config['startup_delay']}s for it to load...")
        time.sleep(config["startup_delay"])

    print("  ✅ All instances launched!")
    time.sleep(3)

    while True:
        ram_total, ram_used, ram_percent = get_ram()
        cpu_percent = get_cpu()

        for pkg, info in packages_status.items():
            info["running"] = is_running(pkg)

        clear()
        print("=" * 40)
        print("   🎮 ROBLOX AUTO REJOINER - RUNNING")
        print("=" * 40)
        print()

        for pkg, info in packages_status.items():
            status = "ONLINE  ✅" if info["running"] else "OFFLINE ❌"
            print(f"  📦 {pkg}")
            print(f"     Status: {status} | Game: {info['game_id']} | Restarts: {info['restarts']}")
            print()

        print(f"  💾 RAM:  [{draw_bar(ram_percent)}] {ram_percent}%")
        print(f"          {ram_used}MB used / {ram_total}MB total")
        print()
        print(f"  ⚡ CPU:  [{draw_bar(cpu_percent)}] {cpu_percent}%")
        print()
        print(f"  🔄 Total Restarts: {total_restarts}")
        print()
        print("=" * 40)
        print("  Press Ctrl+C to stop")
        print("=" * 40)

        now = time.time()
        if config["webhook_url"] and (now - last_webhook) >= config["webhook_interval"] * 60:
            send_webhook(config["webhook_url"], packages_status, ram_total, ram_used, ram_percent, cpu_percent, total_restarts)
            last_webhook = now

        for pkg, info in packages_status.items():
            if not info["running"] or ram_percent >= config["ram_threshold"]:
                print()
                print(f"  ⚠️  {pkg} is down! Restarting in {config['rejoin_delay']}s...")
                time.sleep(config["rejoin_delay"])
                kill_app(pkg)
                time.sleep(3)
                launch_roblox(pkg, info["game_id"])
                info["restarts"] += 1
                total_restarts += 1
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
