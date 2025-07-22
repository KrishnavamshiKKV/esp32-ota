# ====================================================================
# --- CORE MODULES AND INITIALIZATION ---
# ====================================================================
from machine import UART  # 'reset' is removed from this import
import utime
import uos
import sys              # Import the 'sys' module for rebooting

# Import all necessary libraries at the top
try:
    import dataCall
    import request
    import app_fota
except Exception as e:
    # Initialize UART here to ensure errors can be printed
    uart2_early = UART(UART.UART2, 9600, 8, 0, 1, 0)
    utime.sleep(1)
    uart2_early.write("FATAL: Import error: {}. Halting.\r\n".format(e))
    # Stop execution if a critical library is missing
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
# This is the version of this script.
# When you create a new version, YOU MUST INCREMENT THIS NUMBER.
CURRENT_VERSION = 1.1

# The name of the script we want to update.
TARGET_FILENAME = "main.py" 

# --- CORRECT GITHUB RAW URLs FOR YOUR REPOSITORY ---
VERSION_URL = "https://raw.githubusercontent.com/KrishnavamshiKKV/esp32-ota/main/version.txt"
SCRIPT_URL = "https://raw.githubusercontent.com/KrishnavamshiKKV/esp32-ota/main/main.py"

# ====================================================================
# --- NATIVE OTA UPDATE FUNCTION (Using app_fota) ---
# ====================================================================
def perform_native_ota_check():
    """
    Checks for a new script version and uses the built-in app_fota library.
    """
    debug("@OTA_NATIVE: Starting Update Check$")
    debug("@OTA_NATIVE: Current Version: {}$".format(CURRENT_VERSION))

    # Step 1: Check the version file
    try:
        r = request.get(VERSION_URL, timeout=20)
        if r.status_code != 200:
            debug("@OTA_NATIVE: Failed to get version file. Status: {}$".format(r.status_code))
            r.close()
            return
        
        response_builder = ""
        for chunk in r.text:
            response_builder += chunk
        latest_version = float(response_builder.strip())
        
        r.close()
        debug("@OTA_NATIVE: Server version is: {}$".format(latest_version))
    except Exception as e:
        debug("@OTA_NATIVE: ERROR - Could not get/parse version file: {}$".format(e))
        return

    # Step 2: Compare versions
    if latest_version <= CURRENT_VERSION:
        debug("@OTA_NATIVE: Script is up to date.$")
        return

    debug("@OTA_NATIVE: New version found! Starting download with app_fota...$")

    # Step 3: Use the built-in app_fota library
    try:
        result = app_fota.update(SCRIPT_URL, TARGET_FILENAME)
        if result == 0:
            debug("@OTA_NATIVE: UPDATE SUCCESSFUL!$")
            # Step 4: Reboot using the correct method
            debug("@OTA_NATIVE: Rebooting in 5 seconds to apply update...$")
            utime.sleep(5)
            sys.exit()  # --- CORRECT REBOOT METHOD ---
        else:
            debug("@OTA_NATIVE: FAILED! app_fota.update() returned error code: {}$".format(result))
            return
            
    except Exception as e:
        debug("@OTA_NATIVE: FAILED! An exception occurred during app_fota: {}$".format(e))
        return

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

        if current_response != last_response:
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
    # Step 2: Perform a one-time NATIVE OTA check on boot
    perform_native_ota_check()

    # If the script continues, it means no update was performed.
    # Now, start your main application loop.
    debug("@OTA check complete. Starting main application.$")
    
    while True:
        check_server()
        debug("OTA worked")
        utime.sleep(10)
else:
    # If network fails, rebooting is the best option
    debug("@FATAL: Network failed. Rebooting in 30 seconds.$")
    utime.sleep(30)
    sys.exit() # --- CORRECT REBOOT METHOD ---