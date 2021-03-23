import datetime

TIME = "20210323074817"

newtime = datetime.datetime.strptime(TIME, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
print(newtime)
