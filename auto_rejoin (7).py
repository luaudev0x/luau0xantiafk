import subprocess
import time
import os
import json
import urllib.request
import urllib.parse
import base64

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

def run_cmd(cmd):
    try:
        result = subprocess.run(["su", "-c", cmd], capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except:
        pass
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout
    except:
        return ""

def detect_roblox_packages():
    found = []
    try:
        out = run_cmd("pm query-activities -a android.intent.action.VIEW -d roblox://")
        for line in out.splitlines():
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

    keywords = ["roblox", "rblx", "roblx", "rbx", "noka", "delta", "arceus", "fluxus", "executor"]
    try:
        out = run_cmd("pm list packages")
        for line in out.splitlines():
            pkg = line.replace("package:", "").strip()
            if is_valid_package(pkg) and any(k in pkg.lower() for k in keywords) and pkg not in found:
                found.append(pkg)
    except:
        pass

    common = [
        "com.roblox.client","com.roblox.client2","com.roblox.client3",
        "com.roblox","com.roblox2","com.roblox3","com.roblx","com.roblx.client",
        "com.delta.executor","com.delta.executor2","com.delta.executorlite",
        "com.delta.lite","com.delta.roblox","com.noka.delta","com.noka.executor",
        *[f"premium.noka{chr(i)}" for i in range(ord('A'), ord('Z')+1)],
        *[f"premium.noka{chr(i)}" for i in range(ord('a'), ord('z')+1)],
        "premium.noka","premium.NOKA",
        *[f"free.noka{chr(i)}" for i in range(ord('A'), ord('Z')+1)],
        *[f"free.noka{chr(i)}" for i in range(ord('a'), ord('z')+1)],
        "free.noka","free.NOKA",
        "com.arceus.x","com.arceusx","com.arceus.executor","com.arceus.lite",
        "com.arceus.neo","com.arceus.v3","com.arceus.x2","com.arceus.roblox",
        "com.fluxus","com.fluxus.executor","com.fluxteam.roblox","com.flux.executor",
        "com.hydrogen","com.hydrogen.executor","com.h2executor",
        "com.trigon.evo","com.trigon.executor","com.trigonevo",
        "com.codex.executor","com.codex.roblox","com.codex",
        "com.cerberus.executor","com.cerberus.roblox",
        "com.krnl.executor","com.krnl",
        "com.velocity.executor","com.velocity.roblox",
        "com.xeno.executor","com.xeno.roblox",
        "com.evon.executor","com.evon",
        "com.cocoz.executor","com.cocoz.roblox",
        "com.executor.roblox","com.roblox.executor",
        "org.roblox.client","net.roblox.client","io.roblox.client",
    ]
    for pkg in common:
        try:
            out = run_cmd(f"pm list packages {pkg}")
            if f"package:{pkg}" in out and pkg not in found:
                found.append(pkg)
        except:
            pass

    return list(set(found))

def get_ram():
    try:
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
    except:
        return 0, 0, 0, 0

def get_pkg_pid(package):
    # Use pidof with root for exact match
    out = run_cmd(f"pidof {package}").strip()
    if out:
        return out.split()[0]
    # fallback: grep cmdline
    out = run_cmd(f"grep -rl '{package}' /proc/*/cmdline 2>/dev/null | head -1")
    if out:
        try:
            return out.strip().split("/")[2]
        except:
            pass
    return None

def get_pkg_stats(package):
    try:
        pid = get_pkg_pid(package)
        if not pid:
            return None, None

        # RAM from /proc/PID/status VmRSS
        ram_kb = 0
        status = run_cmd(f"cat /proc/{pid}/status")
        for line in status.splitlines():
            if line.startswith("VmRSS:"):
                try:
                    ram_kb = int(line.split()[1])
                except:
                    pass
                break

        # CPU: read stat twice with 1s gap
        def read_stat(p):
            s = run_cmd(f"cat /proc/{p}/stat").split()
            uptime = float(run_cmd("cat /proc/uptime").split()[0])
            return int(s[13]) + int(s[14]), uptime

        t1, u1 = read_stat(pid)
        time.sleep(1)
        t2, u2 = read_stat(pid)
        delta_proc = t2 - t1
        delta_time = (u2 - u1) * 100
        cpu_pct = round((delta_proc / delta_time) * 100, 1) if delta_time > 0 else 0.0

        return round(ram_kb / 1024), cpu_pct
    except:
        return None, None

def get_device_model():
    try:
        return run_cmd("getprop ro.product.model").strip() or "Unknown"
    except:
        return "Unknown"

def is_running(package):
    # pidof gives exact package name match
    out = run_cmd(f"pidof {package}").strip()
    if out:
        return True
    # fallback: check dumpsys activity for foreground
    out2 = run_cmd(f"dumpsys activity processes | grep {package}")
    return bool(out2.strip())

def kill_app(package):
    run_cmd(f"am force-stop {package}")
    run_cmd("am kill-all")
    time.sleep(2)

def launch_roblox(package, place_id):
    deeplink = f"roblox://experiences/start?placeId={place_id}"
    run_cmd(f'am start -a android.intent.action.VIEW -d "{deeplink}"')

def format_uptime(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"

def take_screenshot():
    try:
        path = "/sdcard/rejoin_screen.png"
        run_cmd(f"screencap -p {path}")
        time.sleep(1)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        # try termux storage path
        path2 = os.path.expanduser("~/storage/shared/rejoin_screen.png")
        run_cmd(f"screencap -p {path2}")
        time.sleep(1)
        if os.path.exists(path2):
            with open(path2, "rb") as f:
                return f.read()
    except:
        pass
    return None

def send_webhook(webhook_url, packages_status, device_model, start_times):
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
            ram = f"{info.get('ram_mb', '?')}MB" if info.get('ram_mb') is not None else "?"
            cpu = f"{info.get('cpu_pct', '?')}%" if info.get('cpu_pct') is not None else "?"
            line = (
                f"{dot} **{pkg}**\n"
                f"└ ⏱️ {uptime} | 🎮 `{info['place_id']}` | 🔄 `{info['restarts']}`\n"
                f"└ 🖥️ CPU: `{cpu}` | 💾 RAM: `{ram}`"
            )
            instance_lines.append(line)

        embed = {
            "title": "📊 Roblox Auto Rejoiner Status",
            "color": 3066993 if online == total else 15158332,
            "fields": [
                {
                    "name": "📱 Device",
                    "value": f"🖥️ `{device_model}`",
                    "inline": False
                },
                {
                    "name": "🤖 Instances",
                    "value": f"Total: `{total}` | 🟢 `{online}` | 🔴 `{offline}`",
                    "inline": False
                },
                {
                    "name": "📋 Details",
                    "value": "\n".join(instance_lines) or "No instances",
                    "inline": False
                }
            ],
            "footer": {"text": "Roblox Auto Rejoiner • Termux"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        # Try to send screenshot
        screenshot = take_screenshot()
        if screenshot:
            boundary = "----FormBoundary7MA4YWxkTrZu0gW"
            embed_json = json.dumps({"embeds": [embed]})
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="payload_json"\r\n\r\n'
                f"{embed_json}\r\n"
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="screen.png"\r\n'
                f"Content-Type: image/png\r\n\r\n"
            ).encode() + screenshot + f"\r\n--{boundary}--\r\n".encode()
            req = urllib.request.Request(
                webhook_url,
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST"
            )
        else:
            data = json.dumps({"embeds": [embed]}).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        return False

def monitor(config):
    if not config["packages"]:
        clear()
        print("=" * 40)
        print("  ❌ No packages configured!")
        print("  Set up packages first.")
        print("=" * 40)
        time.sleep(3)
        return

    packages_status = {
        p["package"]: {"place_id": p["place_id"], "running": False, "restarts": 0, "ram_mb": None, "cpu_pct": None}
        for p in config["packages"]
    }

    start_times = {p["package"]: time.time() for p in config["packages"]}
    last_webhook = 0
    device_model = get_device_model()

    clear()
    print("=" * 40)
    print("   🎮 LAUNCHING...")
    print("=" * 40)
    for p in config["packages"]:
        print(f"  🚀 {p['package']}...")
        launch_roblox(p["package"], p["place_id"])
        print(f"  ⏳ Waiting {config['startup_delay']}s...")
        time.sleep(config["startup_delay"])
    print("  ✅ All launched!")
    time.sleep(2)

    while True:
        for pkg, info in packages_status.items():
            info["running"] = is_running(pkg)
            if info["running"]:
                ram, cpu = get_pkg_stats(pkg)
                info["ram_mb"] = ram
                info["cpu_pct"] = cpu

        clear()
        print("=" * 40)
        print("   🎮 ROBLOX AUTO REJOINER - RUNNING")
        print("=" * 40)
        print(f"  🖥️  Device: {device_model}")
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
            ram = f"{info['ram_mb']}MB" if info["ram_mb"] is not None else "?"
            cpu = f"{info['cpu_pct']}%" if info["cpu_pct"] is not None else "?"
            print(f"  {dot} {pkg}")
            print(f"     ⏱️ {uptime} | 🎮 {info['place_id']} | 🔄 {info['restarts']}")
            print(f"     🖥️ CPU: {cpu} | 💾 RAM: {ram}")
            print()
        print("=" * 40)
        print("  Press Ctrl+C to stop")
        print("=" * 40)

        if config["webhook_url"] and (now - last_webhook) >= config["webhook_interval"] * 60:
            ok = send_webhook(config["webhook_url"], packages_status, device_model, start_times)
            last_webhook = now
            print(f"  📡 Webhook: {'✅ Sent' if ok else '❌ Failed'}")
            time.sleep(1)

        for pkg, info in packages_status.items():
            if not info["running"]:
                print(f"\n  ⚠️  {pkg} offline! Restarting in {config['rejoin_delay']}s...")
                time.sleep(config["rejoin_delay"])
                kill_app(pkg)
                time.sleep(3)
                launch_roblox(pkg, info["place_id"])
                info["restarts"] += 1
                start_times[pkg] = time.time()
                print(f"  ⏳ Waiting {config['startup_delay']}s to load...")
                time.sleep(config["startup_delay"])

        time.sleep(config["check_interval"])

def menu():
    while True:
        config = load_config()
        clear()
        print("=" * 40)
        print("   🎮 ROBLOX AUTO REJOINER")
        print("=" * 40)
        print()
        # Show saved packages
        if config["packages"]:
            print("  📦 Packages:")
            for p in config["packages"]:
                print(f"     • {p['package']} | 🎮 {p.get('place_id') or 'No place ID'}")
        else:
            print("  📦 No packages saved")
        webhook_status = "✅ " + config["webhook_url"][:30] + "..." if config["webhook_url"] else "❌ Not set"
        print(f"  🔗 Webhook: {webhook_status}")
        print(f"  ⏱️  Webhook every: {config['webhook_interval']} min(s)")
        print(f"  ⏳ Startup delay: {config['startup_delay']}s")
        print(f"  🔄 Rejoin delay: {config['rejoin_delay']}s")
        print(f"  🕐 Check every: {config['check_interval']}s")
        print()
        print("  [1] Start Auto Rejoin")
        print("  [2] Auto Detect Packages")
        print("  [3] Set Place ID")
        print("  [4] Set Webhook")
        print("  [5] Set Startup Delay")
        print("  [6] Set Rejoin Delay")
        print("  [7] Set Check Interval")
        print("  [8] Remove Package")
        print("  [9] Exit")
        print()
        print("=" * 40)
        choice = input("  Select: ").strip()

        if choice == "1":
            try:
                monitor(config)
            except KeyboardInterrupt:
                clear()
                print("=" * 40)
                print("   ⛔ Stopped.")
                print("=" * 40)
                time.sleep(1)

        elif choice == "2":
            clear()
            print("=" * 40)
            print("   🔍 DETECTING PACKAGES")
            print("=" * 40)
            print("\n  Scanning... please wait...")
            found = detect_roblox_packages()
            if not found:
                print("\n  ❌ No packages found!")
                input("  Press any key to go back...")
                continue
            print(f"\n  Found {len(found)} package(s):\n")
            for i, pkg in enumerate(found):
                already = any(p["package"] == pkg for p in config["packages"])
                tag = " ✅ saved" if already else ""
                print(f"  [{i+1}] {pkg}{tag}")
            print()
            sel = input("  Type number to add, 0 to cancel: ").strip()
            if sel == "0":
                continue
            try:
                idx = int(sel) - 1
                pkg = found[idx]
                if any(p["package"] == pkg for p in config["packages"]):
                    print("  ⚠️  Already saved!")
                    input("  Press any key...")
                    continue
                config["packages"].append({"package": pkg, "place_id": ""})
                save_config(config)
                print(f"\n  ✅ Added {pkg}")
                print("  Use option [3] to set its Place ID")
                input("  Press any key to go back...")
            except:
                print("  Invalid!")
                input("  Press any key...")

        elif choice == "3":
            clear()
            print("=" * 40)
            print("   🎮 SET PLACE ID")
            print("=" * 40)
            print()
            if not config["packages"]:
                print("  No packages saved! Detect packages first.")
                input("  Press any key...")
                continue
            for i, p in enumerate(config["packages"]):
                print(f"  [{i+1}] {p['package']} | Place ID: {p.get('place_id') or 'Not set'}")
            print("  [0] Set same Place ID for ALL packages")
            print()
            sel = input("  Select: ").strip()
            if sel == "0":
                place_id = input("  Enter Place ID for ALL: ").strip()
                for p in config["packages"]:
                    p["place_id"] = place_id
                save_config(config)
                print(f"  ✅ Set {place_id} for all packages!")
                time.sleep(1)
            else:
                try:
                    idx = int(sel) - 1
                    place_id = input(f"  Place ID for {config['packages'][idx]['package']}: ").strip()
                    config["packages"][idx]["place_id"] = place_id
                    save_config(config)
                    print("  ✅ Saved!")
                    time.sleep(1)
                except:
                    print("  Invalid!")
                    time.sleep(1)

        elif choice == "4":
            clear()
            print("=" * 40)
            print("   🔗 SET WEBHOOK")
            print("=" * 40)
            print(f"\n  Current URL: {config['webhook_url'] or 'Not set'}")
            print(f"  Current interval: {config['webhook_interval']} min(s)\n")
            url = input("  Paste Discord Webhook URL: ").strip()
            if url:
                config["webhook_url"] = url
                try:
                    mins = int(input("  Send every how many minutes? (e.g. 1, 5): ").strip())
                    config["webhook_interval"] = mins
                except:
                    config["webhook_interval"] = 1
                save_config(config)
                print(f"\n  ✅ Webhook set! Sending every {config['webhook_interval']} min(s)")
                time.sleep(2)

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
            print("   🔄 REJOIN DELAY")
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
            print("   🕐 CHECK INTERVAL")
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
            clear()
            print("=" * 40)
            print("   🗑️  REMOVE PACKAGE")
            print("=" * 40)
            print()
            if not config["packages"]:
                print("  No packages to remove!")
                input("  Press any key...")
                continue
            for i, p in enumerate(config["packages"]):
                print(f"  [{i+1}] {p['package']}")
            print()
            sel = input("  Select number to remove, 0 to cancel: ").strip()
            if sel == "0":
                continue
            try:
                idx = int(sel) - 1
                removed = config["packages"].pop(idx)
                save_config(config)
                print(f"  ✅ Removed {removed['package']}")
                time.sleep(1)
            except:
                print("  Invalid!")
                time.sleep(1)

        elif choice == "9":
            clear()
            print("   Bye!")
            break
        else:
            time.sleep(0.5)

if __name__ == "__main__":
    menu()
