import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import time
import os
import sys
import ctypes
import re
import traceback

#===========================
# HELPER CLASS FOR TOOLTIPS
#===========================
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.after_id = None  # used to cancel scheduled tooltip

        widget.bind("<Enter>", self.schedule)
        widget.bind("<Leave>", self.hide_tip)

    def schedule(self, event=None):
        # wait 500ms before showing tooltip
        self.after_id = self.widget.after(500, self.show_tip)

    def show_tip(self):
        if self.tipwindow or not self.text:
            return

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            font=("Segoe UI", 9)
        )
        label.pack(ipadx=5, ipady=2)

    def hide_tip(self, event=None):
        # cancel scheduled tooltip if mouse leaves early
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None
# ==========================================
# 1. ADMIN PRIVILEGES
# ==========================================
# Pktmon and Promiscuous mode require root/admin access to tap into the network hardware
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    windowless_exe = sys.executable.replace("python.exe", "pythonw.exe")
    script_path = f'"{os.path.abspath(sys.argv[0])}"'
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", windowless_exe, script_path, None, 0)
    
    if ret <= 32:
        root = tk.Tk()
        root.withdraw() 
        messagebox.showerror("Permission Denied", "LinkDiscovery requires Administrator privileges to access the network card.")
    sys.exit()

# ==========================================
# MAIN APPLICATION CLASS
# ==========================================
class LinkDiscoveryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LinkDiscovery - Python Edition")
        self.root.geometry("650x450")
        self.root.configure(padx=10, pady=10)

        self.etl_file = os.path.join(os.environ['TEMP'], "capture.etl")
        self.txt_file = os.path.join(os.environ['TEMP'], "capture.txt")
        self.is_capturing = False

        self.setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        header = ttk.Label(self.root, text="Network Link Discovery (CDP / LLDP)", font=("Segoe UI", 14, "bold"))
        header.pack(pady=(0, 10))

        # NIC selection UI
        nic_frame = ttk.Frame(self.root)
        nic_frame.pack(fill=tk.X, pady=5)
        nic_label = ttk.Label(nic_frame, text="Select NIC", font=("Segoe UI", 9, "underline"))
        nic_label.pack(side=tk.LEFT)

        ToolTip(nic_label, "NIC = Network Interface Card (your network adapter)")        
        self.nic_var = tk.StringVar()
        self.nic_dropdown = ttk.Combobox(nic_frame, textvariable=self.nic_var, state="readonly")
        self.nic_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill=tk.X, pady=5)

        self.btn_cdp = ttk.Button(btn_frame, text="Listen for CDP (Cisco)", command=lambda: self.start_capture("CDP"))
        self.btn_cdp.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        self.btn_lldp = ttk.Button(btn_frame, text="Listen for LLDP", command=lambda: self.start_capture("LLDP"))
        self.btn_lldp.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        self.btn_stop = ttk.Button(btn_frame, text="Stop Capture", command=self.stop_capture, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # LOG text area
        self.log_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=15, font=("Consolas", 10))
        self.log_area.pack(fill=tk.BOTH, expand=True, pady=10)
        self.log("Ready. Awaiting command...\n", ts=False)

        self.load_nics()

    def load_nics(self):
        # Uses PowerShell to find all network adapters currently connected and "Up"
        ps_cmd = "powershell -command \"Get-NetAdapter | Where-Object Status -eq 'Up' | Select-Object -ExpandProperty Name\""
        output = self.run_cmd(ps_cmd)

        nics = [line.strip() for line in output.splitlines() if line.strip()]
        
        if not nics:
            self.log("[-] No active NICs found!")
            return

        self.nic_dropdown["values"] = nics
        self.nic_dropdown.current(0)  # select first by default

    def log(self, message, ts=True):
        """Prints to the GUI log. ts=True adds a timestamp."""
        # Don't add timestamps to empty lines, dividers, or if explicitly disabled
        if ts and message.strip() != "" and not message.startswith("-"):
            current_time = time.strftime("%H:%M:%S")
            formatted_message = f"[{current_time}] {message}"
        else:
            formatted_message = message
            
        self.log_area.insert(tk.END, formatted_message + "\n")
        self.log_area.see(tk.END)
        self.root.update_idletasks()

    def get_hidden_startupinfo(self):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        return startupinfo

    def run_cmd(self, cmd):
        # Executes system commands in the background
        CREATE_NO_WINDOW = 0x08000000
        try:
            result = subprocess.run(
                cmd, shell=True, 
                creationflags=CREATE_NO_WINDOW,
                startupinfo=self.get_hidden_startupinfo(),
                capture_output=True, text=True
            )
            if result.returncode != 0 and "stop" not in cmd and "remove" not in cmd and "SilentlyContinue" not in cmd:
                self.log(f"[-] Command Warning ({cmd}): {result.stderr.strip()}")
            return result.stdout
        except Exception as e:
            self.log(f"[-] FATAL SYSTEM ERROR executing '{cmd}': {str(e)}")
            return ""

    # ==========================================
    #       PROMISCUOUS MODE
    # Forces the NIC to listen to all traffic, not just packets addressed to its own MAC.
    # Essential for catching multicast CDP/LLDP packets
    # ==========================================
    def enable_promiscuous(self, nic_name):
        self.log(f"[*] Enabling Promiscuous Mode on: {nic_name}")

        self.run_cmd('powershell -command "Remove-NetEventSession -Name \'LinkDiscovery\' -ErrorAction SilentlyContinue"')

        ps_cmd = (
            "$ErrorActionPreference = 'SilentlyContinue'; "
            "New-NetEventSession -Name 'LinkDiscovery' -CaptureMode RealtimeLocal; "
            "Add-NetEventPacketCaptureProvider -SessionName 'LinkDiscovery' -Level 0x0 -CaptureType Physical -TruncationLength 1; "
            f"Add-NetEventNetworkAdapter -Name '{nic_name}' -PromiscuousMode $True; "
            "Start-NetEventSession -Name 'LinkDiscovery'"
        )

        self.run_cmd(f'powershell -command "{ps_cmd}"')

    def disable_promiscuous(self):
        ps_cmd = (
            "Stop-NetEventSession -Name 'LinkDiscovery' -ErrorAction SilentlyContinue; "
            "Remove-NetEventSession -Name 'LinkDiscovery' -ErrorAction SilentlyContinue"
        )
        self.run_cmd(f'powershell -command "{ps_cmd}"')

    def start_capture(self, mode):
        # Tears down the promiscuous session to return the NIC to its normal state
        selected_nic = self.nic_var.get()
        if not selected_nic:
            messagebox.showerror("Error", "Please select a network interface.")
            return
        if self.is_capturing:
            return
        
        self.is_capturing = True
        self.btn_cdp.config(state=tk.DISABLED)
        self.btn_lldp.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        
        self.log_area.delete(1.0, tk.END)
        self.log(f"[*] Starting {mode} capture sequence...")
        threading.Thread(
        target=self.capture_thread,
        args=(mode, selected_nic),
        daemon=True
        ).start()

    def stop_capture(self):
        self.is_capturing = False
        self.log("[-] User aborted packet monitor...")
        self.run_cmd("pktmon stop")
        self.disable_promiscuous()
        self.reset_ui()

    def reset_ui(self):
        self.btn_cdp.config(state=tk.NORMAL)
        self.btn_lldp.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)

    def capture_thread(self, mode, nic_name):
        # The core logic: Cleanup -> Enable Promiscuous -> Set Filter -> Monitor loop
        try:
            # 1. Clean up old files
            self.run_cmd("pktmon stop")
            self.run_cmd("pktmon filter remove")
            if os.path.exists(self.etl_file):
                try: os.remove(self.etl_file)
                except: pass
            if os.path.exists(self.txt_file):
                try: os.remove(self.txt_file)
                except: pass

            # 2. Promiscuous & Filters
            self.enable_promiscuous(nic_name)
            if mode == "CDP":
                self.run_cmd('pktmon filter add "CDP" -m 01-00-0C-CC-CC-CC -d 0x2000')
            else:
                self.run_cmd('pktmon filter add "LLDP" -d LLDP')

            # 3. Listen
            self.log(f"[*] Filters applied. Waiting for {mode} broadcast (60s timeout)...")
            self.run_cmd(f'pktmon start --capture --type flow --pkt-size 0 --file-name "{self.etl_file}" --comp nics')

            # 4. Wait for counter with countdown and timer)
            packet_received = False
            start_time = time.time()
            last_logged_time = 0

            while self.is_capturing:
                elapsed_time = int(time.time() - start_time)

                # Timeout after 60 seconds
                if elapsed_time >= 60:
                    self.log("[-] 60 seconds passed with no packet. Timeout reached.")
                    break

                # Print a heartbeat every 5 seconds
                if elapsed_time > 0 and elapsed_time % 5 == 0 and elapsed_time != last_logged_time:
                    self.log(f"[*] Waiting... {elapsed_time}s")
                    last_logged_time = elapsed_time

                CREATE_NO_WINDOW = 0x08000000
                try:
                    result = subprocess.check_output(
                        "pktmon counters", shell=True, text=True, 
                        creationflags=CREATE_NO_WINDOW,
                        startupinfo=self.get_hidden_startupinfo(),
                        errors='ignore'
                    )
                    if "All counters are zero" not in result:
                        packet_received = True
                        break
                except:
                    break
                
                time.sleep(1)

            if not packet_received:
                return 
            # Logging is handled by the timeout block or the stop button

            # 5. Process
            self.log(f"[+] {mode} Packet caught! Processing data...")
            self.run_cmd("pktmon stop")
            
            # Wait 1.5s for Windows to finish saving the file from RAM
            time.sleep(1.5) 
            self.run_cmd(f'pktmon etl2txt "{self.etl_file}" --out "{self.txt_file}" --verbose 3')

            self.parse_data(mode)

        except Exception as e:
            self.log(f"\n[CRITICAL ERROR] Thread crashed:\n{traceback.format_exc()}")
            self.run_cmd("pktmon stop")
            
        finally:
            self.disable_promiscuous()
            self.is_capturing = False
            self.root.after(0, self.reset_ui)

    def parse_data(self, mode):
        # Reads the text file and uses Regex to find and clean the switch info
        try:
            if not os.path.exists(self.txt_file):
                self.log("[-] Error: Packet file was not generated by Windows.")
                return

            with open(self.txt_file, 'rb') as f:
                raw_bytes = f.read()
                
            if not raw_bytes:
                self.log("[-] Error: The capture file is completely empty.")
                return

            if raw_bytes.startswith(b'\xff\xfe'):
                content = raw_bytes.decode('utf-16-le', errors='ignore')
            else:
                content = raw_bytes.decode('utf-8', errors='ignore')
            
            content = content.replace('\x00', '')

            self.log("-" * 40, ts=False)
            found_any = False
            
            if mode == "CDP":
                mac_pattern = r"(?:MacSrc=|)([0-9A-Fa-f\-]{17})(?:\s*>\s*|\s+MacDst=)01-00-0C-CC-CC-CC"
                mac_match = re.search(mac_pattern, content, re.IGNORECASE)
                if mac_match:
                    self.log(f"{'MAC Address':<15}: {mac_match.group(1).upper()}", ts=False)
                    found_any = True

                patterns = {
                    "Device": r"Device-ID[^\n]*bytes:\s*(.*)",
                    "Address": r"Address[^\n]*bytes:\s*(.*)",
                    "Port": r"Port-ID[^\n]*bytes:\s*(.*)",
                    "Capability": r"Capability[^\n]*bytes:\s*(.*)",
                    "Platform": r"Platform[^\n]*bytes:\s*(.*)",
                    "VLAN": r"Native VLAN ID[^\n]*bytes:\s*(.*)"
                }
                
                for key, pattern in patterns.items():
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        found_any = True
                        clean_val = match.group(1).replace("'", "").strip()
                        self.log(f"{key:<15}: {clean_val}", ts=False)
            
            elif mode == "LLDP":
                lines = content.splitlines()
                lldp_started = False
                for line in lines:
                    if "ethertype LLDP" in line or "0x88cc" in line.lower():
                        lldp_started = True
                        continue
                    if lldp_started:
                        if "End TLV" in line:
                            break
                        clean_line = line.strip()
                        if clean_line:
                            self.log(clean_line, ts=False)
                            found_any = True

            # Failsafe if the parser fails, Data is still shown in raw format
            if not found_any:
                self.log("[-] Parser couldn't format the standard fields. RAW DUMP:")
                self.log(content[:1500].strip(), ts=False) 

            self.log("-" * 40, ts=False)
            self.log("\nReady for next capture.", ts=False)
            
        except Exception as e:
            self.log(f"[-] Data Parsing Error: {str(e)}")

    # Cleanup to stop pktmon if the user closes the window during a scan
    def on_closing(self):
        self.run_cmd("pktmon stop")
        self.run_cmd("pktmon filter remove")
        self.disable_promiscuous()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = LinkDiscoveryApp(root)
    root.mainloop()