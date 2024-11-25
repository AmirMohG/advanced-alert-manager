from flask import Flask, request, jsonify
import requests
import yaml
import os
import json
from collections import defaultdict
from time import time

app = Flask(__name__)

# Load config from config.yml
def load_config():
    config_path = os.path.join(os.getcwd(), "config.yml")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at {config_path}")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def logger(message):
    print(f"[LOG] {message}")

config = load_config()

# Track resource alerts
resource_tracking = defaultdict(lambda: {"count": 0, "timestamps": []})

# Send a POST request
def send_post_request(url, payload):
    response = requests.post(url, json=payload)
    return response
import re

def parse_time(time_value):
    if isinstance(time_value, int):  # Already an integer
        return time_value

    if not isinstance(time_value, str):  # Ensure it's a string
        raise ValueError(f"Invalid time value: {time_value}")

    time_units = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800
    }
    match = re.match(r"(\d+)([smhdw]?)$", time_value.strip())
    if not match:
        raise ValueError(f"Invalid time format: {time_value}")

    amount, unit = match.groups()
    return int(amount) * time_units.get(unit, 1)  # Default to seconds

def evaluate_conditions(alert, conditions):
    for condition in conditions:
        condition_type = condition.get("type")
        operator = condition.get("operator")
        key = condition.get("key")
        value = condition.get("value", "")

        # Get the source dictionary (labels or annotations)
        source = alert.get(condition_type + "s", {})

        # Check if the key exists in the source
        field_value = source.get(key)

        if operator == "exists":
            if field_value is None:  # Key must exist
                return False
        elif operator == "equals":
            if field_value is None or str(field_value) != str(value):  # Ensure type-safe comparison
                return False
        else:
            raise ValueError(f"Unknown operator: {operator}")

    return True


# Send a Telegram message
def send_telegram_message(api_token, chat_id, message):
    telegram_url = f"https://api.telegram.org/bot{api_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    response = requests.post(telegram_url, json=payload)
    return response

# Convert labels to a unique string key
def get_resource_key(labels):
    return json.dumps(labels, sort_keys=True)  # Sort keys to ensure consistent order




# Flask route to accept POST requests
# Flask route to process incoming alerts
@app.route("/api/v2/alerts", methods=["POST"])
def process_route():
    try:
        input_json = request.json  # Parse JSON payload
        if not input_json:
            return jsonify({"error": "Invalid JSON payload"}), 400

        # Process the JSON and send requests/messages
        
        results = process_alert(input_json, config)
        
        return jsonify({"results": results}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


from time import time
from collections import defaultdict

# Global tracker for resources
resource_tracking = defaultdict(lambda: {"count": 0, "timestamps": [], "last_sent": 0})


# Process the incoming alert
def process_alert(input_json, config):
    responses = []
    for request_config in config["requests"]:
        method = request_config["method"].upper()
        url = request_config.get("url")
        repeat = request_config.get("repeat", 1)
        interval = parse_time(request_config.get("interval", "60"))
        sleep = parse_time(request_config.get("sleep", "0"))
        conditions = request_config.get("conditions", [])
        data_mappings = request_config["data"]
        api_token = request_config.get("api_token")
        chat_id = request_config.get("chat_id")
        for item in input_json:
            # Evaluate conditions before proceeding
            if conditions and not evaluate_conditions(item, conditions):
                logger(f"Message discarded: Conditions not met for alert {item['labels']}")
                continue  # Skip this request if conditions are not met

            # Get the unique resource key
            resource_key = get_resource_key(item["labels"])
            current_time = time()

            # Access the global tracking dictionary
            if resource_key not in resource_tracking:
                resource_tracking[resource_key] = {
                    "count": 0,
                    "timestamps": [],
                    "last_sent": 0,
                }
            resource_data = resource_tracking[resource_key]

            # Update timestamps and clean up old entries
            resource_data["timestamps"].append(current_time)
            resource_data["timestamps"] = [
                ts for ts in resource_data["timestamps"] if current_time - ts <= interval
            ]

            # Update count
            resource_data["count"] = len(resource_data["timestamps"])

            # Check if the repeat condition is met
            if resource_data["count"] < repeat:
                logger(
                    f"Message discarded: Repeat condition not met for alert {item['labels']} "
                    f"(Current count: {resource_data['count']}, Required: {repeat})"
                )
                continue

            # Check if the last sent time is within the sleep interval
            if current_time - resource_data["last_sent"] < sleep:
                logger(
                    f"Message discarded: Sleep condition not met for alert {item['labels']} "
                    f"(Last sent: {resource_data['last_sent']}, Sleep interval: {sleep}s)"
                )
                continue

            # Trigger the action and record responses
            
            response = perform_action(method, url, data_mappings, item, api_token=api_token, chat_id=chat_id)
            responses.extend(response)

            # Update the last sent time and reset the count/timestamps for the resource
            resource_data["last_sent"] = current_time
            resource_tracking[resource_key] = {"count": 0, "timestamps": [], "last_sent": current_time}

    return responses


# Debugging route to inspect data
def perform_action(method, url, data_mappings, item, api_token, chat_id):
    responses = []

    for mapping in data_mappings:
        input_type = mapping["input"]
        key = mapping.get("key")
        replace_with = mapping.get("replace_with")
        message_template = mapping.get("message")
        source = item.get(input_type + "s", {})  # Use 'labels' or 'annotations'

        if method == "TELEGRAM" and message_template:
            # Parse and replace variables in the message template
            message = message_template
            for placeholder, value in source.items():
                message = message.replace(f"%{placeholder}%", value)
            response = send_telegram_message(api_token, chat_id, message)
            responses.append({
                "method": method,
                "status_code": response.status_code,
                "response_body": response.text,
                "sent_data": {"message": message}
            })
        elif method in ["POST", "GET"]:
            if key in source:
                original_value = source[key]
                if replace_with:
                    source[replace_with] = original_value
                    del source[key]
                if method == "POST":
                    response = send_post_request(url, source)
                elif method == "GET":
                    response = requests.get(url, params=source)
                responses.append({
                    "method": method,
                    "url": url,
                    "status_code": response.status_code,
                    "response_body": response.text,
                    "sent_data": {
                        "key": replace_with,
                        "original_value": original_value
                    }
                })

    return responses

@app.route("/", methods=["POST", "GET"])
def printer():
    print(request.json)
    return jsonify({"results": request.json}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
