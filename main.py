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

config = load_config()

# Track resource alerts
resource_tracking = defaultdict(lambda: {"count": 0, "timestamps": []})

# Send a POST request
def send_post_request(url, payload):
    response = requests.post(url, json=payload)
    return response

# Send a Telegram message
def send_telegram_message(api_token, chat_id, message):
    telegram_url = f"https://api.telegram.org/bot{api_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    response = requests.post(telegram_url, json=payload)
    return response

# Convert labels to a unique string key
def get_resource_key(labels):
    return json.dumps(labels, sort_keys=True)  # Sort keys to ensure consistent order

# Process the incoming alert
def process_alert(input_json, config):
    responses = []

    for request_config in config["requests"]:
        method = request_config["method"].upper()
        url = request_config.get("url")
        repeat = request_config.get("repeat", 1)  # Default repeat is 1
        interval = request_config.get("interval", 60)  # Default interval is 60 seconds
        data_mappings = request_config["data"]
        api_token = request_config.get("api_token")
        chat_id = request_config.get("chat_id")
        api_url = request_config.get("api_url")
        # Telegram-specific configurations
        if method == "TELEGRAM":
            
            if not api_token or not chat_id:
                raise ValueError("TELEGRAM method requires 'api_token' and 'chat_id' in config.")
            if not api_url:
                api_url = "api.telegram.org"
        for item in input_json:
            # Get the unique resource key
            resource_key = get_resource_key(item["labels"])
            current_time = time()
            
            # Update tracking for the resource
            resource_data = resource_tracking[resource_key]
            resource_data["timestamps"].append(current_time)

            # Remove timestamps older than the interval
            resource_data["timestamps"] = [
                ts for ts in resource_data["timestamps"] if current_time - ts <= interval
            ]

            # Update count and check if it meets the repeat threshold
            resource_data["count"] = len(resource_data["timestamps"])

            if resource_data["count"] >= repeat:
                # Perform the action based on the method
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

                # Reset count and timestamps after triggering the action
                resource_tracking[resource_key] = {"count": 0, "timestamps": []}

    return responses

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

def process_alert(input_json, config):
    responses = []
    
    for request_config in config["requests"]:
        method = request_config["method"].upper()
        url = request_config.get("url")
        repeat = request_config.get("repeat", 1)  # Default repeat is 1
        interval = request_config.get("interval", 60)  # Default interval is 60 seconds
        sleep = request_config.get("sleep", 0)  # Default sleep is 0 seconds
        data_mappings = request_config["data"]
        api_token = request_config.get("api_token")
        chat_id = request_config.get("chat_id")
        # Telegram-specific configurations
        if method == "TELEGRAM":
           
            
            if not api_token or not chat_id:
                raise ValueError("TELEGRAM method requires 'api_token' and 'chat_id' in config.")

        for item in input_json:
            # Get the unique resource key
            resource_key = get_resource_key(item["labels"])  # e.g., a stringified version of the labels
            current_time = time()

            # Access the global tracking dictionary
            resource_data = resource_tracking[resource_key]

            # Update timestamps and clean up old entries
            resource_data["timestamps"].append(current_time)
            resource_data["timestamps"] = [
                ts for ts in resource_data["timestamps"] if current_time - ts <= interval
            ]

            # Update count
            resource_data["count"] = len(resource_data["timestamps"])

            # Check if the repeat condition is met
            if resource_data["count"] >= repeat:
                # Check if the last sent time is within the sleep interval
                if current_time - resource_data["last_sent"] < sleep:
                    continue  # Ignore this alert since it's within the sleep interval

                # Trigger the action and record responses
                response = perform_action(method, url, data_mappings, item, api_token, chat_id)
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
