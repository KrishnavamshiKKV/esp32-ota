# ====================================================================
# --- CORE MODULES AND INITIALIZATION ---
# ====================================================================
from machine import UART, WDT 
import utime
import uos
import sys

# Import all necessary libraries at the top
try:
    import dataCall
    import request
    # We are not using app_fota anymore in this version
except Exception as e:
    uart2_early = UART(UART.UART2, 9600, 8, 0, 1, 0)
    utime.sleep(1)
    uart2_early.write("FATAL: Import error: {}. Halting.\r\n".format(e))
    while True:
        utime.sleep(1)

# Initialize UART2 for debugging
uart2 = UART(UART.UART2, 9600, 8, 0, 1, 0)
utime.sleep(1)

def debug(msg):
    """Sends a message over UART2 for debugging."""
    if not isinstance(msg, str):
        msg = str(msg)
    uart2.write(msg + "\r\n")

debug("BOOTING...")

# ====================================================================
# --- OTA UPDATE CONFIGURATION (ACTION REQUIRED) ---
# ====================================================================
CURRENT_VERSION = 1.2  # Set this to 1.0 for the first deployment

# --- FIX #1: Correct file path for QuecPython filesystem ---
# The target file must be in the /usr directory.
TARGET_FILENAME = "/usr/main.py" 

# --- CORRECT GITHUB RAW URLs FOR YOUR REPOSITORY ---
VERSION_URL = "https://raw.githubusercontent.com/KrishnavamshiKKV/esp32-ota/main/version.txt"
SCRIPT_URL = "https://raw.githubusercontent.com/KrishnavamshiKKV/esp32-ota/main/main.py"

# ====================================================================
# --- OTA UPDATE FUNCTION (Manual Download Method) ---
# ====================================================================
def perform_ota_check():
    """
    Checks for a new script version and downloads it manually,
    using the correct file path and a memory-safe streaming method.
    """
    debug("OTA: Starting Update Check")
    debug("OTA: Current Version: {}".format(CURRENT_VERSION))

    # Step 1: Fetch latest version info
    try:
        r = request.get(VERSION_URL, timeout=20)
        response_builder = ""
        for chunk in r.text:
            response_builder += chunk
        latest_version = float(response_builder.strip())
        r.close()
        debug("OTA: Server version is: {}".format(latest_version))
    except Exception as e:
        debug("OTA: ERROR getting version: {}".format(e))
        return

    # Step 2: Compare with current version
    if latest_version <= CURRENT_VERSION:
        debug("OTA: Script is up to date.")
        return

    debug("@OTA: New version found! Downloading script...$")

    # Step 3: Try downloading the new script
    try:
        r = request.get(SCRIPT_URL, timeout=120) # Longer timeout for bigger file
        debug("OTA: Script Download Status: {}".format(r.status_code))

        if r.status_code != 200:
            debug("OTA: Download failed. HTTP code: {}".format(r.status_code))
            r.close()
            return

        # --- FIX #2: Stream the file directly to flash to save RAM ---
        # This is the memory-safe way to write the file.
        debug("OTA: Writing to file {}...".format(TARGET_FILENAME))
        with open(TARGET_FILENAME, "w") as f:
            for chunk in r.text:
                f.write(chunk)
        # --- End of Fix #2 ---
        
        r.close()

        #Using the Watchdog Timer for a reliable reboot ---
        debug("@OTA: UPDATE SUCCESSFUL! Forcing hardware reboot with Watchdog in 20 seconds...$")
        
        # Start the watchdog with a 1-second timeout (1000 milliseconds)
        wdt = WDT(timeout=1000)
        
        # Enter an infinite loop to intentionally "hang" the software.
        while True:
            pass  # Do nothing and wait for the watchdog to bite.
        # --- End of Watchdog Reboot Fix ---

    except Exception as e:
        debug("@OTA: FAILED during download/write: {}$".format(e))

# ====================================================================
# --- YOUR WORKING CODE ---
# ====================================================================
def activate_pdp():
    try:
        debug("Setting PDP context for Airtel...")
        dataCall.setPDPContext(1, 0, "airtelgprs.com", "", "", 0)
    except Exception as e:
        debug("@PDP Setup Failed$: {}".format(e))
        return False

    debug("Waiting for PDP to activate...")
    for i in range(15):
        status = dataCall.getInfo(1, 0)
        if status and len(status) > 2 and status[2][0] == 1:
            ip_addr = status[2][2]
            if ip_addr and ip_addr.count('.') == 3:
                debug("@PDP is active$ with IP: {}".format(ip_addr))
                return True
        utime.sleep(2)
    debug("@PDP failed to activate after retries.$")
    return False

last_response = ""
def check_server():
    global last_response
    try:
        r = request.get("https://esp32-ota-7bffb-default-rtdb.firebaseio.com/command.json")
        
        response_builder = ""
        for chunk in r.text:
            response_builder += chunk
        current_response = response_builder.strip()

        r.close()

        if current_response and current_response != last_response:
            last_response = current_response
            debug("New Firebase content found!")
            debug(current_response) 
        else:
            debug("No change on Firebase.")
    except Exception as e:
        debug("Error checking Firebase server: {}".format(e))

# ====================================================================
# --- EXECUTION FLOW ---
# ====================================================================

# Step 1: Connect to the network
if activate_pdp():
    # Step 2: Perform a one-time OTA check on boot
    perform_ota_check() # Using the corrected function

    # If the script continues, it means no update was performed.
    # Now, start your main application loop.
    debug("@OTA check complete. Starting main application.$")
    
    while True:
        check_server()
        debug("Version {}: Main Loop Running...".format(CURRENT_VERSION))
        utime.sleep(10)
else:
    # If network fails, rebooting is the best option
    debug("@FATAL: Network failed. Rebooting in 30 seconds.$")
    # Start the watchdog with a 1-second timeout (1000 milliseconds)
    wdt = WDT(timeout=1000)
    while True:
        pass  # Do nothing and wait for the watchdog to bite.
    # --- End of Watchdog Reboot Fix ---