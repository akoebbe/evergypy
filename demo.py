import json

from evergypy import Evergy


def get_creds():
    with open("credentials.json", "r") as f:
        return json.loads(f.read())


creds = get_creds()
username = creds["username"]
password = creds["password"]
account_num = creds["account_num"]
premise_id = creds["premise_id"]

evergy = Evergy(username, password, account_num)

data = evergy.get_usage()
print(evergy.get_premises(), end="\n")
print(data, end="\n")
print("Today's kWh: " + str(data[-1]["usage"]), end="\n")
