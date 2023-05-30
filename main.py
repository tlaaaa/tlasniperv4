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
import re

#variable init
times = []
lastUpdated = 0
updateTime = 0
nameLookup = {}
LBIN = {}
lastTry = 0
count = 0
with open("cache/nameLookup.json", "r") as f:
  nameLookup = json.load(f)
with open("data/lbin.json", "r") as f:
  avglbin = json.load(f)

#functions!!
def milliTime():
  return (int(time.time()*1000))

def removeFormatting(string):
  unformattedString = re.sub("§.", "", string)
  return unformattedString

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
  global nameLookup, LBIN, lastUpdated, count, avglbin
  #logger.info(item["item_name"])
  #print(item["item_bytes"])

  if item["bin"]:
    itemName = str(item["item_name"])
    startingBid = int(item["starting_bid"])
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
        #with open('cache/item.json', "w") as file:
        #  json.dump(x_object, file, ensure_ascii=False, indent=4)
    except Exception:
      logger.opt(exception=Exception).error("error occured while getting item id "+item["item_bytes"]+" item "+item["item_name"])
    
    if isScan:
      if item["start"] > lastUpdated - 60_000:
        count = count + 1
        if itemID in avglbin:
          profit = avglbin[itemID] - startingBid
          if profit > 500_000:
            print("flip!!! "+itemName + " /viewauction "+item["uuid"]+"\nprice: "+str(startingBid)+" value apparently: "+str(avglbin[itemID])+" profit: "+str(profit)+"\nlowest bin: "+str(LBIN[itemID])+" difference from lbin: "+str(LBIN[itemID]-startingBid))
    
    elif itemName != None:
        #yep so we got the ID lets just do lbin stuff
        if itemID in LBIN:
          if LBIN[itemID] > startingBid:
            LBIN[itemID] = startingBid
        else:
          LBIN[itemID] = startingBid
      
     
        
def doEnded():
  try:
    start_of_ended = datetime.datetime.now()
    recentlyEnded = requests.get("https://api.hypixel.net/skyblock/auctions_ended").json()
    with open("cache/recentlyEnded.json", "w") as f:
      f.truncate(0)
      json.dump(recentlyEnded, f, indent=4, ensure_ascii=False)
    for item in recentlyEnded["auctions"]:
      x_bytes = base64.b64decode(item["item_bytes"])
      x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
      itemID = x_object["i"][0]["tag"]["ExtraAttributes"]["id"]
      #print(removeFormatting(x_object["i"][0]["tag"]["display"]["Name"] + " " + str(item["price"])))
    logger.info("Fetched Ended Auctions, "+str(len(recentlyEnded["auctions"]))+" auctions found. Time Taken: "+str(datetime.datetime.now() - start_of_ended))
  except Exception:
    logger.opt(exception=Exception).error("error occured while fetching ended auctions")

def main():
  global lastUpdated, times, nameLookup, lastTry, LBIN, count, updateTime
  api = getApiPage(0)
  if api != None:
    if api['success'] and ( api["lastUpdated"] != lastUpdated ):
      lastUpdated = api["lastUpdated"]
      logger.info("time after api update: "+str(milliTime() - lastUpdated))
      if updateTime == 0:
        updateTime = lastUpdated
      else:
        updateTime = milliTime()
      ##do flip calculations here
        count = 0
        times = []
        beforescan = datetime.datetime.now()
        for item in api["auctions"]:
          itemStart = datetime.datetime.now()
          auc(item, True)
          times.append(datetime.datetime.now() - itemStart)
        logger.info(str(count)+" new items have been scanned, with a total time taken of "+str(datetime.datetime.now() - beforescan)+".\nFastest time: "+str(times[0])+" | Median time: "+str(times[int(len(times) / 2)]) + " | Slowest time: "+str(times[-1]))
      
      #caching prices here yeah
      times = []
      LBIN = {}
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
      logger.info("Fetching Complete. "+str(len(times))+" items parsed, with a total time taken of "+str(datetime.datetime.now() - beforeparse)+".\nFastest time: "+str(times[0])+" | Median time: "+str(times[int(len(times) / 2)]) + " | Slowest time: "+str(times[-1]))
      logger.info("lastUpdated: "+str(lastUpdated))

      with open("cache/nameLookup.json", "w") as f:
        f.truncate(0)
        json.dump(nameLookup, f, indent=4, ensure_ascii=False)
      try:
        with open("data/lbin.json", "r") as lbinfile:
          avglbin = json.load(lbinfile)
        for id in LBIN:
          if id in avglbin:
            avglbin[id] = int(avglbin[id] - avglbin[id]/1000 + LBIN[id]/1000)
          else:
            avglbin[id] = LBIN[id]
        with open("data/lbin.json", "w") as lbinfile:
          lbinfile.truncate(0)
          json.dump(avglbin, lbinfile, indent=2, ensure_ascii=False)
      except Exception:
        logger.opt(exception=Exception).error("Something went wrong while saving average LBIN data.")
        #add failsafe here! wait where is the failsafe

      #going through and getting data from sold auctions
      doEnded()
    else:
      lastTry = milliTime()
      print("no new data.. trying again soon..")
  else:
    logger.info("retrying in 5 seconds")
    lastTry = milliTime() + 5000
  
main()

while True:
  if lastTry < milliTime() - 500:
    if (updateTime < milliTime() - 59_000):
      main()
      
    
