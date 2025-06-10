import os
import time
import random
from cryptography.fernet import Fernet  # For simulated encryption

def generate_fake_files(num_files=10, target_dir="test_files"):
    """Create dummy files to 'encrypt' (safe for testing)."""
    os.makedirs(target_dir, exist_ok=True)
    for i in range(num_files):
        with open(f"{target_dir}/victim_file_{i}.txt", "w") as f:
            f.write(f"SIMULATED_FILE_CONTENTS_{random.randint(1000, 9999)}")

def simulate_encryption(target_dir="test_files"):
    """Mimic ransomware behavior (no real encryption)."""
    key = Fernet.generate_key()  # Generate a fake key
    cipher = Fernet(key)
    
    print("[SIM] Starting simulated ransomware attack...")
    time.sleep(1)
    
    for file in os.listdir(target_dir):
        file_path = os.path.join(target_dir, file)
        if os.path.isfile(file_path):
            # Read file, "encrypt" (add prefix), and rewrite
            with open(file_path, "r+") as f:
                data = f.read()
                f.seek(0)
                f.write(f"ENCRYPTED_{data}")  # Simulate encryption
            print(f"[SIM] 'Encrypted' {file}")
            time.sleep(0.3)  # Simulate processing delay

def spike_cpu(duration=5):
    """Simulate CPU load (ransomware behavior)."""
    print(f"[SIM] Spiking CPU for {duration} seconds...")
    start_time = time.time()
    while time.time() - start_time < duration:
        # Burn CPU cycles
        [x**2 for x in range(1, 1000000)]

if __name__ == "__main__":
    print("=== SAFE RANSOMWARE SIMULATOR ===")
    print("This script mimics ransomware behavior WITHOUT harming real files.\n")
    
    # Step 1: Create dummy files
    generate_fake_files()
    
    # Step 2: Simulate encryption + CPU spike
    simulate_encryption()
    spike_cpu()
    
    print("\n[SIM] Attack simulation complete. Check 'test_files/' for dummy results.")