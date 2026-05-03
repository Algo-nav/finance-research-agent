import os
from dotenv import load_dotenv

# Load the .env file into environment variables.
# This must be called before any os.getenv() call.
# In production (Hugging Face Spaces), this line does nothing
# because secrets are already in the environment — which is correct behavior.
load_dotenv()

def verify_keys():
    keys = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "FMP_API_KEY": os.getenv("FMP_API_KEY"),
        "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY"),
        "FRED_API_KEY": os.getenv("FRED_API_KEY"),
    }

    all_good = True
    for name, value in keys.items():
        if value is None:
            print(f"MISSING: {name}")
            all_good = False
        elif len(value) < 8:
            # Catches placeholder values like "your_key_here"
            print(f"LOOKS WRONG: {name} (value too short, check .env)")
            all_good = False
        else:
            # Print only first 6 chars so you can visually confirm
            # it matches your key without exposing it in terminal output
            print(f"OK: {name} = {value[:6]}...")

    print()
    if all_good:
        print("All keys loaded. Ready to build.")
    else:
        print("Fix the above before continuing.")

if __name__ == "__main__":
    verify_keys()