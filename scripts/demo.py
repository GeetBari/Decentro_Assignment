"""Create an isolated demo group through a running API. Does not reset existing data."""

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    def call(method, path, body=None):
        request = Request(
            base + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15) as response:
            return json.load(response)

    try:
        users = [call("POST", "/users", {"name": name}) for name in ["Mohit", "Rahul", "Ankit"]]
        group = call("POST", "/groups", {"name": "Goa Trip Demo"})
        group_id = group["id"]
        for user in users:
            call("POST", f"/groups/{group_id}/members", {"user_id": user["id"]})
        expense = call(
            "POST",
            "/expenses",
            {
                "group_id": group_id,
                "paid_by": users[0]["id"],
                "amount": "1200.00",
                "description": "Dinner",
                "category": "food",
            },
        )
        print("Created dinner:")
        print(json.dumps(expense, indent=2))
        print("\nBalances before settlement:")
        balances = call("GET", f"/balances?group_id={group_id}")
        print(json.dumps(balances, indent=2))
        assert [row["amount"] for row in balances["balances"]] == ["400.00", "400.00"]
        call(
            "POST",
            f"/groups/{group_id}/settlements",
            {
                "from_user_id": users[1]["id"],
                "to_user_id": users[0]["id"],
                "amount": "400.00",
            },
        )
        print("\nRemaining settlement suggestion:")
        suggestions = call("GET", f"/groups/{group_id}/settlement-suggestions")
        print(json.dumps(suggestions, indent=2))
        assert suggestions["payment_count"] == 1
        assert suggestions["suggestions"][0]["from_user_id"] == users[2]["id"]
        print(f"\nDemo verified. Group ID: {group_id}. Explore {base}/docs")
    except (HTTPError, URLError) as error:
        parser.exit(1, f"Demo request failed: {error}. Check that the API is running.\n")


if __name__ == "__main__":
    main()
