import os
import time
import hashlib
from cryptography.fernet import Fernet  # Simulate encryption

# --- SAFE TEST CONFIG ---
TEST_FILE = "malicious_test.txt"
BACKUP_FILE = "malicious_test_BACKUP.txt"  # Backup to restore later

def create_test_file():
    """Create the test file if it doesn't exist."""
    if not os.path.exists(TEST_FILE):
        with open(TEST_FILE, "w") as f:
            f.write("This is a SAFE test file for ransomware detection.\n")
            f.write("If this content changes unexpectedly, trigger an alert.\n")
            f.write("Original checksum: 3a7bd3e2360a3d29eea436fcfb7e44c735d117c7\n")

def simulate_attack():
    """Mimic ransomware (backup -> modify -> restore)."""
    print("[TEST] Starting SAFE ransomware simulation...")
    
    # Backup original file
    with open(TEST_FILE, "r") as f:
        original_content = f.read()
    with open(BACKUP_FILE, "w") as f:
        f.write(original_content)
    
    # Simulate "encryption" (modify file)
    with open(TEST_FILE, "w") as f:
        f.write("ENCRYPTED_" + original_content)  # Safe modification
    print(f"[TEST] Modified {TEST_FILE} (simulated encryption)")
    
    # Simulate CPU spike (detectable by monitoring)
    print("[TEST] Spiking CPU for 5 seconds...")
    start = time.time()
    while time.time() - start < 5:  # 5-second CPU load
        [x**2 for x in range(1, 1000000)]
    
    # Restore original file
    with open(BACKUP_FILE, "r") as f:
        original_content = f.read()
    with open(TEST_FILE, "w") as f:
        f.write(original_content)
    os.remove(BACKUP_FILE)
    print("[TEST] Restored original file. Simulation complete.")

if __name__ == "__main__":
    create_test_file()
    simulate_attack()