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

#real code starts here
import json
import requests
import base64
import nbtlib
import io
import re
import pickle
from collections import Counter

#variable init
times = []
lastUpdated = 0
updateTime = 0
nameLookup = {}
LBIN = {}
lastTry = 0
count = 0
recentSellers = []
flips = []
petlbin = {}
with open("cache/nameLookup.json", "r") as f:
  nameLookup = json.load(f)
with open("data/lbin.json", "r") as f:
  avglbin = json.load(f)
with open("data/volume.json", "r") as f:
  volume = json.load(f)
with open("data/sold.json", "r") as f:
  avgsold = json.load(f)
with open("cache/skinLookup.json", "r") as f:
  skinLookup = json.load(f)
with open("cache/heldItemLookup.json", "r") as f:
  heldItemLookup = json.load(f)
with open("data/pets/lbindata.pkl", "rb") as f:
  petlbindata = pickle.load(f)

#functions!!
def milliTime():
  return (int(time.time()*1000))

def formatNumber(number):
  number = round(number/1000, 0)*1000
  if number / 1_000_000_000 > 1 or number / 1_000_000_000 < -1:
    formattedNumber = str(round(number / 1_000_000_000, 2)) + "b"
  elif number / 1_000_000 > 1 or number / 1_000_000 < -1:
    formattedNumber = str(round(number / 1_000_000, 2)) + "m"
  elif number / 1_000 > 1 or number / 1_000 < -1:
    formattedNumber = str(round(number / 1_000, 2)) + "k"
  else:
    formattedNumber = str(round(number, 0))
  return formattedNumber
  
def removeFormatting(string):
  unformattedString = re.sub("§.", "", string)
  return unformattedString

