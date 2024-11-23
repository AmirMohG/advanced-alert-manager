from flask import Flask, request, jsonify
import requests
import yaml
import os

app = Flask(__name__)

# Load config from config.yml
def load_config():
    config_path = os.path.join(os.getcwd(), "config.yml")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found at {config_path}")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

config = load_config()

# Process JSON and send HTTP requests based on config
def process_json_and_send_requests(input_json, config):
    responses = []
    for request_config in config["requests"]:
        method = request_config["method"]
        url = request_config["url"]
        data_mappings = request_config["data"]

        for item in input_json:
            for mapping in data_mappings:
                input_type = mapping["input"]
                key = mapping["key"]
                replace_with = mapping["replace_with"]

                # Extract the relevant dictionary (labels or annotations)
                source = item.get(input_type + "s", {})
                if key in source:
                    original_value = source[key]
                    
                    # Prepare data for request
                    if method.upper() == "POST":
                        body = {replace_with: original_value}
                        response = requests.post(url, json=body)
                    elif method.upper() == "GET":
                        params = {replace_with: original_value}
                        response = requests.get(url, params=params)
                    else:
                        continue

                    # Record the response
                    responses.append({
                        "method": method,
                        "url": url,
                        "status_code": response.status_code,
                        "response_body": response.text,
                        "sent_data": {
                            "replace_with": replace_with,
                            "original_value": original_value
                        }
                    })
    return responses

# Flask route to accept POST requests
@app.route("/api/v2/alerts", methods=["POST"])
def process_route():
    try:
        input_json = request.json  # Parse JSON payload
        if not input_json:
            return jsonify({"error": "Invalid JSON payload"}), 400

        # Process the JSON and send HTTP requests
        results = process_json_and_send_requests(input_json, config)
        return jsonify({"results": results}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["POST", "GET"])
def printer():
    print(request.json)
    return jsonify({"results": request.json}), 200
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

