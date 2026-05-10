import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
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
        self.after_id = None

        widget.bind("<Enter>", self.schedule)
        widget.bind("<Leave>", self.hide_tip)

    def schedule(self, event=None):
        self.after_id = self.widget.after(500, self.show_tip)

    def show_tip(self):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT, background="#ffffe0", relief=tk.SOLID, borderwidth=1, font=("Segoe UI", 9))
        label.pack(ipadx=5, ipady=2)

    def hide_tip(self, event=None):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

# ==========================================
# 1. ADMIN PRIVILEGES
# ==========================================
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

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ==========================================
# MAIN APPLICATION CLASS
# ==========================================
class LinkDiscoveryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LinkDiscovery - Python Edition V1.0.5")
        self.root.geometry("680x520")
        self.root.configure(padx=10, pady=10)

        self.etl_file = os.path.join(os.getcwd(), "capture.etl")
        self.txt_file = os.path.join(os.getcwd(), "capture.txt")
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
        # Bind the dropdown change to update the IP label automatically
        self.nic_dropdown.bind("<<ComboboxSelected>>", lambda e: self.update_nic_info())

        self.btn_refresh = ttk.Button(nic_frame, text="Refresh", command=self.load_nics)
        self.btn_refresh.pack(side=tk.LEFT, padx=5)

        # Buttons Frame
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill=tk.X, pady=5)

        self.btn_cdp = ttk.Button(btn_frame, text="Listen for CDP", command=lambda: self.start_capture("CDP"))
        self.btn_cdp.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        self.btn_lldp = ttk.Button(btn_frame, text="Listen for LLDP", command=lambda: self.start_capture("LLDP"))
        self.btn_lldp.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        self.btn_stop = ttk.Button(btn_frame, text="Stop Capture", command=self.stop_capture, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        self.btn_save = ttk.Button(btn_frame, text="Save Log", command=self.save_log)
        self.btn_save.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        # GUI Info Bar
        info_frame = ttk.LabelFrame(self.root, text="Current Adapter Information")
        info_frame.pack(fill=tk.X, pady=10, padx=2)

        ttk.Label(info_frame, text="Local IP:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, padx=5, pady=8, sticky="e")
        self.lbl_local_ip = ttk.Label(info_frame, text="Waiting...", font=("Segoe UI", 9))
        self.lbl_local_ip.grid(row=0, column=1, padx=5, pady=8, sticky="w")

        ttk.Label(info_frame, text="Discovered VLAN:", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, padx=(30, 5), pady=8, sticky="e")
        self.lbl_vlan_id = ttk.Label(info_frame, text="Waiting for capture...", font=("Segoe UI", 9, "bold"), foreground="#0055AA")
        self.lbl_vlan_id.grid(row=0, column=3, padx=5, pady=8, sticky="w")

        # LOG text area
        self.log_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=13, font=("Consolas", 10))
        self.log_area.pack(fill=tk.BOTH, expand=True, pady=5)
        self.log("Ready. Awaiting command...\n", ts=False)

        self.load_nics()

    def update_nic_info(self):
        """Updates the Local IP label when a new NIC is selected or refreshed."""
        selected_nic = self.nic_var.get()
        if selected_nic:
            ip = self.get_local_ip(selected_nic)
            self.lbl_local_ip.config(text=ip)
            self.lbl_vlan_id.config(text="Waiting for capture...", foreground="#0055AA")

    def load_nics(self):
        ps_cmd = "powershell -command \"Get-NetAdapter | Where-Object Status -eq 'Up' | Select-Object -ExpandProperty Name\""
        output = self.run_cmd(ps_cmd)
        nics = [line.strip() for line in output.splitlines() if line.strip()]
        
        if not nics:
            self.nic_dropdown.set('')
            self.nic_dropdown["values"] = []
            self.lbl_local_ip.config(text="No active adapters")
            self.log("[-] No active NICs found! Check connections and hit Refresh.")
            return

        self.nic_dropdown["values"] = nics
        self.nic_dropdown.current(0)
        self.update_nic_info()

    def save_log(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt", 
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            title="Save Discovery Log"
        )
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    f.write(self.log_area.get(1.0, tk.END))
                self.log(f"[*] Log saved successfully to: {filepath}")
            except Exception as e:
                self.log(f"[-] Error saving file: {str(e)}")

    def get_local_ip(self, nic_name):
        cmd = f"powershell -command \"(Get-NetIPAddress -InterfaceAlias '{nic_name}' -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress\""
        ip = self.run_cmd(cmd).strip()
        if ip:
            return ip.split('\n')[0].strip()
        return "No IPv4 Address"

    def log(self, message, ts=True):
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
        CREATE_NO_WINDOW = 0x08000000
        try:
            result = subprocess.run(
                cmd, shell=True, 
                creationflags=CREATE_NO_WINDOW,
                startupinfo=self.get_hidden_startupinfo(),
                capture_output=True, text=True
            )
            return result.stdout
        except Exception as e:
            return ""

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

    def cleanup_temp_files(self):
        time.sleep(0.1)
        for temp_file in [self.etl_file, self.txt_file]:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass

    def start_capture(self, mode):
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
        
        # Reset VLAN UI
        self.lbl_vlan_id.config(text="Capturing...", foreground="black")
        
        self.log_area.delete(1.0, tk.END)
        self.log(f"[*] Starting {mode} capture sequence...")
        
        local_ip = self.get_local_ip(selected_nic)
        
        threading.Thread(
            target=self.capture_thread,
            args=(mode, selected_nic, local_ip),
            daemon=True
        ).start()

    def stop_capture(self):
        self.is_capturing = False
        self.log("[-] User aborted packet monitor...")
        self.lbl_vlan_id.config(text="Capture Aborted", foreground="red")
        self.run_cmd("pktmon stop")
        self.disable_promiscuous()
        self.reset_ui()

    def reset_ui(self):
        self.btn_cdp.config(state=tk.NORMAL)
        self.btn_lldp.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)

    def capture_thread(self, mode, nic_name, local_ip):
        try:
            self.run_cmd("pktmon stop")
            self.run_cmd("pktmon filter remove")
            self.cleanup_temp_files()

            self.enable_promiscuous(nic_name)
            if mode == "CDP":
                self.run_cmd('pktmon filter add "CDP" -m 01-00-0C-CC-CC-CC -d 0x2000')
            else:
                self.run_cmd('pktmon filter add "LLDP" -d LLDP')

            self.log(f"[*] Filters applied. Waiting for {mode} broadcast (60s timeout)...")
            self.run_cmd(f'pktmon start --capture --type flow --pkt-size 0 --file-name "{self.etl_file}" --comp nics')

            packet_received = False
            start_time = time.time()
            last_logged_time = 0

            while self.is_capturing:
                elapsed_time = int(time.time() - start_time)
                if elapsed_time >= 60:
                    self.log("[-] 60 seconds passed with no packet. Timeout reached.")
                    self.root.after(0, lambda: self.lbl_vlan_id.config(text="Timeout Reached", foreground="red"))
                    break
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
                time.sleep(0.1)

            if not packet_received:
                return 

            self.log(f"[+] {mode} Packet caught! Processing data...")
            self.run_cmd("pktmon stop")
            time.sleep(0.2) 
            self.run_cmd(f'pktmon etl2txt "{self.etl_file}" --out "{self.txt_file}" --verbose 3')

            self.parse_data(mode, local_ip)

        except Exception as e:
            self.log(f"\n[CRITICAL ERROR] Thread crashed:\n{traceback.format_exc()}")
            self.run_cmd("pktmon stop")
            
        finally:
            self.disable_promiscuous()
            self.cleanup_temp_files()
            self.is_capturing = False
            self.root.after(0, self.reset_ui)

    def parse_data(self, mode, local_ip):
        try:
            if not os.path.exists(self.txt_file):
                self.log("[-] Error: Packet file was not generated.")
                return

            with open(self.txt_file, 'rb') as f:
                raw_bytes = f.read()
                
            if not raw_bytes:
                return

            if raw_bytes.startswith(b'\xff\xfe'):
                content = raw_bytes.decode('utf-16-le', errors='ignore')
            else:
                content = raw_bytes.decode('utf-8', errors='ignore')
            
            content = content.replace('\x00', '')

            self.log("-" * 40, ts=False)

            found_any = False
            vlan_found = "Untagged / None"
            
            frame_vlan = re.search(r"(?:VLAN\s*ID|VlanId)[\s:=]+(\d+)", content, re.IGNORECASE)
            if frame_vlan and frame_vlan.group(1) != "0":
                vlan_found = frame_vlan.group(1)
            
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
                    "VLAN": r"(?:Native VLAN ID|NativeVlan|VLAN ID)[^\n:]*[:=]\s*([^\n\r]+)"
                }
                
                for key, pattern in patterns.items():
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        found_any = True
                        clean_val = match.group(1).replace("'", "").strip()
                        
                        if key == "Capability":
                            clean_val = re.sub(r"\(0x[0-9a-fA-F]+\):\s*", "", clean_val)
                            
                        if key == "VLAN":
                            # Only overwrite if we found something useful
                            vlan_found = clean_val
                            
                        self.log(f"{key:<15}: {clean_val}", ts=False)
                
                # 3. PORT FALLBACK: Extract VLAN from the Port string if Native VLAN TLV was completely missing
                if vlan_found in ["Untagged / None", "0"]:
                    port_match = re.search(r"Port-ID[^\n]*bytes:\s*(.*)", content, re.IGNORECASE)
                    if port_match:
                        # Looks for "VLAN" followed by numbers (e.g., VLAN10_Trusted -> 10)
                        port_vlan = re.search(r"VLAN\D*(\d+)", port_match.group(1), re.IGNORECASE)
                        if port_vlan:
                            vlan_found = port_vlan.group(1)
                            self.log(f"{'VLAN (Inferred)':<15}: {vlan_found}", ts=False)
            
            elif mode == "LLDP":
                lldp_start = content.lower().find("ethertype lldp")
                if lldp_start == -1:
                    lldp_start = content.lower().find("0x88cc")
                
                if lldp_start != -1:
                    lldp_content = content[lldp_start:]
                    
                    lldp_patterns = {
                        "Chassis ID": r"Chassis ID TLV[^\n]*\r?\n[^\n]*?:\s*([^\n\r]+)",
                        "Port ID": r"Port ID TLV[^\n]*\r?\n[^\n]*?:\s*([^\n\r]+)",
                        "Port Desc": r"Port Description TLV[^\n]*:\s*([^\n\r]+)",
                        "System Name": r"System Name TLV[^\n]*:\s*([^\n\r]+)",
                        "System Desc": r"System Description TLV[^\n]*\r?\n([^\n\r]+)",
                        # BROADER LLDP VLAN REGEX
                        "VLAN": r"(?:Port VLAN ID|VLAN ID)[^\n:]*[:=]\s*([^\n\r]+)" 
                    }
                    
                    for key, pattern in lldp_patterns.items():
                        match = re.search(pattern, lldp_content, re.IGNORECASE)
                        if match:
                            found_any = True
                            clean_val = match.group(1).replace("'", "").strip()
                            if key == "VLAN":
                                vlan_found = clean_val
                            self.log(f"{key:<15}: {clean_val}", ts=False)

                    mgmt_matches = re.findall(r"AFI IPv[46][^\n]*?:\s*([a-fA-F0-9\.\:]+)", lldp_content, re.IGNORECASE)
                    if mgmt_matches:
                        found_any = True
                        unique_ips = list(dict.fromkeys(mgmt_matches))
                        self.log(f"{'Mgmt Address':<15}: {', '.join(unique_ips)}", ts=False)

            # Update the GUI safely from the thread
            self.root.after(0, lambda v=vlan_found: self.lbl_vlan_id.config(text=v, foreground="green"))

            if not found_any:
                self.log("[-] Parser couldn't format the standard fields. RAW DUMP:")
                self.log(content[:1500].strip(), ts=False) 

            self.log("-" * 40, ts=False)
            self.log("\nReady for next capture.", ts=False)
            
        except Exception as e:
            self.log(f"[-] Data Parsing Error: {str(e)}")

    def on_closing(self):
        self.run_cmd("pktmon stop")
        self.run_cmd("pktmon filter remove")
        self.disable_promiscuous()
        self.cleanup_temp_files()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = LinkDiscoveryApp(root)
    root.mainloop()