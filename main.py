
import time
import json
import os
import argparse
import tempfile
import requests

from datetime import datetime
from zoneinfo import ZoneInfo

url = os.getenv(
    "API_URL",
    "https://bnsgaming.site/api/send.php"
)

# This checks for COUPON first, and falls back to COUPON_CODE if it's not there
coupon = os.getenv("COUPON") or os.getenv("COUPON_CODE")


region = "PK"

uids = [
    "15842394005",
    "16293036206",
    "10885057885",
    "17854582997",
    "18431337306",
    "11501045579",
    "11504633467",
#    "2862394070",
]

PKT = ZoneInfo("Asia/Karachi")


def get_today():
    return datetime.now(PKT).strftime("%Y-%m-%d")


def load_records(path):
    today = get_today()

    try:
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)

        if records.get("date") != today:
            print("New Pakistan day detected. Resetting records.")
            records = {"date": today, "uids": {}}

    except FileNotFoundError:
        records = {"date": today, "uids": {}}

    except (json.JSONDecodeError, OSError):
        raise RuntimeError(
            "Could not safely read success records."
        )

    if not isinstance(records.get("uids"), dict):
        raise RuntimeError("Invalid UID records structure.")

    for uid in uids:
        if records["uids"].get(uid) is not True:
            records["uids"][uid] = False

    return records


def save_records(path, records):
    directory = os.path.dirname(os.path.abspath(path))

    os.makedirs(directory, exist_ok=True)

    # Atomic file replacement
    fd, temp_path = tempfile.mkstemp(
        dir=directory,
        suffix=".tmp"
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=4)

        os.replace(temp_path, path)

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def is_success(response_data):
    if not isinstance(response_data, dict):
        return False

    # Prefer nested data.success when a data object exists.
    if "data" in response_data:
        nested = response_data.get("data")

        return (
            isinstance(nested, dict)
            and nested.get("success") is True
        )

    # Support the response format in your original script.
    return response_data.get("success") is True


def all_completed(records):
    return all(
        records["uids"].get(uid) is True
        for uid in uids
    )


def process_uids(state_file):

    if not coupon:
        raise RuntimeError(
            f"COUPON environment variable is missing. (Detected value: {coupon})"
        )


    records = load_records(state_file)

    print("=" * 50)
    print("DAILY UID AUTOMATION")
    print("Pakistan date:", get_today())
    print("=" * 50)

    if all_completed(records):
        print("All UIDs already completed today.")
        print("No further API requests required.")
        return

    session = requests.Session()

    for uid in uids:

        if records["uids"].get(uid) is True:
            print(f"Skipping completed UID: {uid}")
            continue

        print(f"Processing UID: {uid}")

        payload = {
            "uid": uid,
            "coupon": coupon,
            "region": region
        }

        try:
            response = session.post(
                url,
                json=payload,
                timeout=20
            )

            response.raise_for_status()

            data = response.json()

            if not isinstance(data, dict):
                raise ValueError("Invalid JSON response structure")

            print(data)

            if is_success(data):

                records["uids"][uid] = True

                print(f"SUCCESS: UID {uid}")

                result = data.get("data", data)

                if isinstance(result, dict):
                    print(
                        "Player:",
                        result.get(
                            "PlayerNickname",
                            "N/A"
                        )
                    )

                    print(
                        "Likes Used:",
                        result.get(
                            "LikesUsed",
                            "N/A"
                        )
                    )

                    print(
                        "Coupon Remaining:",
                        result.get(
                            "CouponRemaining",
                            "N/A"
                        )
                    )

                # Save immediately after confirmed success.
                save_records(state_file, records)

            else:
                records["uids"][uid] = False

                print(
                    f"Pending UID {uid}: "
                    f"{data.get('msg', 'Unsuccessful response')}"
                )

        except requests.exceptions.Timeout:
            print(f"TIMEOUT: UID {uid} remains pending.")

        except requests.exceptions.RequestException as e:
            print(f"REQUEST ERROR: {uid}: {e}")

        except (ValueError, requests.exceptions.JSONDecodeError) as e:
            print(f"INVALID RESPONSE: {uid}: {e}")

        except Exception as e:
            print(f"UNEXPECTED ERROR: {uid}: {e}")

        # Persist the latest state.
        save_records(state_file, records)

        print("-" * 40)

        time.sleep(1)

    session.close()

    print("\nDAILY SUMMARY")

    completed = sum(
        1 for uid in uids
        if records["uids"].get(uid) is True
    )

    pending = len(uids) - completed

    print(f"Completed: {completed}/{len(uids)}")
    print(f"Pending: {pending}/{len(uids)}")

    if all_completed(records):
        print("ALL UIDs COMPLETED FOR TODAY.")
    else:
        print("Pending UIDs will be eligible next run.")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--state-file",
        default="success_records.json"
    )

    args = parser.parse_args()

    process_uids(args.state_file)
