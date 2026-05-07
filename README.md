# LinkDiscoveryWindows
Portable, driverless CDP/LLDP discovery tool for Windows 10/11. Identify switch ports instantly using windows-native pktmon.
Administrator privileges needed!

Many IT professionals rely on legacy tools like LDWin to identify which switch port a laptop is plugged into.
However it does not work for Windows 11! (if updated from 10 to 11 it might work)

This is a modern Python implementation of logic inspired by these excellent tools:

  LinkSkippy (by andkrau) - For the core pktmon logic.
    https://github.com/andkrau/LinkSkippy/blob/main/LinkSkippy.cmd#L16
    
  LDWin (by Chris Hall) - For the original GUI concept.
    https://github.com/chall32/LDWin
