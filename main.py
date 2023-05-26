from loguru import logger
import sys
import datetime
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
logger.remove()
logger.add("logs/out.log", enqueue=True, rotation="1 MB", retention=10, backtrace=True, diagnose=True)
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
import base64
import nbtlib
import io

#variable init
times = []
lastUpdated = 0
nameLookup = {}
lastTry = 0
with open("cache/nameLookup.json", "r") as f:
  nameLookup = json.load(f)

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

def fetchPage(pg):
  global times
  page = getApiPage(pg)
  checkpoint = datetime.datetime.now()
  
  for item in page["auctions"]:
    auc(item, False)
    timetaken = datetime.datetime.now() - checkpoint
    #print("Parsed an item. Time taken: "+ str(timetaken))
    checkpoint = datetime.datetime.now()
    times.append(timetaken)

async def fetchAll(pages):
    with ThreadPoolExecutor(max_workers=5) as executor:
        # allows for 5 threads to be operated at once: reduces the impact of lag. having too many slows it down further
        _ = [executor.submit(fetchPage, pg) for pg in range(pages)]

def auc(item, isScan):
  global nameLookup
  #logger.info(item["item_name"])
  #print(item["item_bytes"])
  if item["bin"]:
    itemName = str(item["item_name"])
    startingBid = int(item["starting_bid"])
    if isScan:
      pass
    elif itemName != None:
      try:
        if "[Lvl" in itemName:
          itemID = "PET"
        elif itemName in nameLookup:
          itemID = nameLookup[itemName]
        else:
          x_bytes = base64.b64decode(item["item_bytes"])
          x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
          itemID = x_object["i"][0]["tag"]["ExtraAttributes"]["id"]
          nameLookup[itemName] = itemID
          with open('cache/item.json', "w") as file:
            json.dump(x_object, file, ensure_ascii=False, indent=4)
        #yep so we got the ID
      
        #not necessary, slows down code

      except Exception:
        logger.opt(exception=Exception).error("error occured while printing bytes "+item["item_bytes"]+" item "+item["item_name"])
        
  

def main():
  global lastUpdated, times, nameLookup, lastTry
  api = getApiPage(0)
  if api['success'] and api["lastUpdated"] != lastUpdated:
    lastUpdated = api["lastUpdated"]
    times = []
    beforeparse = datetime.datetime.now()
    ####REMOVE AFTER WORKING
    with open('cache/api.json', "w") as file:
      json.dump(api, file, ensure_ascii=False, indent=4)  

      loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    future = asyncio.ensure_future(fetchAll(api["totalPages"]))
    loop.run_until_complete(future)
    #await fetch_tasks
    times.sort()
    logger.info("Parsing Complete. "+str(len(times))+" items parsed, with a total time taken of "+str(datetime.datetime.now() - beforeparse)+".\nFastest time: "+str(times[0])+" | Median time: "+str(times[int(len(times) / 2)]) + " | Slowest time: "+str(times[-1]))
    with open("cache/nameLookup.json", "w") as f:
      f.truncate(0)
      json.dump(nameLookup, f, indent=4, ensure_ascii=False)
  else:
    lastTry = milliTime()
  
main()

while True:
  if lastTry < milliTime() + 500:
    if (lastUpdated < milliTime() + 59000):
      main()
      
    
