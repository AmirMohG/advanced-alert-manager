import requests
#from flask import Flask, request
import yaml
import pprint

with open("config.yml") as stream:
    config = yaml.safe_load(stream)["requests"]

pprint.pprint(config)

app = Flask(__name__)

def requester(url,method="get", body_json={}):
    #TODO lower
    if method.lower()=="get":
        requests.get(url,body_json)
        print(f"requests.get {url} + {body_json}")



@app.route('/api/v2/alerts', methods=['GET',"POST"])
def handle_request():
    data=request.json
    print(data)
    labels = data["labels"]
    annotations = data["annotations"]
    for key in config:
        obj={}
        for data_ in key["data"]:
            key_ = data_["key"]
            key2 = data_["replace_with"]
            if data_["input"] == "label":
                value = labels[{key_}]
            elif data_["input"] == "annotation":
                value = annotations[{key_}]
            obj.update({key2:value})
            print(key["url"])
            print(obj)
            print(key["method"])
            #requester("get",obj)
    #print(obj)
    #requester("get",obj)
    return "Request received", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)


