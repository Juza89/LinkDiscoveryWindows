# LinkDiscoveryWindows (LDWIN Alternative for Windows 11)

A portable, driverless CDP (Cisco Discovery Protocol) and LLDP (Link Layer Discovery Protocol) discovery tool for Windows 10 and Windows 11. 

Originally developed to quickly map out large-scale network outlet deployments (such as in hotels), this tool serves as a modern replacement for legacy utilities like LDWin that struggle to run reliably on Windows 11. It identifies which switch port a Windows machine is plugged into instantly using native Windows packet monitoring tools. (Credit to LinkSkippy!)

## Key Features

* **Windows 11 Native:** Built to work flawlessly on modern Windows OS without requiring third-party packet capture drivers (like WinPcap or Npcap).
* **Driverless Capture:** Leverages the built-in Windows `pktmon` utility to capture broadcast packets.
* **CDP & LLDP Support:** Listens for and parses both major discovery protocols.
* **Accurate VLAN Parsing:** Parses and displays the correct VLAN IDs from the packet headers (ensuring tagged VLANs display their actual ID, like VLAN 10, rather than defaulting to 0).

## Why I built this

Many IT professionals rely on legacy tools to identify network topology from the endpoint. However, popular tools like LDWin often fail or require tedious workarounds when machines are upgraded from Windows 10 to Windows 11. `LinkDiscoveryWindows` solves this by rewriting the concept from the ground up in Python, relying solely on native OS capabilities to ensure it works every time you plug into a new wall jack.

## Prerequisites & Requirements

* **OS:** Windows 10 (October 2018 Update or newer) or Windows 11.
* **Privileges:** **Administrator privileges are absolutely required!** The tool must interact with the network interface card in promiscuous mode to capture network traffic. 

## How to Use
1. Download the .exe in the "releases" -section
2. Run as administrator
3. *Note: If you do not run it as an Administrator, the script will automatically attempt to prompt you for UAC elevation.*
4. Select your active Network Interface Card (NIC) from the dropdown menu.
5. Click **Listen for CDP** or **Listen for LLDP** depending on your switch environment.
6. The tool will enable promiscuous mode, apply the necessary filters, and wait for the switch to broadcast its discovery packet (usually within 60 seconds).
7. Once captured, the tool will parse the data and display the Switch Name, Port ID, Chassis ID, and VLAN information.

## Credits & Acknowledgements

This is a modern Python implementation of logic inspired by these excellent legacy tools:
* [LinkSkippy by andkrau](https://github.com/andkrau/LinkSkippy) - For the core `pktmon` execution logic.
* [LDWin by Chris Hall](https://github.com/chall32/LDWin) - For the original GUI concept and workflow that inspired this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. Copyright (c) 2026 Juza89.
