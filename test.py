import yaml
import pprint

with open("config.yml") as stream:
    config = yaml.safe_load(stream)["requests"]

pprint.pprint(config)



obj={}

for key in config:
    for data_ in key["data"]:
        key_ = data_["key"]
        key2 = data_["replace_with"]
        if data_["input"] == "label":
            value = f"labels[key_]"
        elif data_["input"] == "annotation":
            value = f"annotations[{key_}]"
        obj.update({key2:value})
        print(key["url"]) 
        #requester(key["url"],obj)
print(obj)
