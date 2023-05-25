from loguru import logger
import sys
import datetime
import time
import asyncio
logger.remove()
logger.add("out.log", enqueue=True, rotation="1 MB", backtrace=True, diagnose=True)
logger.add(sys.stderr, colorize=True, format="| <g><d>{time:HH:mm:ss}</d></g> | <g><b>{level}</b></g> | {message} |", level="INFO")

start_time = datetime.datetime.now()
#Keeps thing running on replit, remove if you don't need
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
class MyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(bytes("a", 'utf8'))
        except:
          pass

def run():
    logger.info("Api up. Time taken: "+ str(datetime.datetime.now() - start_time))
    httpd = HTTPServer(('', 8000), MyHandler)
    httpd.serve_forever()

t = Thread(target=run)
t.start()

#real code starts here
import json
import requests
from auction import auc

#variable init
times = []
lastUpdated = 0

#functions!!
def milliTime():
  return (int(time.time()*1000))

def getApiPage(page):
  try:
    api = requests.get("https://api.hypixel.net/skyblock/auctions?page="+str(page)).json()
    return api
  except Exception as e:
    logger.opt(exception=e).error("error occured while requesting api")
  #print("Request Returned. Time taken: "+ str(datetime.datetime.now() - start_time))

async def fetchPage(page):
  page = getApiPage(a)
  checkpoint = datetime.datetime.now()
  
  for item in page["auctions"]:
    auc(item, False)
    timetaken = datetime.datetime.now() - checkpoint
    #print("Parsed an item. Time taken: "+ str(timetaken))
    checkpoint = datetime.datetime.now()
    times.append(timetaken)

api = getApiPage(0)
if api['success'] or api["lastupdated"] != lastUpdated:
  lastUpdated = api["lastUpdated"]
  times = []
  beforeparse = datetime.datetime.now()
  ####REMOVE AFTER WORKING
  with open('cache/api.json', "w") as file:
    json.dump(api, file, ensure_ascii=False, indent=4)  

  for a in range(api["totalPages"]):
    asyncio.run(fetchPage(a))
  times.sort()
  logger.info("Parsing Complete. "+str(len(times))+" items parsed, with a total time taken of "+str(datetime.datetime.now() - beforeparse)+".\nFastest time: "+str(times[0])+" | Median time: "+str(times[int(len(times) / 2)]) + " | Slowest time: "+str(times[-1]))
    