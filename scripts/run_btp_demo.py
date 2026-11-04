import subprocess
import sys
import argparse
from pathlib import Path

def run_demo(mode: str):
    print(f"\n{'='*80}")
    print(f"SCDM BTP DEMONSTRATION RUNNER ({mode} MODE)")
    print(f"{'='*80}")
    print("\nExecuting scenario: Disruption affecting 'Microsoft Corporation' due to 'Server Outage'\n")
    
    cmd = [
        sys.executable,
        "-m", "scdm",
        "--focal-company", "Microsoft Corporation",
        "--query", "Server Outage affecting critical compute node suppliers",
        "--mode", mode
    ]
    
    # We auto-approve the human gate for the automated BTP demo runner
    # We pipe 'y' to stdin
    
    try:
        process = subprocess.run(
            cmd,
            input=b"y\n",
            capture_output=False,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[DEMO FAILED] Workflow encountered a fatal error. Exit code: {e.returncode}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SCDM BTP Demo")
    parser.add_argument("--mode", choices=["MOCK", "DEMO"], default="MOCK", help="Run mode")
    args = parser.parse_args()
    
    run_demo(args.mode)