def handler(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    elif isinstance(obj, ...):
        return ...
    else:
        raise TypeError


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
  global nameLookup, LBIN, lastUpdated, count, avglbin, flips, skinLookup, heldItemLookup, petlbindata, petlbin, avgsold
  #logger.info(item["item_name"])
  #print(item["item_bytes"])

  if item["bin"]:
    itemName = str(item["item_name"])
    startingBid = int(item["starting_bid"])
    itemLore = str(item["item_lore"])
    #initial blacklist
    try:
      if "[Lvl" in itemName:
        itemID = "PET_"+itemName.split("] ")[1].replace(" ✦", "").replace(" ", "_").upper()
        petLevel = int(itemName.split("]")[0].replace("[Lvl ", ""))
        if petLevel == 100:
          petLevelRange = 100
        elif petLevel <= 69:
          petLevelRange = 0
        elif petLevel <= 84:
          petLevelRange = 70
        elif petLevel <= 94:
          petLevelRange = 85
        elif petLevel <= 99:
          petLevelRange = 95
        else:
          petLevelRange = round(petLevel/10)*10
        petCandied = bool("Pet Candy Used" in itemLore)
        petRarity = item["tier"]
        #print(petLevel)
        if ("✦" in itemName):
          firstLine = itemLore.split("\n\n")[0]
          if firstLine+itemID in skinLookup:
            skin = skinLookup[firstLine+itemID]
          else:
            x_bytes = base64.b64decode(item["item_bytes"])
            x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
            skin = x_object["i"][0]["tag"]["ExtraAttributes"]["petInfo"].split("\"skin\":\"")[1].split("\",")[0]
            skinLookup[firstLine+itemID] = skin
        else:
          skin = None
        if ("Held Item:") in itemLore:
          heldLine = itemLore.split("Held Item: ")[1].split("\n")[0]
          if heldLine in heldItemLookup:
            heldItem = heldItemLookup[heldLine]
          else:
            x_bytes = base64.b64decode(item["item_bytes"])
            x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
            heldItem = x_object["i"][0]["tag"]["ExtraAttributes"]["petInfo"].split("\"heldItem\":\"")[1].split("\",")[0]
            heldItemLookup[heldLine] = heldItem
        else:
          heldItem = None
        petInfo = (itemID, petRarity, petLevelRange, skin, heldItem, petCandied)
        if petInfo not in petlbin:
          petlbin[petInfo] = startingBid
        else:
          if petlbin[petInfo] > startingBid:
            petlbin[petInfo] = startingBid
        #print(petInfo)
      else:
        isHoe = False
        for notId in ("Euclid's Wheat", "Gauss Carrot", "Newton Nether Warts", "Pythagorean Potato", "Turing Sugar Cane"):
          if notId in itemName:
            isHoe = True
            hoelookup = itemName + item["tier"] + str(len(itemLore.split("Counter: ")[1].split("\n\n")[0])) + str(itemLore.count("§ka§r"))
            if hoelookup in nameLookup:
              itemID = nameLookup[hoelookup]
            else:
              x_bytes = base64.b64decode(item["item_bytes"])
              x_object = nbtlib.load(io.BytesIO(x_bytes), gzipped=True, byteorder="big")
              itemID = x_object["i"][0]["tag"]["ExtraAttributes"]["id"]
              nameLookup[hoelookup] = itemID
        if itemName in nameLookup and not isHoe:
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
        if itemID in avglbin and itemID in LBIN and itemID in volume and itemID in avgsold:
          profit = avglbin[itemID] - startingBid
          lbinProfit = LBIN[itemID] - startingBid
          if profit > 500_000 and volume[itemID] > 20 and lbinProfit > 400_000 and profit/avglbin[itemID] > 0.08 and lbinProfit/LBIN[itemID] > 0.07 and avgsold[itemID]*2 > avglbin[itemID]:
            if LBIN[itemID] > avglbin[itemID] * 1.2:
              target = (LBIN[itemID] + avglbin[itemID])/2
            else:
              target = LBIN[itemID] * 0.998 - 1000
            target = int(int(target / 10_000) * 10_000 - 1)
            print(itemName + " /viewauction "+item["uuid"]+"\nprice: "+formatNumber(startingBid)+" value apparently: "+formatNumber(avglbin[itemID])+" profit: "+formatNumber(profit)+"\nlowest bin: "+formatNumber(LBIN[itemID])+" difference from lbin: "+formatNumber(LBIN[itemID]-startingBid)+" volume: "+str(volume[itemID]) + " target: "+str(target))
            flips.append({
              "itemName": itemName,
              "id": item["uuid"],
              "startingBid": startingBid,
              "target": target,
              "purchaseAt": json.dumps(datetime.datetime.fromtimestamp(int((item["start"] + 19000) / 1000)), default=handler).replace('"',"") + "Z",
            })
    
    else:
        #yep so we got the ID lets just do lbin stuff
        if itemID in LBIN:
          if LBIN[itemID] > startingBid:
            LBIN[itemID] = startingBid
        else:
          LBIN[itemID] = startingBid
        
      
     
        
def doEnded():
  global volume, avgsold, recentSellers
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
      itemName = removeFormatting(x_object["i"][0]["tag"]["display"]["Name"])
      itemLore = "\n".join(x_object["i"][0]["tag"]["display"]["Lore"])
      if "[Lvl" in itemName:
        itemID = "PET_"+itemName.split("] ")[1].replace(" ✦", "").replace(" ", "_").upper()
        petLevel = int(itemName.split("]")[0].replace("[Lvl ", ""))
        if petLevel == 100: petLevelRange = 100
        elif petLevel <= 69: petLevelRange = 0
        elif petLevel <= 84: petLevelRange = 70
        elif petLevel <= 94: petLevelRange = 85
        elif petLevel <= 99: petLevelRange = 95
        else: petLevelRange = round(petLevel/10)*10
        petCandied = bool("Pet Candy Used" in itemLore)
        petRarity = x_object["i"][0]["tag"]["ExtraAttributes"]["petInfo"].split("\"tier\":\"")[1].split("\",")[0]
        #print(petLevel)
        if ("✦" in itemName):
          skin = x_object["i"][0]["tag"]["ExtraAttributes"]["petInfo"].split("\"skin\":\"")[1].split("\",")[0]
        else: skin = None
        if ("Held Item:") in itemLore:
          heldItem = x_object["i"][0]["tag"]["ExtraAttributes"]["petInfo"].split("\"heldItem\":\"")[1].split("\",")[0]
        else: heldItem = None
        petInfo = (itemID, petRarity, petLevelRange, skin, heldItem, petCandied)
        #print(petInfo)
      #print(removeFormatting(x_object["i"][0]["tag"]["display"]["Name"] + " " + str(item["price"])))
      recentSellers.append(item["seller"])
      if itemID in volume:
        volume[itemID] = volume[itemID] + 1
      else:
        volume[itemID] = 0
      if itemID in avgsold:
        avgsold[itemID] = int(avgsold[itemID] * 0.96 + item["price"] * 0.04)
      else:
        avgsold[itemID] = item["price"]
    if len(recentSellers) > 1000:
      recentSellers = recentSellers[-999:]
    sellerCount = Counter(recentSellers)
    #print(sellerCount.most_common(10))
    
    logger.info("Fetched Ended Auctions, "+str(len(recentlyEnded["auctions"]))+" auctions found. Time Taken: "+str(datetime.datetime.now() - start_of_ended))
  except Exception:
    logger.opt(exception=Exception).error("error occured while fetching ended auctions")

def main():
  global lastUpdated, times, nameLookup, lastTry, LBIN, count, updateTime, volume, flips, skinLookup, heldItemLookup, petlbindata
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
        flips = []
        beforescan = datetime.datetime.now()
        for item in api["auctions"]:
          itemStart = datetime.datetime.now()
          auc(item, True)
          times.append(datetime.datetime.now() - itemStart)
        logger.info(str(count)+" new items have been scanned, with a total time taken of "+str(datetime.datetime.now() - beforescan)+".\nFastest time: "+str(times[0])+" | Median time: "+str(times[int(len(times) / 2)]) + " | Slowest time: "+str(times[-1]))
      #print(flips)
      if len(flips) > 0:
        payload = {
          "flips": flips
        }
        with open("flips.json", "w") as file:
          json.dump(payload, file, ensure_ascii=False)
      #caching prices here yeah
      times = []
      LBIN = {}
      beforeparse = datetime.datetime.now()
      ####REMOVE AFTER WORKING
      with open('cache/api.json', "w") as file:
        json.dump(api, file, ensure_ascii=False, indent=4)  
  
      loop = asyncio.new_event_loop()
      asyncio.set_event_loop(loop)
      future = asyncio.ensure_future(fetchAll(api["totalPages"]))
      loop.run_until_complete(future)
      #await fetch_tasks
      times.sort()
      logger.info("Fetching Complete. "+str(len(times))+" items parsed, with a total time taken of "+str(datetime.datetime.now() - beforeparse)+".\nFastest time: "+str(times[0])+" | Median time: "+str(times[int(len(times) / 2)]) + " | Slowest time: "+str(times[-1]))
      logger.info("lastUpdated: "+str(lastUpdated))
      
      doEnded()

      with open("cache/nameLookup.json", "w") as f:
        f.truncate(0)
        json.dump(nameLookup, f, indent=4, ensure_ascii=False)
      with open("cache/skinLookup.json", "w") as f:
        f.truncate(0)
        json.dump(skinLookup, f, indent=4, ensure_ascii=False)
      with open("cache/heldItemLookup.json", "w") as f:
        f.truncate(0)
        json.dump(heldItemLookup, f, indent=4, ensure_ascii=False)
      try:
        with open("data/lbin.json", "r") as lbinfile:
          avglbin = json.load(lbinfile)
        for id in LBIN:
          if id in avglbin:
            if avglbin[id] > LBIN[id] * 2:
              avglbin[id] = int(avglbin[id] - avglbin[id]/20 + LBIN[id]/20)
            elif avglbin[id] > LBIN[id] * 1.3:
              avglbin[id] = int(avglbin[id] - avglbin[id]/250 + LBIN[id]/250)
            else:
              avglbin[id] = int(avglbin[id] - avglbin[id]/1000 + LBIN[id]/1000)
          else:
            avglbin[id] = LBIN[id]
        with open("data/lbin.json", "w") as lbinfile:
          lbinfile.truncate(0)
          json.dump(avglbin, lbinfile, indent=2, ensure_ascii=False)
        with open("data/pets/lbindata.pkl", "rb") as petlbinpkl:
          petlbindata = pickle.load(petlbinpkl)
        for petInfo in petlbin:
          if petInfo in petlbindata:
            petlbindata[petInfo] = int(petlbindata[petInfo] - petlbindata[petInfo]/500 + petlbin[petInfo]/500)
          else:
            petlbindata[petInfo] = petlbin[petInfo]
        with open("data/pets/lbindata.json", "w") as petlbinfile:
          petlbinfile.truncate(0)
          petlbinfile.write(str(petlbindata))
        with open("data/pets/lbindata.pkl", "wb") as petlbinpkl:
          petlbinpkl.truncate(0)
          pickle.dump(petlbindata, petlbinpkl)
        for item in volume:
          if volume[item] > 100:
            volume[item] = 100
          elif volume[item] < 0:
            volume[item] = 0
          else:
            volume[item] = volume[item] - volume[item]/1440
        with open("data/volume.json", "w") as volumefile:
          volumefile.truncate(0)
          json.dump(volume, volumefile, indent=2, ensure_ascii=False)
        with open("data/sold.json", "w") as soldfile:
          soldfile.truncate(0)
          json.dump(avgsold, soldfile, indent=2, ensure_ascii=False)
      except Exception:
        logger.opt(exception=Exception).error("Something went wrong while saving average LBIN data.")
        #add failsafe here! wait where is the failsafe
    else:
      lastTry = milliTime()
      print("no new data.. trying again soon..")
  else:
    logger.info("retrying in 5 seconds")
    lastTry = milliTime() + 5000

try:
  main()
except Exception:
  logger.opt(exception=Exception).error("uncaught exception at some point in main()...")

while True:
  if lastTry < milliTime() - 500:
    if (updateTime < milliTime() - 59_000):
      try:
        main()
      except Exception:
        logger.opt(exception=Exception).error("uncaught exception at some point in main()...")
    
